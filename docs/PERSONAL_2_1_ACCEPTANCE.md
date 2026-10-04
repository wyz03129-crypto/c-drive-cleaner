# 2.1.0b1 个人增强版验收

日期：2026-10-04。基线：main 的 02d578f（2.0.0b3）。
目标：个人与朋友离线使用；不是正式发行，也不声称已与所有商业清理软件等效。

## 本次实际完成

- 目录树按展开加载，大文件前 1000 项可按路径、扩展名、风险筛选；显示扫描进度、
  取消后的部分结果、不可读计数和路径。目录汇总改为自底向上合并。
- 重复文件分析：大小分组、首尾采样、完整 SHA-256；硬链接去重、变化检查、取消、
  默认 10 万文件上限。只读，不自动选取或删除副本。
- 21 项规则：19 项可清理、2 项仅分析。增加 Epic webcache；Office/Maven 改为仅分析，
  浏览器离线 CacheStorage 保留；Temp 7 天/普通缓存 1 天保留期。
- 扫描、计划、执行共同检查年龄及文件名；生产执行器再核对代码内规则元数据。
  规则版本升级到 2.0.0，旧版本 finding 不授权。
- 应用运行或进程检测不可用时跳过；Windows 以同一文件句柄复核后删除，拒绝写入占用、
  文件替换、硬链接、异常最终路径、重解析点。Windows 失败不回退到普通路径删除。
- GUI 串行任务、独立取消令牌、关闭保护、失败原因和历史汇总；CLI 补齐专项确认。
- DISM 清理、恢复休眠的独立确认入口；系统工具使用受信系统目录的绝对路径。
- 构建隔离 PATH：验收发现 Poppler 的同名 ICU DLL 被误打包，导致 QtCore 加载失败。
  已修复依赖收集环境，并把打包 EXE 启动检查设为构建成功的必要条件。

## 本地验收证据

环境：Windows 11 10.0.26200 x64、Python 3.12.10、PySide6 Essentials 6.11.2、
PyInstaller 6.22.3。

| 检查 | 结果 |
|---|---|
| Ruff lint / format | 通过 |
| Mypy（src、scripts） | 通过 |
| Pytest | 119 passed，4 skipped |
| 含分支覆盖率 | 86.27%；统计排除 GUI，GUI 另有实际 Qt 测试 |
| 删除入口静态检查 / 版本发布检查 | 通过；不等同于生产认证 |
| Qt 窗口、异步回调线程、取消及手动项选择 | 通过 |
| 中文界面截图 | 快速清理、目录树/筛选、高级优化已检查 |
| PyInstaller 单文件 EXE | 构建成功，`--smoke-test` 自动退出码 0 |
| 真实删除循环 | 测试目录内 20 轮，每轮先模拟再执行、验证目标消失 |
| 10,000 文件目录统计 | 1.038 秒，数量与逻辑大小断言通过 |
| 真实系统规则只读扫描 | 1.328 秒，1,203 个候选文件，1 个读取错误 |

以上时间是单机、单次测试目录样本，不是全 C 盘扫描速度、P95 或性能承诺。
候选包含仅分析项，不代表都能删除。检测到 1 个读取错误，不声称全盘完整覆盖。
跳过项：3 项符号链接创建权限不足，1 项仅非 Windows 适用。真实 Windows junction
越界测试和文件替换/写入占用/硬链接测试已通过。

测试清理限定 `tests/.tmp`。没有在真实 C 盘执行缓存删除、清空回收站、DISM、
关闭休眠或虚拟磁盘压缩。实际系统高级命令只测固定参数、确认、提权、路径解析，未运行。
开发工具自身的构建缓存和临时解包不属于清理器清理量。

## 仍未通过或尚未实施的范围

- 尚无 Windows 10、其他电脑/应用版本、不同 DPI、长时间压力测试矩阵。
- 本地交付是便携包；本机没有进行安装器安装/卸载测试。PR 的 Windows 构建 CI
  已配置一次性 runner 内安装器测试，云端结果应独立查看，不替代实机证据。
- 无隔离区/恢复、文件级持久清理凭证、最小权限 helper、增量索引。
- 未验证对抗恶意管理员的目录竞态；进程名检测不能证明所有应用状态。
- 目录记录随目录数增长；重复文件读取可能很慢；不自动压缩 WSL/Docker，不直接动系统核心目录。
- 未签名；不是商业稳定版。给朋友前先解释永久删除边界。

## 后续优先级

1. 跨盘隔离与恢复事务：空间不足、取消、断电、恢复冲突、过期清理都要测试；
   同盘移动不能冒充释放空间。
2. 每个应用版本独立证据和回归夹具，再扩 QQ/微信、Adobe、游戏启动器规则；
   不把聊天附件/素材/工程文件伪装成缓存。
3. 独立提权 helper、详细但默认私密的操作凭证、低内存索引与扫描性能测量。
4. 先按测量结果定位 Python 瓶颈，必要时把扫描/句柄层做成 Rust/C++ 模块，
   无需现在重写整个 Python/Qt 程序。

参考依据：

- [Microsoft 文件句柄删除 API](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle)
- [Office 文档缓存管理](https://support.microsoft.com/en-us/office/collab-files/delete-your-office-document-cache)
- [Epic 启动器缓存说明](https://www.epicgames.com/help/en-US/c-Category_EpicAccounts/c-TechnicalSupport_GeneralSupport/a000086158)

复现：`scripts/check.ps1`、`python scripts/gui_smoke.py --previews dist/previews`、
`python scripts/personal_acceptance.py --files 10000 --read-only-system-scan`、
`scripts/build_exe.ps1`。最后一个命令包含冻结 EXE 的只读启动测试。
