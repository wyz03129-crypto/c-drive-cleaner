# C Drive Cleaner v2 技术架构

状态：第二阶段设计基线  
目标平台：Windows 10 22H2、Windows 11 23H2 及更高版本  
产品目标：在不损害系统、程序状态和用户数据的前提下，快速解释 C 盘占用，并最大化可验证的实际释放空间。

## 1. 架构决策

采用“保留安全思想、重写产品架构”的路线：

- 保留现有白名单、deny-first、扫描后复核、Dry Run、单文件失败隔离等原则。
- 不直接扩展当前串行扫描器和 Tkinter 页面。
- Python 继续作为规则、分析和任务编排层；目标版本为 Python 3.12。
- GUI 改用 PySide6，提供任务进度、取消、分组选择、结果对比和无障碍支持。
- 所有管理员操作进入独立 elevated helper，普通 GUI 进程不持续以管理员运行。
- 只有当 Windows 文件句柄级删除或系统接口确有必要时，才增加小型原生辅助组件；不提前引入大型多语言架构。

## 2. 目标分层

```text
UI / CLI
  ↓
Application Services
  ├─ ScanCoordinator
  ├─ CleanupPlanner
  ├─ CleanupCoordinator
  └─ VerificationService
  ↓
Domain
  ├─ Rule / Finding / ActionPlan
  ├─ RiskPolicy / SafetyDecision
  └─ ScanSnapshot / CleanupReceipt
  ↓
Infrastructure
  ├─ WindowsPathProvider
  ├─ FileSystemScanner
  ├─ StorageAnalyzer
  ├─ RuleRegistry
  ├─ Executors
  ├─ Persistence
  └─ Windows APIs
```

UI 不允许直接删除文件、运行系统命令或拼接清理路径。所有清理必须经过 `CleanupPlanner → SafetyPolicy → Executor → VerificationService`。

## 3. 建议目录结构

```text
c-drive-cleaner/
├─ pyproject.toml
├─ README.md
├─ CHANGELOG.md
├─ src/cdrive_cleaner/
│  ├─ app/
│  │  ├─ scan_service.py
│  │  ├─ cleanup_service.py
│  │  └─ verification_service.py
│  ├─ domain/
│  │  ├─ models.py
│  │  ├─ risk.py
│  │  ├─ policy.py
│  │  └─ errors.py
│  ├─ analysis/
│  │  ├─ fast_scan.py
│  │  ├─ deep_scan.py
│  │  ├─ directory_tree.py
│  │  └─ large_files.py
│  ├─ rules/
│  │  ├─ registry.py
│  │  ├─ predicates.py
│  │  ├─ windows.py
│  │  ├─ browsers.py
│  │  ├─ office.py
│  │  ├─ messaging.py
│  │  └─ developer_tools.py
│  ├─ safety/
│  │  ├─ path_policy.py
│  │  ├─ identity.py
│  │  ├─ reparse.py
│  │  └─ authorization.py
│  ├─ executors/
│  │  ├─ file_delete.py
│  │  ├─ recycle_bin.py
│  │  ├─ dism.py
│  │  ├─ application.py
│  │  └─ advisory.py
│  ├─ windows/
│  │  ├─ known_folders.py
│  │  ├─ disk_space.py
│  │  ├─ restart_manager.py
│  │  └─ elevation.py
│  ├─ persistence/
│  │  ├─ settings.py
│  │  ├─ scan_cache.py
│  │  └─ audit_log.py
│  ├─ ui/
│  └─ cli.py
├─ helper/
│  └─ elevated_helper.py
├─ tests/
│  ├─ unit/
│  ├─ contract/
│  ├─ security/
│  ├─ fixtures/
│  └─ windows_integration/
├─ packaging/
├─ scripts/
└─ docs/
```

## 4. 核心数据模型

### Finding

扫描只产生事实，不授予删除权限：

- `finding_id`
- `rule_id` 和规则版本
- 分类、显示名称、风险等级
- 原始路径、规范路径、卷标识
- 逻辑大小、分配大小、文件数量
- 文件身份快照
- 最近访问/修改时间摘要
- 扫描错误和置信度
- 推荐执行器类型

### ActionPlan

用户选择后重新生成，不直接复用 UI 中的路径：

- 规则与策略版本
- 目标集合及不可变身份
- 所需权限
- 预计释放空间
- 可逆性和用户影响
- 前置条件，如关闭应用或接通电源
- 明确确认文本

### CleanupReceipt

- 每个动作的开始/结束时间
- 授权、执行、跳过和失败原因
- 逻辑删除字节
- 分配大小减少量
- 清理前后磁盘可用空间观测值
- 执行器退出码/HRESULT
- 不包含敏感路径的默认诊断摘要

## 5. 扫描架构

### 快速扫描

目标是尽快回答“有多少明确缓存可清理”：

- 只扫描版本化规则注册表中的可信根目录。
- 使用流式 `os.scandir`，不得将超大目录一次性转换为列表。
- 目录级排除结果缓存一次，不对每个文件重复遍历父目录。
- 有界线程池并行不同物理目录，默认并发数较低，避免压垮磁盘。
- 支持取消令牌、进度事件、超时和部分结果。

### 深度分析

目标是回答“空间到底去了哪里”，不授予清理权限：

- 先宽度优先统计顶层，再向大目录逐层钻取。
- 维护 top-N 大目录和大文件，不保留所有普通文件对象。
- 用户目录、ProgramData、Windows 和应用数据分别标注所有者与风险。
- reparse point 默认不跟随；硬链接大小避免重复估算。
- 无权限区域显示“统计不完整”，不得把未知大小当作 0。
- 支持增量缓存，但缓存只能提升显示速度，不能授权删除。

## 6. 执行器类型

| 执行器 | 用途 | 默认权限 |
|---|---|---|
| `DirectFileDeleteExecutor` | 已证明安全的缓存文件 | 普通用户 |
| `RecycleBinExecutor` | 查询/清空指定卷回收站 | 明确确认 |
| `DismExecutor` | Windows 组件存储清理 | 管理员、单独确认 |
| `ApplicationExecutor` | 调用应用自身受支持的清理命令 | 按规则定义 |
| `AdvisoryExecutor` | 无安全自动接口的项目 | 只显示引导 |

禁止通用“以管理员身份递归删除目录”的执行器。

## 7. Windows 官方机制边界

- WinSxS 永远不能直接删除文件。组件存储只能通过 Windows 自带任务或 `DISM /Online /Cleanup-Image /StartComponentCleanup` 处理。
- `/ResetBase` 会使现有更新包无法卸载，正式版不得作为普通清理选项；如未来提供，必须归为最高风险、默认隐藏且单独说明不可逆影响。
- 回收站通过 `SHQueryRecycleBin` 获取容量，通过 `SHEmptyRecycleBinW` 清空指定卷；必须由用户明确勾选。
- Storage Sense 和 Cleanup recommendations 作为系统能力参考与引导入口；没有稳定公共执行接口时不得模拟或依赖未文档化调用。
- Restart Manager仅用于识别文件占用者和解释失败。默认不关闭应用或服务；关闭普通应用必须再次获得用户确认，关键服务永不自动关闭。
- Windows Update、DriverStore、Installer、Defender、还原点、休眠和分页文件必须各自使用官方或明确支持的机制，不能通过猜测路径直接删除。

## 8. 权限模型

- GUI 默认以普通用户运行。
- 扫描阶段不提权。
- 计划中只有确需管理员权限的动作才启动 helper。
- helper 接受结构化、版本化、带随机会话标识的动作计划，不接受任意 shell 字符串或任意路径。
- helper 重新执行所有安全校验，不信任 GUI 传来的“已授权”结论。
- helper 返回结构化结果；GUI 不根据标准输出文本猜测是否成功。

## 9. 状态与写入位置

程序目录视为只读。设置、扫描缓存、日志和报告写入 `%LOCALAPPDATA%\CDriveCleaner`：

- `settings.json`
- `cache/scan.db`
- `logs/`
- `reports/`

日志默认对用户名和绝对路径脱敏。用户主动导出诊断包时再次说明包含内容。

## 10. 技术来源

- Microsoft：Clean Up the WinSxS Folder  
  https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/clean-up-the-winsxs-folder?view=windows-11
- Microsoft：SHEmptyRecycleBinW  
  https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shemptyrecyclebinw
- Microsoft：About Restart Manager  
  https://learn.microsoft.com/en-us/windows/win32/rstmgr/about-restart-manager
- Microsoft：Free up drive space in Windows  
  https://support.microsoft.com/en-us/windows/experience/storage-filemanagement/free-up-drive-space-in-windows

