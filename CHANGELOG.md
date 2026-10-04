# Changelog

## 2.1.0 beta 1 — personal deep analysis

- Added lazy directory drill-down, top-1000 large-file path/extension/risk filters,
  partial-scan diagnostics, and live analysis counters. Directory aggregation now
  visits each directory once instead of every ancestor for each file.
- Added read-only duplicate discovery: size, edge sampling, then full SHA-256;
  skips hard links, validates changing files, supports cancellation and a file cap.
- Added Toolhelp application-process checks; running/unknown state skips cleanup.
- Replaced Windows path deletion with verified-handle disposition; rejects writers,
  hard links, changed identity, unexpected final path and reparse ancestors.
- Restored 7-day Temp retention and added shared scan/plan/execution predicates.
- Office pending-upload cache and Maven local artifacts are advisory-only; browser
  offline CacheStorage is preserved. CAUTION is no longer preselected.
- Added Epic Games documented webcache roots, default unchecked and process guarded.
- Enforced dedicated confirmation in CLI as well as GUI and revalidated rule
  metadata inside production executors.
- Serialized GUI jobs, captured cancellation tokens per task, guarded close while
  busy, added failure summaries and history details, DISM cleanup and restore-hibernation UI.
- Windows command execution resolves executables from the trusted system directory.
- Reduced Qt dependency to Essentials; made PowerShell quality gates fail on any
  command failure and extended the mutation gate to aliases and handle deletion.
- All test fixtures and benchmark cleanup are confined to tests/.tmp.
- Versioned the tightened catalog rules; isolated build PATH to prevent unrelated
  ICU DLLs from entering the EXE, and made frozen startup smoke mandatory.
- Added a reproducible personal ZIP packager, included source and acceptance evidence.

## 2.0.0 beta 3 — development

- Expanded the code-owned cleanup catalog from 17 to 20 rules with narrowly scoped
  VS Code, Discord, and classic Teams cache roots, default unchecked pending wider
  real-application validation.
- Replaced the user-facing RECOMMENDED/REVIEW/ADVANCED wording with
  SAFE/CAUTION/MANUAL/SYSTEM while retaining compatibility aliases.
- Added rule category, description, scan strategy, recommendation, selection, and
  dedicated-confirmation metadata; removed Baidu confirmation hard-coding from GUI.
- Added configurable 500 MB, 1 GB, and 5 GB large-file thresholds and conservative
  advice for system files, virtual disks, applications, development environments,
  AppData, downloads, and archives.
- Added attempted, processed, skipped, unattempted, cancelled, and observed-free-space
  cleanup accounting.
- Added cooperative cleanup cancellation between atomic file operations.
- Added GUI query and independently confirmed emptying of the system-drive Recycle Bin.
- Expanded hibernation/pagefile/virtual-disk impact, administrator, and reversibility
  explanations.
- Made release-asset publishing version-independent.

## 2.0.0 beta 2

- Added targeted Baidu Netdisk accelerate-cache cleanup with dedicated confirmation.
- Expanded Chrome and Edge multi-profile cache discovery.
- Added administrator relaunch and supported hibernation control.

## 2.0.0 beta 1

- Delivered the v2 safety kernel, quick clean, storage analyzer, advanced Windows
  operations, GUI, EXE/installer packaging, CI, and release gates.
