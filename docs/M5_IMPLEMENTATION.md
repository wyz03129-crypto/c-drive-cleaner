# M5 — Windows desktop beta candidate

M5 adds the consumer-facing PySide6 desktop application and a reproducible Windows EXE build.

## Delivered

- Overview of C-drive capacity and remaining space.
- Background quick scan with category selection and cancellation.
- One clear confirmation followed by real cleanup; dry-run is not the GUI default.
- Estimated, processed, and observed free-space values remain separate.
- Large-directory and large-file analysis.
- Read-only advanced-storage inspection and allowlisted Windows official tools.
- Aggregate cleanup history without file paths.
- Privacy-safe diagnostic ZIP export.
- PyInstaller one-file Windows build and SHA-256 checksum.
- Per-user Inno Setup installer with Start Menu entry and uninstall support.
- Offscreen GUI construction smoke test and 20-cycle confined cleanup stress test.
- GitHub Actions build artifact for every relevant change on `main`.

## Safety boundaries

The GUI does not directly delete WinSxS content, virtual disks, hibernation files, page files, user
documents, or protected Windows directories. Advanced mutating operations remain behind the M4
action-specific confirmation and administrator checks. The CLI retains dry-run for automation and
technical review, while the GUI uses scan, selection, confirmation, real execution, and verification.

## Release status

The generated executable is an **unsigned beta candidate**. Code signing and validation on a real
Windows 10/11 machine with representative application caches are required before calling it a
production release.
