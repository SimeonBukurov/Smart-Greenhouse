# logger.py
from __future__ import annotations

import datetime as dt
from typing import List
from config import LOG_FILE

class EventLogger:
    def __init__(self, file_path: str = LOG_FILE, keep_last: int = 400):
        self.file_path = file_path
        self.keep_last = keep_last
        self._buffer: List[str] = []

    def log(self, msg: str) -> None:
        ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {msg}"
        self._buffer.append(line)
        if len(self._buffer) > self.keep_last:
            self._buffer = self._buffer[-self.keep_last:]

        try:
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            # do not crash UI
            pass

    def tail(self, n: int = 200) -> str:
        # prefer file tail if possible
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return "".join(lines[-n:])
        except Exception:
            return "\n".join(self._buffer[-n:])
