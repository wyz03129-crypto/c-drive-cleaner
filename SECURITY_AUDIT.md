# C Drive Safe Cleaner v1.0.0 — Security Audit

审计日期：2026-09-14  
审计范围：`src/`、`config.json`、启动脚本、打包脚本、测试与发布边界。  
结论：在记录的限制条件下通过；未对真实 C 盘执行删除。

## 攻击面复核

1. **路径穿越：通过。** 只接受绝对路径，并同时验证 lexical 与 canonical 严格
   containment；前缀相似兄弟目录测试通过。
2. **symlink 逃逸：通过。** 扫描不跟随；删除检查真实路径和完整组件链。无创建
   权限环境使用 mock 路径链测试，另有实际 junction 测试。
3. **junction 逃逸：通过。** Windows `mklink /J` 模拟夹具验证拒绝跨范围目标。
4. **reparse point：通过。** 检查 `FILE_ATTRIBUTE_REPARSE_POINT` 和
   `os.path.isjunction`；属性无法读取时按危险处理。
5. **环境变量污染：通过。** 生产规则用 Windows Shell/Kernel API 获取 Windows、
   Profile、LocalAppData、Roaming 与 ProgramData；TEMP 还必须位于可信用户目录且
   末级为 Temp/Tmp。测试注入接口只用于 E 盘模拟环境。
6. **错误用户名/中文路径：通过。** 路径从系统 API 获取并全程使用 Unicode；中文
   文件名清理测试通过。
7. **Windows 路径大小写：通过。** 比较使用 `normcase`。
8. **8.3 短路径：通过（存在路径）。** 规范化时调用 `GetLongPathNameW`，随后再次
   canonical/denylist 检查。不存在目标一律拒绝。
9. **UNC/扩展路径：通过。** 网络与 `\\` 前缀路径保守拒绝。
10. **黑名单绕过：通过。** 原路径和真实路径均检查；deny 优先于 allow，有专门
    不变量测试。
11. **白名单过宽：已收窄。** 白名单只由代码规则生成，不允许配置追加。浏览器只
    授权缓存子目录；WPS 只有最窄 cache，其他目录降为 MANUAL。
12. **递归删除：通过。** 源码没有 `shutil.rmtree`；唯一 `os.remove` 位于 guard，
    逐文件失败隔离。不尝试删除目录。
13. **TOCTOU：风险降低、不能完全消除。** 扫描记录 file identity，授权时与调用
    删除前各复核一次，且重新检查路径链。Python 标准库没有本项目可用的完全无竞
    态 Windows delete-by-handle；仍建议不要与不可信的并发目录修改者同时运行。
14. **config 篡改：通过。** 只接受固定显示/扫描键；任意 allow_paths 和 risk
    override 被忽略。启用列表只能从内置规则做减法。
15. **浏览器数据误删：通过。** Profile 不作为范围；Bookmarks、History、Cookies、
    Login Data、Web Data、Local State、Extensions、Preferences 受保护。
16. **WPS 数据误删：通过。** backup/recovery/cloud 路径和文档扩展受保护；官方未
    明确的临时/日志/崩溃目录全部 MANUAL。
17. **Office 数据误删：通过。** OfficeFileCache 标记 MANUAL，不进入候选。
18. **Windows 系统文件误删：通过。** 核心系统/安装/恢复/启动路径为 denylist；
    Update、Windows.old 和回收站均报告-only。
19. **管理员运行扩大风险：已控制。** 不自动提权、不改 ACL；即使用户手动以管理
    员运行，路径与风险检查不放宽。
20. **异常处理：通过。** 权限、占用、不存在、路径/类型和一般 OS 错误按文件跳过
    并继续；模拟 PermissionError/OSError 测试通过。

## 审计中发现并修复

- **AUD-001 / High：** Windows `DirEntry.stat()` 与 `os.stat()` 的 identity 字段
  不一致，导致所有删除被误拒绝。扫描改用与复核一致的 `os.stat()`；回归通过。
- **AUD-002 / High：** 单靠环境变量构建白名单可能被污染。生产路径切换到 Windows
  API，TEMP 增加可信父目录与名称约束。
- **AUD-003 / Medium：** 对每个文件枚举父目录检查项目标志会造成平方级耗时。
  改为固定 marker 定点检查，并在扫描阶段跳过项目目录。
- **AUD-004 / Medium：** 所有 TEMP 文件均可能候选，过于激进。用户/Windows Temp
  加入硬编码 7 天最小修改年龄，WPS cache 加入 1 天。
- **AUD-005 / Medium：** WPS 多个目录缺少跨版本官方语义保证。只保留最窄 cache
  为 SAFE，其余降为 MANUAL，并保护备份/恢复/云/文档。
- **AUD-006 / Low：** 发布脚本递归重建 release 前缺少范围断言。现验证规范化路径
  必须是项目下名为 release 的确切目录。

## 静态检查结论

- 生产源码中 `os.remove`：1 处，仅 `src/safety.py`。
- `shutil.rmtree`、`os.system`、`shell=True`、takeown、icacls、taskkill：0 处。
- 网络库导入、遥测、服务、注册表持久化、计划任务：0 处。
- 运行时第三方依赖：0。

## 剩余限制

- 自定义 Chrome/Edge UserDataDir 不主动发现，以漏扫换安全。
- 应用版本可能改变缓存布局；未知布局不会自动纳入。
- 被占用/无权限/重解析/身份变化的候选会减少实际释放空间。
- 未代码签名的 PyInstaller EXE 可能触发信誉提示；不提供任何规避方法。
