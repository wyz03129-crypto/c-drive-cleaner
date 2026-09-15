# M4 Windows 高级空间优化实施记录

## 已交付

- 休眠文件、分页文件、交换文件、Docker VHDX 和 WSL `ext4.vhdx` 的只读检查；
- DISM 组件存储分析；
- DISM `StartComponentCleanup` 官方清理入口；
- 使用 `powercfg /hibernate off|on` 管理休眠文件；
- 使用 `vssadmin list shadows /for=C:` 只读列出卷影副本；
- 打开 Windows Storage Sense 设置的官方系统入口；
- 所有命令均为代码内置参数数组，使用 `shell=False`，不接受任意命令或路径；
- 所有变更动作要求管理员上下文和动作专属确认词；
- 命令返回结构化退出码、stdout 和 stderr。

## 明确禁止

- 不提供 DISM `/ResetBase`；
- 不直接删除 WinSxS、DriverStore、Installer 或 Windows Update 目录；
- 不自动删除还原点或卷影副本；
- 不直接删除或在线压缩 Docker/WSL 虚拟磁盘；
- 不自动关闭 WSL、Docker、应用或系统服务；
- 不接收 UI 拼接的 shell 字符串。

## 命令示例

```powershell
python -m cdrive_cleaner advanced inspect
python -m cdrive_cleaner advanced run analyze_component_store
python -m cdrive_cleaner advanced run list_shadows
python -m cdrive_cleaner advanced run open_storage_settings
python -m cdrive_cleaner advanced run clean_component_store --confirm "CLEAN COMPONENT STORE"
python -m cdrive_cleaner advanced run disable_hibernation --confirm "DISABLE HIBERNATION"
python -m cdrive_cleaner advanced run enable_hibernation --confirm "ENABLE HIBERNATION"
```

变更操作必须从已提升权限的终端运行。当前版本不会自行绕过 UAC。

## 官方依据

- Microsoft DISM：<https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/clean-up-the-winsxs-folder?view=windows-11>
- Microsoft powercfg：<https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/powercfg-command-line-options>
- Microsoft VSSAdmin：<https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/vssadmin>
- Microsoft WSL 磁盘空间：<https://learn.microsoft.com/en-us/windows/wsl/disk-space>
- Microsoft compact vdisk：<https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/compact-vdisk>

## 尚未宣称完成

- 暂不自动压缩 WSL/Docker VHDX，因为必须处理关机、挂载状态及版本差异；
- 暂不删除还原点，避免破坏用户恢复能力；
- Windows Update 和 Delivery Optimization 使用系统设置入口，不猜测内部缓存路径；
- 独立最小权限 UAC helper 和图形化影响说明将在 M5 完成。

M4 提供受控的高级 CLI，不代表可以无判断地执行所有建议。
