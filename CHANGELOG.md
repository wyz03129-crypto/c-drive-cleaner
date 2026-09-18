# Changelog

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
