# C Drive Cleaner 2.2 可恢复清理测试版

解压后双击 `CDriveCleaner.exe`，不需要安装 Python，不需要账号或会员。
首次启动需要解包运行库，可能稍慢。本包未签名，请只使用自己构建或可信来源的文件；
不要为运行本程序关闭杀毒软件。可用同目录 SHA-256 文件核对下载完整性。

## 怎么使用

1. 先到“空间分析”查看系统盘目录树和大文件。点击目录或文件可查看完整路径及建议。
2. 到“快速清理”点“开始扫描”。扫描不删除文件。
3. 默认是“备份后清理”。先在“隔离与恢复”页选择另一磁盘卷的私人文件夹，再勾选类别。
   同盘不会释放空间，程序会拒绝；需要管理员的类别先取消勾选。
4. 完全退出相关应用，阅读说明并确认后执行真实清理。备份校验成功才删除原文件。
   可在隔离页选中记录恢复，不会覆盖已存在的文件。CAUTION 项默认不勾选。
5. 结果区区分预计大小、已处理大小、可用空间变化及失败原因。失败后处理原因并重新扫描。

Temp 保留最近 7 天，普通缓存保留最近 1 天。正在写入、权限不足、身份变化、硬链接、
重解析点等项目跳过。不自动关闭应用，不删除聊天记录、文档、下载或未知 AppData。

“重复文件”仅比较所选文件夹中的内容，不删除副本。不同路径下的相同文件可能各自有用。
“高级优化”里的清理组件存储、关闭/恢复休眠和清空回收站分别确认；不是一键清理的一部分。
不要在 DISM 执行期间强制结束进程。拒绝 UAC 不会授权操作。

也可以明确切换“永久清理（不可恢复）”，该模式和清空回收站均不能用隔离区撤销。
恢复后备份仍保留；确认应用正常后，可在隔离页单独永久删除所选备份。默认配额 10 GB，
无自动过期删除；取消/失败的残留会标注未完成，不会自动恢复。

隔离内容未加密，不要放在共享/云同步目录。恢复清单绑定 Windows 当前用户，换机器、
重装系统或账号变化可能无法使用。只恢复缓存内容与修改时间，不是完整系统备份。

## 保存什么、不会做什么

- 无联网、无遥测、无广告、无会员校验。
- 清理历史保存在当前用户 `.c-drive-cleaner` 目录，仅存汇总和错误类别。
- 无自动更新、定时自动删除，不自动优化 Docker/WSL 虚拟磁盘。
- Office 文档缓存和 Maven 本地仓库仅分析，避免损坏待上传文档或本地构建产物。
- 只在本次验收所述 Windows 11 x64 环境完成实机验证，不能据此保证所有应用版本兼容。

完整源代码附在 `source/`，不含本机账号、扫描路径、虚拟环境或 Git 凭据。
详细验收见 `PERSONAL_2_2_ACCEPTANCE.md`；第三方许可及源码地址见 `THIRD_PARTY_NOTICES.md`。

CLI 示例（E 盘文件夹须已存在，示例不会自动执行）：

```powershell
python -m cdrive_cleaner recovery init --root E:\Private\CDriveCleaner-Quarantine --confirm "INIT BACKUP"
python -m cdrive_cleaner clean --rule user_temp --quarantine E:\Private\CDriveCleaner-Quarantine --execute --confirm CLEAN
python -m cdrive_cleaner recovery list --root E:\Private\CDriveCleaner-Quarantine
python -m cdrive_cleaner recovery restore --root E:\Private\CDriveCleaner-Quarantine --id 备份编号 --confirm RESTORE
```
