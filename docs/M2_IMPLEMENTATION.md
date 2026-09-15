# M2 快速清理 MVP 实施记录

## 已交付

- 有界线程池与流式 `os.scandir` 快速扫描器；
- 协作式取消、部分结果、脱敏错误码和进度回调；
- 16 组代码内置、版本化缓存规则；
- Chrome、Edge 与 Firefox 仅扫描明确缓存子目录，不扫描浏览器资料根；
- 用户/Windows Temp、shader、缩略图、崩溃转储、开发工具及 Office/WPS 缓存规则；
- 从 Finding 到 ActionPlan、执行时重新授权、结果收据的完整闭环；
- 预计字节、成功处理字节、磁盘可用空间观测变化分开统计；
- CLI 默认 Dry Run，真实执行要求规则选择、`--execute` 和精确确认词；
- 管理员动作未处于提权上下文时主动拒绝；
- 回收站使用 `SHQueryRecycleBinW` / `SHEmptyRecycleBinW`，并采用独立确认词。

## 安全边界

- 扫描不跟随 symlink、junction 或其他 reparse point；
- 规则根只能由 Windows Known Folder API 结果构造，环境变量不能扩权；
- Firefox 只把每个 profile 下的 `cache2`、`startupCache` 作为根；
- 缩略图规则只匹配 `thumbcache_*.db` 和 `iconcache_*.db`；
- 普通清理不会清空回收站；
- 执行前再次验证路径、卷、文件类型、身份、denylist 和项目标志。

## 尚未宣称完成

- P95 扫描时间和 300 MB 内存目标需要固定 Windows 硬件及公开 50 万文件夹具；
- GUI、后台任务交互和一秒取消体验属于 M5；
- 被占用文件只返回跳过结果，Restart Manager 诊断属于 M4；
- 当前只删除文件，不递归暴力删除目录；空缓存目录会保留；
- WPS/Office 规则需要继续在更多正式版本上做兼容性实机验证。

因此，M2 是可测试的 CLI MVP，不是正式面向普通用户发布的 EXE。
