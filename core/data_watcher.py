"""
Real-time Data Watcher

Monitors NT8's trade.sqlite for changes and emits signals
when new execution data arrives. Uses polling since SQLite
file modification events can be unreliable on Windows.
"""

from pathlib import Path
from PyQt6.QtCore import QTimer, QObject, pyqtSignal
import os
import time


class NT8DataWatcher(QObject):
    """
    Polls NT8's trade.sqlite for changes.
    Emits `data_changed` signal when file modification time updates.
    """
    data_changed = pyqtSignal()
    connection_changed = pyqtSignal(bool)  # True = connected, False = disconnected

    def __init__(self, db_path: Path, interval_ms: int = 3000, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self._last_mtime = 0.0
        self._connected = False
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._poll)

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def set_interval(self, ms: int):
        self._timer.setInterval(ms)

    def _poll(self):
        exists = self.db_path.exists()

        if exists != self._connected:
            self._connected = exists
            self.connection_changed.emit(self._connected)

        if not exists:
            return

        try:
            mtime = os.path.getmtime(self.db_path)
            if mtime != self._last_mtime:
                self._last_mtime = mtime
                self.data_changed.emit()
        except OSError:
            pass
