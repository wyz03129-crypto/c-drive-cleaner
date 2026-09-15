# 安全说明

## 永久原则

安全优先级高于清理效果。`DENYLIST` 永远高于 `ALLOWLIST`；未知、大型、无法
确认或非普通文件统一拒绝自动处理。真实清理只允许 `SAFE` 规则。

## 明确不会做的事

- 不删除整个 `SoftwareDistribution`，不停止 Windows Update 服务。
- 不由 Python 删除 Windows.old，不清空回收站。
- 不删除 Program Files、Windows 核心组件、恢复区、启动区或 WindowsApps。
- 不删除用户库、OneDrive、源码/Git 仓库、虚拟环境、node_modules 或数据库。
- 不删除浏览器书签、历史、Cookie、登录信息、扩展或偏好设置。
- 不删除 WPS 备份、恢复文件、云文档、用户文档或历史版本。
- 不强制关闭浏览器/WPS/Office，不自动 UAC 提权，不使用 takeown/icacls。
- 不联网、不遥测、不上传，不安装服务、驱动、计划任务或启动项。

## 删除前检查

每个文件均在唯一的 `SafetyGuard` 入口重新执行：原始路径、环境变量/用户目录
展开、绝对路径、8.3 长路径、realpath、白名单范围、保护列表、用户数据名称、
源码/数据库保护、symlink、junction、reparse point、普通文件类型和扫描身份
复核。任何一步失败就跳过并继续其他文件。

## 用户确认

启动程序不会删除。真实清理至少需要：选择清理功能、查看项目/文件数/空间，
最后输入完全一致的大写 `CLEAN`。输入其他内容即取消。

## Dry Run

Dry Run 走相同的授权路径，但在唯一删除调用之前返回 `SIMULATED_DELETE`。
自动化测试还会监视删除 API，保证没有被调用。Dry Run 的真实删除数量必须为 0。

## Windows 安全软件提示

未签名的个人 PyInstaller 程序可能触发 SmartScreen 或杀毒软件的信誉提示。
发布包提供 SHA256 供核对。不要关闭 Defender，不要绕过 SmartScreen；无法确认
来源或哈希时不要运行。
