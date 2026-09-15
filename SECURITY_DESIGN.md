# C Drive Safe Cleaner v1.0.0 — Security Design

## 1. Trust boundary

The application treats every filesystem path, environment variable, directory
entry, configuration value, and scan result as untrusted.  A scan result is
never an authorization to delete.  Authorization is performed again for every
individual file immediately before the delete attempt.

Real cleanup is supported only for code-defined `SAFE` rules.  `CAUTION`,
`MANUAL`, unknown, and `NEVER_DELETE` items are report-only in v1.0.0.  The
editable `config.json` cannot add deletion roots or change a risk level.

## 2. Security invariants

- **INV-001 — Deny wins:** no path in or beneath a denylisted location can be
  deleted, even when it also matches an allowlisted scope.
- **INV-002 — No link escape:** a symlink, junction, mount point, or other
  reparse point cannot be traversed during scanning or deletion.
- **INV-003 — Dry run cannot delete:** dry-run mode never calls a cleanup
  mutation API. It may write its explicitly documented local log and report.
- **INV-004 — Unknown means report-only:** an unknown directory is never an
  automatic cleanup target.
- **INV-005 — Size is not permission:** size and anomaly findings never grant
  deletion authority.
- **INV-006 — User data is protected:** Desktop, Documents, Downloads,
  Pictures, Videos, Music, OneDrive, source repositories, databases, and user
  records are not cleanup targets.
- **INV-007 — One deletion gateway:** production deletion is reachable only
  through `SafetyGuard.delete_file`.
- **INV-008 — SAFE only:** the deletion gateway rejects every risk level other
  than `SAFE`.
- **INV-009 — Revalidation:** normalized, absolute, canonical, scope, denylist,
  link/reparse, type, and identity checks run immediately before deletion.
- **INV-010 — Configuration cannot authorize:** configuration can enable or
  disable built-in rules but cannot define paths or weaken the guard.
- **INV-011 — No recursive bulk delete:** files are handled individually;
  empty directories are removed only after a fresh safety check.
- **INV-012 — Failure containment:** a denied, missing, locked, long, or
  inaccessible path is skipped and logged without aborting the run.

## 3. Authorization pipeline

1. A built-in cache rule supplies an immutable rule id, risk, and scope root.
2. The scanner walks without following directory links or reparse points.
3. The scanner records a file identity snapshot where available.
4. Before deletion, the guard expands and normalizes the candidate and scope.
5. The guard rejects non-local/UNC paths and non-absolute paths.
6. The guard proves lexical and canonical containment in the same built-in
   allowlisted scope.
7. The guard checks hard-coded protected roots, names, and user-data segments.
8. Every existing component from scope to target is checked for symlink,
   junction, mount, and reparse attributes.
9. The target must be a regular file and its identity must still match the
   scan snapshot when one was captured.
10. In dry-run mode a `SIMULATED_DELETE` result is emitted.  Otherwise the one
    guarded `os.remove` call is attempted.

## 4. Hard-coded protected areas

Windows system components, program installation trees, recovery/boot areas,
WindowsApps, user libraries, OneDrive, paging/hibernation files, browser
credentials/profile state, WPS backup/recovery/cloud locations, and common
project/database markers are protected.  Protection is implemented in code,
not loaded from configuration.

## 5. Residual risk and TOCTOU

Python's standard library cannot provide a fully race-free Windows
delete-by-handle primitive.  v1.0.0 narrows the race by rescanning each cleanup
scope and then performing canonical path, parent-chain, reparse, type, and file
identity checks immediately before each individual delete.  Running untrusted
software concurrently with cleanup is outside the threat model.  The program
does not elevate itself and recommends closing cache-producing applications.

## 6. Non-goals

The program does not remove Windows Update data, Windows.old, the recycle bin,
program installations, user documents, browser history/cookies/passwords,
Office sync caches, WPS backups, or unknown large directories.  It does not
change services, permissions, registry keys, Defender, or SmartScreen, and it
never connects to a network.
