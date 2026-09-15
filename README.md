# C Drive Cleaner

C Drive Cleaner 是一个面向普通 Windows 用户的 C 盘空间分析与安全清理项目。

当前分支处于 **v2.0.0-alpha 工程重构阶段**。现有 v1.1 源码保留用于迁移和行为对照，不能视为正式发行版本，也不建议直接用于重要电脑的深度清理。

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
| 深度空间分析 | 尚未实现 |
| 正式 GUI 和 EXE | 尚未实现 |

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

## 运行 M2 CLI

```powershell
python -m cdrive_cleaner --version
python -m cdrive_cleaner status
python -m cdrive_cleaner scan
python -m cdrive_cleaner clean --rule user_temp
python -m cdrive_cleaner clean --rule user_temp --execute --confirm CLEAN
python -m cdrive_cleaner recycle-bin
python -m cdrive_cleaner recycle-bin --empty --confirm "EMPTY RECYCLE BIN"
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

## 安全声明

M2 是供测试的 CLI MVP，并非正式发布版。请先运行 Dry Run 并核对规则。旧版入口仍位于
`src/main.py`，仅用于迁移对照，不属于新包的命令入口。
