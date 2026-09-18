# C Drive Safe Cleaner Development Report — 2.0.0 beta 3

## 1. Baseline

Audited the repository implementation rather than relying on README claims. The beta 2
baseline had a real GUI cleaner, a deny-first execution policy, reparse and identity
checks, whole-volume read-only analysis, DISM/powercfg integration, PyInstaller/Inno
Setup packaging, Windows CI, and release workflows. It had 17 direct-file rules.

Baseline command evidence in the Codex Linux environment:

- `pytest -q`: 77 passed, 1 Windows-only test skipped, 84.99% coverage.
- `ruff check .` and `ruff format --check .`: passed.
- `mypy src scripts`: passed.
- `python scripts/check_mutation_gate.py`: passed.
- `python scripts/release_gate.py`: passed for 2.0.0b2.

No SMTP/email implementation or credentials exist. The requested “email P0” item is
not applicable; adding an unrelated email subsystem would expand privacy and security
risk without helping disk cleanup.

## 2. Root causes of the earlier 1.7 GB result

The 1.7 GB result was not a fake-clean or Dry Run bug. GUI cleanup used
`dry_run=False`. The primary constraints were:

- a narrow rule catalog that deliberately recognized only well-known cache roots;
- large application data appearing only in analysis, because directory size is not
  deletion authorization;
- administrator-only system locations being skipped without elevation;
- the tested machine's dominant consumer was a Baidu Netdisk `.accelerate` cache that
  beta 1 did not recognize;
- hibernation, installed applications, emulator images, virtual disks and Windows
  recovery/update data are not ordinary cache files.

User-provided real Windows evidence for beta 2 later showed an estimated 35.1 GB,
35.0 GB processed, and 35.0 GB observed free-space increase after the targeted Baidu
rule was introduced. This proves the earlier 1.7 GB was workload/rule coverage, not a
global execution failure. It does not prove every beta 3 rule on every machine.

## 3. Beta 3 changes

- Rule metadata now includes category, description, scan strategy, recommended action,
  elevation, dedicated confirmation, phrase, and default selection.
- Public risk vocabulary is SAFE / CAUTION / MANUAL / SYSTEM. PROTECTED remains an
  internal deny class; beta 2 enum names remain aliases for compatibility.
- Added narrow cache roots for VS Code, Discord, and classic Teams. No profile,
  configuration, extension, download, project, or chat-data directory is authorized;
  all three are default unchecked pending wider real-application validation.
- Added configurable large-file thresholds and a conservative advice classifier.
- Added attempted, processed, skipped, unattempted, cancelled and observed free-space
  metrics.
- Cleanup cancellation is cooperative between atomic file operations.
- Added independent Recycle Bin query/empty GUI actions through Windows Shell API.
- Expanded advanced-storage impact, administrator and reversibility information.
- Added `AGENTS.md`, this report, changelog, and version-independent release uploads.

## 4. Architecture

`RuleRegistry -> FastScanner -> user selection -> CleanupPlanner -> SafetyPolicy ->`
`DirectFileDeleteExecutor -> CleanupReceipt -> history/report`

The storage analyzer and advice classifier are read-only. They cannot create a cleanup
plan. SYSTEM operations use fixed code-owned command arrays or documented Windows APIs.

## 5. Cleaning coverage

Direct rules cover user/Windows temp, thumbnail and DirectX caches, crash dumps, WER
archives, Chrome/Edge/Firefox caches, pip/npm/NuGet/Gradle/Maven, Office/WPS, Baidu
accelerate cache, VS Code, Discord, and classic Teams. Recycle Bin is an independent
Windows API operation. DISM and powercfg remain isolated SYSTEM operations.

Windows Update, Delivery Optimization, restore points, shadow copies, unknown AppData,
QQ/WeChat data, installed programs, emulator images, virtual disks, downloads and
desktop files are analysis/advice only in beta 3.

## 6. Safety

Filesystem mutation remains confined to reviewed executors. Every file is rechecked for
trusted root, deny roots, traversal/namespace hazards, links/reparse points, current
identity, risk and elevation immediately before deletion. Permission, lock, race and
not-found errors are isolated and counted. Tests only delete temporary fixtures.

## 7. Tests

Post-change result at report creation: 90 passed, 1 Windows-only skipped, 85.52%
coverage. Ruff, formatting, strict mypy, mutation gate, release gate, portable GUI
offscreen smoke, source distribution and wheel build passed. A Linux PyInstaller smoke
also completed; it is not evidence of a Windows executable. Final Windows CI/build
status must be recorded in release notes after pushing the candidate.

## 8. Build

PyInstaller, version resources, Inno Setup, installer smoke scripts and GitHub Actions
are present and versioned for beta 3. A Linux cloud runner cannot truthfully validate a
Windows EXE; the Windows workflow is the authoritative build gate.

## 9. Email

Not applicable. There is no email feature, dependency, configuration or credential.
Email failure does not affect cleanup because no email execution path exists.

## 10. Known issues

- Unsigned binaries may trigger SmartScreen.
- Newly added application cache locations need broader real-version validation.
- Logical size can differ from physically reclaimed clusters for compressed/sparse data.
- Update cleanup and restore-point management are not automated.
- GUI analysis is explanatory text rather than a full interactive directory tree.

## 11. Requires Real Windows Validation

- Windows 10 22H2 and Windows 11, standard/admin, Chinese/English and redirected folders.
- GUI DPI, cancellation during large cleanup, locked files and junctions on NTFS.
- VS Code/Discord/Teams cache regeneration and retained login/configuration.
- Recycle Bin query/empty, DISM output/localization and hibernation on/off/recovery.
- Packaged EXE, silent installer/uninstaller, SmartScreen and antivirus behavior.

## 12. Release readiness

| Gate | Status | Evidence |
|---|---|---|
| Repository audit | PASS | Source, tests, packaging and workflows reviewed |
| Safety boundary | PASS | Mutation gate and focused unit/security tests |
| Linux cloud quality gates | PASS | 90 passed, 1 skipped, 85.52% coverage |
| Windows EXE/installer | PARTIAL | Scripts/workflows ready; candidate workflow pending |
| Real Windows beta 2 cleanup | PASS | User-observed 35.0 GB increase |
| Beta 3 application matrix | BLOCKED | Requires real Windows/application validation |
| Code signing | BLOCKED | No signing certificate |
| Production stable | BLOCKED | Remains an unsigned beta |

## 13. Next priorities

- P0: Run Windows CI, GUI smoke, EXE and installer smoke; fix all failures.
- P0: Validate beta 3 on a disposable Windows profile before public release.
- P1: Add Windows-supported Update/Delivery Optimization analysis and action only when
  reliable version-independent APIs/commands are identified.
- P1: Replace text analysis with safe directory drill-down and filters.
- P2: Add more application cache rules only with fixtures and retained-data evidence.
- P3: Code signing and update delivery after the beta behavior stabilizes.
