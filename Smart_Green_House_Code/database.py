from __future__ import annotations

import sqlite3
import datetime as dt
from typing import Optional, List, Tuple

class DatabaseManager:
    """
    Keeps your original 'readings' table for graphs (do not break).
    Also adds Sensor/Reading tables (optional, helps for expansion).
    """

    def __init__(self, db_name: str):
        self.db_name = db_name
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_name)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            # original table (graphs rely on this)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS readings (
                    ts TEXT PRIMARY KEY,
                    temp REAL NOT NULL,
                    humidity REAL NOT NULL,
                    light REAL NOT NULL,
                    rain REAL NOT NULL,
                    soil REAL NOT NULL
                )
                """
            )

            # optional normalized schema
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS Sensor (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    sensor_type TEXT NOT NULL,
                    unit TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS Reading (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sensor_id INTEGER NOT NULL,
                    value REAL NOT NULL,
                    recorded_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY(sensor_id) REFERENCES Sensor(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reading_sensor_time ON Reading(sensor_id, recorded_at)")
            conn.commit()

            # ensure sensors exist
            self._ensure_sensor(conn, "temp", "temperature", "°C")
            self._ensure_sensor(conn, "humidity", "humidity", "%")
            self._ensure_sensor(conn, "light", "light", "lux")
            self._ensure_sensor(conn, "rain", "rain", "mm")
            self._ensure_sensor(conn, "soil", "soil", "%")

    @staticmethod
    def _ensure_sensor(conn: sqlite3.Connection, name: str, sensor_type: str, unit: str) -> None:
        conn.execute(
            "INSERT OR IGNORE INTO Sensor(name, sensor_type, unit) VALUES(?,?,?)",
            (name, sensor_type, unit),
        )

    @staticmethod
    def _ts_to_str(ts: Optional[object]) -> str:
        if ts is None:
            ts = dt.datetime.now()
        if isinstance(ts, str):
            return ts
        if isinstance(ts, dt.datetime):
            return ts.isoformat(sep=" ", timespec="seconds")
        raise TypeError(f"Unsupported ts type: {type(ts)}")

    def _sensor_id(self, conn: sqlite3.Connection, name: str) -> int:
        cur = conn.execute("SELECT id FROM Sensor WHERE name = ?", (name,))
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"Sensor missing: {name}")
        return int(row[0])

    def insert_reading(self, temp: float, humidity: float, light: float, rain: float, soil: float, ts=None) -> None:
        ts_str = self._ts_to_str(ts)
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO readings (ts, temp, humidity, light, rain, soil) VALUES (?, ?, ?, ?, ?, ?)",
                (ts_str, float(temp), float(humidity), float(light), float(rain), float(soil)),
            )

            # also insert normalized readings
            sid_temp = self._sensor_id(conn, "temp")
            sid_hum = self._sensor_id(conn, "humidity")
            sid_light = self._sensor_id(conn, "light")
            sid_rain = self._sensor_id(conn, "rain")
            sid_soil = self._sensor_id(conn, "soil")

            conn.execute("INSERT INTO Reading(sensor_id, value, recorded_at) VALUES(?,?,?)", (sid_temp, float(temp), ts_str))
            conn.execute("INSERT INTO Reading(sensor_id, value, recorded_at) VALUES(?,?,?)", (sid_hum, float(humidity), ts_str))
            conn.execute("INSERT INTO Reading(sensor_id, value, recorded_at) VALUES(?,?,?)", (sid_light, float(light), ts_str))
            conn.execute("INSERT INTO Reading(sensor_id, value, recorded_at) VALUES(?,?,?)", (sid_rain, float(rain), ts_str))
            conn.execute("INSERT INTO Reading(sensor_id, value, recorded_at) VALUES(?,?,?)", (sid_soil, float(soil), ts_str))

            conn.commit()

    def fetch_all(self) -> List[Tuple[str, float, float, float, float, float]]:
        with self._conn() as conn:
            cur = conn.execute("SELECT ts, temp, humidity, light, rain, soil FROM readings ORDER BY ts ASC")
            return cur.fetchall()

    def fetch_since(self, since_ts: str) -> List[Tuple[str, float, float, float, float, float]]:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT ts, temp, humidity, light, rain, soil FROM readings WHERE ts >= ? ORDER BY ts ASC",
                (since_ts,),
            )
            return cur.fetchall()

    def fetch_last_n(self, n: int) -> List[Tuple[str, float, float, float, float, float]]:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT ts, temp, humidity, light, rain, soil FROM readings ORDER BY ts DESC LIMIT ?",
                (int(n),),
            )
            rows = cur.fetchall()
            return list(reversed(rows))
