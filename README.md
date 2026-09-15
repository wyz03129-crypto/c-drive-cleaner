# C Drive Cleaner

C Drive Cleaner 是一个面向普通 Windows 用户的 C 盘空间分析与安全清理项目。

当前里程碑是 **M5 未签名 Beta 候选版**。现有 v1.1 源码只用于迁移和行为对照；正式发布前仍需代码签名及真实 Windows 10/11 环境验收。

## 项目目标

- 快速解释 C 盘空间被哪些目录、文件和应用占用；
- 区分安全缓存、建议清理、人工复核、高级操作和禁止删除；
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
| 快速扫描与首批清理规则 | M2 CLI MVP |
| 深度空间分析 | M3 CLI MVP |
| Windows 高级空间优化 | M4 CLI MVP |
| 正式 GUI 和 EXE | M5 Beta 候选版 |

## 桌面版

```powershell
python -m pip install -e ".[gui]"
c-drive-cleaner-gui
```

本地构建单文件 EXE：

```powershell
python -m pip install -e ".[dev,packaging]"
.\scripts\build_exe.ps1
```

输出为 `dist/CDriveCleaner.exe` 和 SHA-256 校验文件。GitHub Actions 的
`Build Windows EXE` 工作流也会生成可下载的未签名构建产物。

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
python -m cdrive_cleaner analyze --top 20
python -m cdrive_cleaner analyze --cached
python -m cdrive_cleaner clean --rule user_temp
python -m cdrive_cleaner clean --rule user_temp --execute --confirm CLEAN
python -m cdrive_cleaner recycle-bin
python -m cdrive_cleaner recycle-bin --empty --confirm "EMPTY RECYCLE BIN"
python -m cdrive_cleaner advanced inspect
python -m cdrive_cleaner advanced run analyze_component_store
python -m cdrive_cleaner advanced run clean_component_store --confirm "CLEAN COMPONENT STORE"
```

`clean` 默认是 Dry Run。真实清理必须明确列出规则、增加 `--execute`，并精确输入
`--confirm CLEAN`。需要管理员权限的规则在未提权时会被主动拒绝。回收站使用独立确认，
不会混入普通缓存清理。

## 设计文档

- `docs/ARCHITECTURE_V2.md`
- `docs/SAFETY_MODEL_V2.md`
- `docs/ROADMAP_AND_ACCEPTANCE.md`
- `docs/LEGACY_MIGRATION.md`
- `docs/M1_IMPLEMENTATION.md`
- `docs/M2_IMPLEMENTATION.md`
- `docs/M3_IMPLEMENTATION.md`
- `docs/M4_IMPLEMENTATION.md`
- `docs/M5_IMPLEMENTATION.md`

## 安全声明

M5 仍是未签名 Beta 候选版，并非正式发布版。CLI 保留 Dry Run 供自动化与技术复核；GUI
采用“扫描 → 选择 → 一次确认 → 真实清理 → 验证”的流程。旧版入口仍位于 `src/main.py`，
仅用于迁移对照，不属于新包入口。
