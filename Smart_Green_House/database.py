import sqlite3
from pathlib import Path
from typing import Optional, Dict, Tuple

from config import DB_NAME

DEFAULT_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Sensor (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    sensor_type TEXT NOT NULL,
    unit TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS Reading (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id INTEGER NOT NULL,
    value REAL NOT NULL,
    recorded_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(sensor_id) REFERENCES Sensor(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_reading_sensor_time ON Reading(sensor_id, recorded_at);
"""

class DatabaseManager:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(__file__).resolve().parent
        self.db_path = self.base_dir / DB_NAME

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        self.initialize_db()
        self._ensure_default_sensors()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def initialize_db(self):
        try:
            self.conn.executescript(DEFAULT_SCHEMA)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _get_or_create_sensor(self, name: str, sensor_type: str, unit: str) -> int:
        self.cursor.execute("SELECT id FROM Sensor WHERE name = ?", (name,))
        row = self.cursor.fetchone()
        if row:
            return int(row["id"])

        self.cursor.execute(
            "INSERT INTO Sensor(name, sensor_type, unit) VALUES(?,?,?)",
            (name, sensor_type, unit),
        )
        self.conn.commit()
        return int(self.cursor.lastrowid)

    def _ensure_default_sensors(self):
        defaults: Dict[str, Tuple[str, str]] = {
            "temp": ("temperature", "°C"),
            "humidity": ("humidity", "%"),
            "light": ("light", "lux"),
            "rain": ("rain", "mm"),
            "soil": ("soil_moisture", "%"),
        }
        for name, (stype, unit) in defaults.items():
            self._get_or_create_sensor(name, stype, unit)

    def insert_reading(self, temp: float, humidity: float, light: float, rain: float, soil: float) -> None:
        values = {"temp": temp, "humidity": humidity, "light": light, "rain": rain, "soil": soil}
        try:
            for sensor_name, val in values.items():
                self.cursor.execute("SELECT id FROM Sensor WHERE name = ?", (sensor_name,))
                row = self.cursor.fetchone()
                sensor_id = int(row["id"]) if row else self._get_or_create_sensor(sensor_name, sensor_name, "")
                self.cursor.execute(
                    "INSERT INTO Reading(sensor_id, value) VALUES(?, ?)",
                    (sensor_id, float(val)),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def get_history(self, sensor_key: str, hours: int | None = None, limit: int = 5000):
        """
        Returns list of tuples: (recorded_at, value)
        If hours is provided (e.g., 6 or 24), returns only records from last N hours.
        """
        self.cursor.execute("SELECT id FROM Sensor WHERE name = ?", (sensor_key,))
        row = self.cursor.fetchone()
        if not row:
            return []

        sensor_id = int(row["id"])

        if hours is None:
            self.cursor.execute(
                """
                SELECT recorded_at, value
                FROM Reading
                WHERE sensor_id = ?
                ORDER BY recorded_at DESC
                LIMIT ?
                """,
                (sensor_id, int(limit)),
            )
        else:
            self.cursor.execute(
                """
                SELECT recorded_at, value
                FROM Reading
                WHERE sensor_id = ?
                  AND recorded_at >= datetime('now', ?)
                ORDER BY recorded_at DESC
                LIMIT ?
                """,
                (sensor_id, f"-{int(hours)} hours", int(limit)),
            )

        rows = [(r["recorded_at"], float(r["value"])) for r in self.cursor.fetchall()]
        rows.reverse()
        return rows
