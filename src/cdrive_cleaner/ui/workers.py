"""Small Qt thread-pool adapter used by long-running application services."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    completed = Signal(object)
    failed = Signal(str)


class FunctionWorker(QRunnable):
    def __init__(self, operation: Callable[[], Any]) -> None:
        super().__init__()
        self.operation = operation
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.completed.emit(self.operation())
        except Exception as error:  # Qt boundary converts failures to UI text.
            self.signals.failed.emit(str(error))
