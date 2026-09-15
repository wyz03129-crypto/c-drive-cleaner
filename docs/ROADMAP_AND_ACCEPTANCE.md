# C Drive Cleaner v2 路线与验收标准

## 总原则

每个里程碑必须先有自动测试，再合并到 `main`。没有 Windows 实机证据的能力不得标记为“已支持”。

## M0：工程骨架

交付：

- `pyproject.toml`、包结构、CLI 入口、统一错误模型；
- pytest、ruff、类型检查和覆盖率；
- Windows GitHub Actions；
- 开发/测试/打包说明；
- 旧版代码保留在兼容层或迁移说明中，不静默丢失规则。

验收：

- Windows CI 全绿；
- 单元测试不接触真实 C 盘；
- Dry Run 测试能证明没有调用变更 API；
- 仓库版本、文档和生成报告版本一致。

## M1：安全内核 v2

交付：

- Windows Known Folder 和系统目录发现；
- 路径规范化、卷边界、reparse point、文件身份和 denylist；
- 版本化 Rule Registry；
- CleanupPlanner 和四类执行器接口；
- 脱敏审计日志。

安全测试矩阵：

- 绝对/相对路径、前缀相似目录、大小写、Unicode；
- UNC、`\\?\`、8.3 路径、长路径；
- symlink、junction、mount/reparse point；
- 扫描后替换文件、替换父目录、权限变化；
- 受保护扩展、项目标志、数据库和浏览器凭据；
- 配置注入、规则篡改、非 SAFE 风险调用；
- 管理员与普通用户行为一致性。

验收：

- 所有安全不变量有自动测试；
- deny 用例误删除数为 0；
- 生产代码不存在绕过安全层的直接删除调用；
- 真实变更只能从显式 ActionPlan 到达执行器。

## M2：快速清理 MVP

首批范围：

- 用户和 Windows Temp；
- Chrome、Edge、Firefox 可再生缓存；
- 缩略图和 DirectX/GPU shader cache；
- crash dump 和错误报告的安全子集；
- pip、npm、NuGet、Gradle/Maven 等可重建缓存；
- WPS/Office 经版本验证的纯缓存子集；
- 回收站查询与独立确认清空。

验收：

- 首次可见结果目标 ≤ 2 秒；
- 参考 SSD、50 万文件夹具下快速扫描 P95 ≤ 15 秒；
- 扫描期间 UI 可操作，取消响应目标 ≤ 1 秒；
- 峰值内存目标 ≤ 300 MB；
- 每类规则都有正例、反例、版本变化和占用文件测试；
- 预计、处理和观测释放量分开显示。

性能目标需在固定硬件与公开夹具上记录，不能用开发机单次结果宣称达标。

## M3：空间分析器

交付：

- C 盘目录树和逐层钻取；
- top-N 大目录、大文件；
- Users、AppData、ProgramData、Windows、应用数据分类；
- 错误覆盖率与统计置信度；
- 增量扫描缓存；
- “为什么 C 盘还是满”诊断页。

验收：

- 100 万文件参考夹具深度扫描 P95 目标 ≤ 90 秒；
- 可取消、可返回部分结果；
- reparse/hard-link 夹具不循环、不明显重复计量；
- 无权限区域明确显示统计不完整；
- 大目录发现不产生任何删除授权。

## M4：Windows 高级执行器

按风险逐项实现：

- DISM `StartComponentCleanup`；
- Windows.old 官方清理引导；
- Windows Update 和 Delivery Optimization 官方机制；
- 休眠文件、还原点、Docker/WSL 的专项分析与官方操作入口；
- Restart Manager 占用诊断。

验收：

- 每项均有微软或应用厂商文档依据；
- 管理员 helper 只接受允许的结构化动作；
- UAC 取消、命令失败、重启需求均能恢复到一致状态；
- 不使用 `/ResetBase` 作为普通选项；
- 不直接删除 WinSxS、DriverStore、Installer 或系统保护目录。

## M5：正式 GUI 与发行

交付：

- 面向普通用户的主页、快速清理、空间分析、高级优化和历史结果；
- Windows EXE/安装包；
- SHA-256 校验文件；
- 自动更新方案在单独安全审计通过前保持关闭；
- 崩溃恢复和诊断包导出；
- Windows 10/11 实机测试报告。

发布门禁：

- 单元、契约、安全和 Windows 集成测试全绿；
- 关键模块覆盖率 ≥ 90%，总体覆盖率 ≥ 80%；
- 误删除安全测试为 0；
- 连续 20 次清理压力测试无崩溃、死锁和越权；
- 真实 Windows 快照/虚拟机回滚验证通过；
- 文档不再声称不存在的测试、脚本或能力；
- 未签名版本明确标识测试版，不诱导用户绕过 SmartScreen。

## 版本推进顺序

```text
M0 工程骨架
→ M1 安全内核
→ M2 快速清理 MVP
→ M3 空间分析
→ M4 高级 Windows 清理
→ M5 GUI 与正式发行
```

不允许先做漂亮 GUI，再补安全内核和测试。

