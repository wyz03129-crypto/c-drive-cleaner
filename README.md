# C Drive Cleaner

C Drive Cleaner 是一个面向普通 Windows 用户的 C 盘空间分析与安全清理项目。

当前开发版本是 **2.2.0 beta 1（可恢复清理测试版，未签名）**。v1.1 迁移已经完成，仓库只保留 v2
生产源码；正式稳定版仍需代码签名以及更多 Windows 10/11 真实机器验收。

## 项目目标

2.1 优先面向个人和朋友离线使用：目录树逐层展开、大文件路径/扩展名/风险筛选、
重复文件完整内容比对、应用运行检测、句柄级文件删除和清理失败解释。
无需会员。2.2 默认选择“备份后清理”：需手动选择另一磁盘卷的私人隔离目录，
校验备份后才删除原文件；可在“隔离与恢复”页恢复，且不覆盖已有文件。
另保留永久清理模式，其删除不可撤销。需要管理员的类别暂不支持可恢复模式。

个人版使用说明：`docs/PERSONAL_QUICKSTART.md`。
本次实机证据和未验证范围：`docs/PERSONAL_2_2_ACCEPTANCE.md`。
2.1 历史验收记录保留在 `docs/PERSONAL_2_1_ACCEPTANCE.md`。

- 快速解释 C 盘空间被哪些目录、文件和应用占用；
- 区分 SAFE、CAUTION、MANUAL、SYSTEM 和内部 PROTECTED 禁止区；
- 尽可能使用 Windows 或应用提供的正式清理机制；
- 对每次清理分别展示估算空间、成功处理空间和实际可用空间变化；
- 保持离线、无遥测，并默认以普通用户权限运行。

## 当前状态

| 模块 | 状态 |
|---|---|
| v2 架构与安全模型 | 已建立 |
| 正式包和 CLI 骨架 | 已完成 |
| 自动测试与 Windows CI | 已完成 |
| 安全内核 v2 | M1 已完成 |
| 快速扫描与 21 项规则（19 项可清理、2 项仅分析） | 2.1 Beta |
| 目录树、大文件筛选、重复文件分析 | 2.1 Beta |
| Windows 高级空间优化 | DISM / 休眠 / 回收站独立确认 |
| GUI、EXE 和安装包 | 未签名测试版 |
| 跨卷备份后清理、恢复与备份清除 | 2.2 Beta；详细限制见使用说明 |

## 安全模型

| 等级 | 行为 |
|---|---|
| SAFE | 经过验证的临时文件或可重建缓存，可默认勾选 |
| CAUTION | 可重建但可能影响首次启动、离线内容或应用状态；显示影响并确认 |
| MANUAL | 只分析和建议，例如下载、桌面、大型应用和开发环境 |
| SYSTEM | 只通过 Windows 官方 API、设置或固定命令处理 |
| PROTECTED | 内部拒绝区，任何普通规则均不能直接删除 |

程序不会因为目录很大就自动删除。浏览器规则不包含密码、书签、Cookie、历史记录或
完整 Profile；WPS/Office 规则不包含用户文档；未知 AppData 仅分析。

## 当前清理覆盖

- 用户和 Windows 临时文件、缩略图、DirectX 着色器、崩溃转储、WER 归档；
- Chrome、Edge、Firefox 的明确缓存子目录；
- pip、npm、NuGet、Gradle 可重建缓存；Maven 本地仓库只分析；
- WPS、百度网盘加速缓存；Office 文档缓存只分析，避免丢失未上传文档；
- VS Code、Discord、经典 Teams 的明确缓存子目录；
- Epic Games 启动器官方列出的 webcache 目录，不包含游戏与存档；
- 使用 Windows Shell API 独立查询/清空回收站；
- 只读分析系统盘目录和达到 100 MB / 500 MB / 1 GB / 5 GB 阈值的大文件；
- 分析 hiberfil、pagefile、swapfile、Docker/WSL 虚拟磁盘，并通过固定的 `powercfg`
  或 `DISM` 操作处理受支持项目。

不直接清理：WinSxS、Windows Installer、System32、未知 AppData、Downloads、Desktop、
用户文档、QQ/微信聊天记录、虚拟磁盘、恢复点或卷影副本。

Temp 保留最近 7 天，普通缓存保留最近 1 天。CAUTION 默认不勾选；已知相关应用运行时
跳过对应清理，进程检测失败也跳过。浏览器离线站点 `Service Worker/CacheStorage`
保留。Windows 删除使用同一句柄复核卷、文件 ID、大小、修改时间、最终路径和链接数；
遇到写入占用、身份变化或硬链接不会退回路径删除。

重复文件页由用户选择目录，默认比较 ≥ 1 MB 文件，最多检查 10 万文件；先比大小、
首尾采样，再比完整 SHA-256。硬链接不计作重复；仅分析，不自动选择或删除副本。
大文件表筛选当前扫描中达到阈值的前 1000 项，目录树按展开加载。

## 桌面版

```powershell
python -m pip install -e ".[gui]"
c-drive-cleaner-gui
```

本地构建单文件 EXE 和安装包（需要 Inno Setup 6）：

```powershell
python -m pip install -e ".[dev,packaging]"
.\scripts\build_installer.ps1
```

输出包括便携版 `CDriveCleaner.exe`、带卸载功能的安装包以及各自的 SHA-256 校验文件。
GitHub Actions 的 `Build Windows EXE` 工作流也会生成可下载的未签名构建产物。

## 开发检查

Windows PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
ruff check .
mypy
pytest
python scripts/check_mutation_gate.py
python scripts/release_gate.py
```

也可以运行：

```powershell
.\scripts\check.ps1
```

## 命令行工具

```powershell
python -m cdrive_cleaner --version
python -m cdrive_cleaner status
python -m cdrive_cleaner scan
python -m cdrive_cleaner analyze --top 20 --large-file-mb 500
python -m cdrive_cleaner analyze --cached
python -m cdrive_cleaner clean --rule user_temp
python -m cdrive_cleaner clean --rule user_temp --execute --confirm CLEAN
python -m cdrive_cleaner clean --rule baidu_accelerate_cache --execute --confirm CLEAN --confirm-rule "baidu_accelerate_cache=清理百度缓存"
python -m cdrive_cleaner recycle-bin
python -m cdrive_cleaner recycle-bin --empty --confirm "EMPTY RECYCLE BIN"
python -m cdrive_cleaner advanced inspect
python -m cdrive_cleaner advanced run analyze_component_store
python -m cdrive_cleaner advanced run clean_component_store --confirm "CLEAN COMPONENT STORE"
```

`clean` 默认是 Dry Run。真实清理必须明确列出规则、增加 `--execute`，并精确输入
`--confirm CLEAN`。需要管理员权限的规则在未提权时会被主动拒绝。回收站使用独立确认，
不会混入普通缓存清理。

GUI 不默认模拟：点击“开始扫描”始终只读预览；选择项目并确认“清理”后会执行真实清理。
CLI 的 `clean` 默认 Dry Run 是给开发、自动化和诊断使用的保护措施。

## 管理员权限与休眠

普通缓存以当前用户权限清理。Windows Temp、DISM 和 `powercfg` 等操作会明确请求管理员
权限；拒绝后其他功能仍可使用。关闭休眠可能立即释放 `hiberfil.sys` 的大小，但会禁用
休眠并可能禁用快速启动；它默认不执行，可用 `powercfg /hibernate on` 恢复。

## 隐私、日志和故障排查

应用离线运行、无遥测、无邮件功能，不上传文件路径或扫描结果。清理历史只保存汇总数字；
诊断包默认不含用户名和路径。被占用、权限不足、身份变化或重解析点目标会被跳过。若分析
覆盖率不足，应以管理员身份重试并查看结果中的不可读数量。详见 `PRIVACY.md`、
`SECURITY.md` 和 `KNOWN_LIMITATIONS.md`。

## 设计文档

- `docs/ARCHITECTURE_V2.md`
- `docs/SAFETY_MODEL_V2.md`
- `docs/ROADMAP_AND_ACCEPTANCE.md`
- `docs/M1_IMPLEMENTATION.md`
- `docs/M2_IMPLEMENTATION.md`
- `docs/M3_IMPLEMENTATION.md`
- `docs/M4_IMPLEMENTATION.md`
- `docs/M5_IMPLEMENTATION.md`

## 安全声明

当前仍是未签名个人 Beta，尚未证明在全部应用版本上兼容。CLI 保留 Dry Run 供自动化与技术复核；GUI
采用“扫描 → 选择 → 一次确认 → 真实清理 → 验证”的流程。
