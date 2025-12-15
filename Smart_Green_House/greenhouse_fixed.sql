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
