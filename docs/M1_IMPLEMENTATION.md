# M1 安全内核实现记录

## 已实现

- `SHGetKnownFolderPath` 和 `GetWindowsDirectoryW` 可信目录发现；
- 相对路径、UNC、设备命名空间和 GLOBALROOT 拒绝；
- 绝对路径与 canonical path 双重范围检查；
- 卷边界、denylist、受保护名称和项目目录检查；
- symlink、junction、mount/reparse point 路径链拒绝；
- 扫描身份与执行前身份复核；
- 版本化、只读 Rule Registry；
- 不可变 Finding、PlannedAction 和 ActionPlan；
- CleanupPlanner 严格匹配规则 ID、版本、风险、动作类型和授权根；
- DirectFileDeleteExecutor 执行时重新授权；
- 默认脱敏的 JSON Lines 审计日志；
- 静态门禁确保删除调用只能位于批准的 executor 网关。

## 用户入口状态

M1 不向 GUI 或 CLI 暴露文件扫描和真实清理。真实删除只在 pytest 创建的临时目录中验证。正式缓存规则、扫描器和用户清理闭环属于 M2。

## 已知残余风险

- Python 路径删除仍无法完全消除最后一次身份校验与删除调用之间的 TOCTOU；后续 Windows 实机安全评估决定是否增加句柄级原生 helper。
- Windows Known Folder 和 junction 测试需要 GitHub Windows runner 或 Windows 实机验证。
- 规则注册表当前只提供机制，没有注册生产清理规则。
- 管理员 helper、Windows API 和官方命令执行器仅有动作类型边界，尚未实现。

## M1 完成门槛

- Ruff、格式和 mypy strict 通过；
- 单元、安全和 Windows 条件测试通过；
- 新安全内核覆盖率不低于 80%；
- mutation gate 通过；
- 构建成功；
- GitHub Windows CI 成功。
