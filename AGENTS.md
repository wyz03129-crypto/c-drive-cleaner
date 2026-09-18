# C Drive Cleaner agent guide

## Goal

Build a deep, safe, explainable, and verifiable Windows system-drive analyzer and
cleaner. A larger scan number is never a reason to weaken the safety boundary.

## Architecture

`RuleRegistry -> FastScanner -> CleanupPlanner -> SafetyPolicy -> Executor -> CleanupReceipt`

Storage analysis is read-only and separate from cleanup authorization. Large paths
may produce advice, but size alone never grants delete permission.

## Safety invariants

- Only modules in `src/cdrive_cleaner/executors` may mutate the filesystem.
- A scan finding is not authorization. Revalidate path, scope, reparse state, file
  identity, and risk immediately before deletion.
- Never directly delete Windows core directories, WinSxS, Installer, pagefile,
  hiberfil, restore points, shadow copies, virtual disks, user documents, downloads,
  desktops, browser profiles, cookies, credentials, projects, or unknown AppData.
- SYSTEM actions must use fixed, code-owned Windows API/command invocations.
- SAFE may be preselected. CAUTION needs a clear impact statement; unusually large
  application-managed caches require dedicated confirmation. MANUAL and SYSTEM are
  never ordinary direct-delete rules.
- GUI cleanup is real cleanup after confirmation. Dry Run belongs to CLI/tests.
- Do not add telemetry, network upload, email, credentials, or secrets.

## Engineering standards

- Python 3.12, typed code, immutable domain records, `pathlib`, no `shell=True`.
- Keep UI work off the worker thread and filesystem work off the UI thread.
- Cancellation is cooperative and only observed between atomic operations.
- Preserve backward compatibility while the project remains beta when practical.
- Use system-drive and Known Folder discovery; do not assume `C:\` or English paths.

## Required checks

```powershell
ruff check .
ruff format --check .
mypy src scripts
pytest
python scripts/check_mutation_gate.py
python scripts/release_gate.py
```

Windows release candidates also require GUI smoke, PyInstaller build, installer
install/uninstall smoke, checksums, and real Windows 10/11 validation. Never label a
release stable while signing or real-machine evidence is missing.

## Definition of done

Changes must have focused tests, preserve the mutation gateway, document user-visible
behavior and limitations, and report exact pass/fail/skip evidence. Cloud-only checks
must be labeled separately from real Windows validation.
