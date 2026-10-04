# Third-party components

The application's MIT license does not replace the licenses of its dependencies.
This personal beta uses unmodified Python, PySide6 Essentials / Qt and Shiboken6,
and a PyInstaller bootloader. Dependency versions are recorded in BUILD_INFO.json.

- Python: Python Software Foundation license; https://www.python.org/downloads/source/
- PySide6 Essentials and Shiboken6: the installed wheel metadata declares
  LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only. This package includes the GNU LGPLv3
  and GPLv3 texts. Qt source: https://code.qt.io/cgit/qt/qtbase.git/
  and https://code.qt.io/cgit/pyside/pyside-setup.git/ (matching release tags).
- PyInstaller: GPL with a bootloader exception;
  https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt

Application source and build instructions are included in source/. The application
does not restrict inspection, modification, or rebuilding with compatible replacement
Qt/PySide libraries. Build with `pip install -e ".[dev,packaging]"` then run
`scripts/build_exe.ps1` from PowerShell. The usual Python/Qt build prerequisites apply.

Copies of license files found in the installed distributions are included under
licenses/. Commercial license text in a wheel is an upstream artifact, not a claim
that this project has purchased or grants a Qt commercial license.
