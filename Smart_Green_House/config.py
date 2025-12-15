DB_NAME = "smart_greenhouse.db"

# UI / demo loop
AUTO_INSERT_INTERVAL_SEC = 2.0

# Greenhouse desired thresholds (logic decisions)
TEMP_LOW = 15.0
TEMP_HIGH = 30.0

HUMIDITY_LOW = 40.0
HUMIDITY_HIGH = 80.0

LIGHT_MIN = 250.0
SOIL_MIN = 30.0

# Demo defaults (starting values)
DEFAULT_VALUES = {
    "temp": 22.0,
    "humidity": 55.0,
    "light": 350.0,
    "rain": 0.0,   # mm
    "soil": 45.0,
}

# UI range lines + warnings (not logic)
ALERT_LIMITS = {
    "temp":     {"min": TEMP_LOW, "max": TEMP_HIGH},
    "humidity": {"min": HUMIDITY_LOW, "max": HUMIDITY_HIGH},
    "light":    {"min": 0.0, "max": 2000.0},
    "rain":     {"min": 0.0, "max": 20.0},
    "soil":     {"min": SOIL_MIN, "max": 90.0},
}

ALERT_COOLDOWN_SEC = 5

# Climate profiles: ambient environment (NOT the greenhouse target)
# These values drive the demo engine so you get realistic seasonal behavior in Bulgaria.
CLIMATE_PROFILES = {
    "Bulgaria (Varna)": {
        "WINTER": {"day_temp": (3, 10),  "night_temp": (-2, 6),  "humidity": (60, 85), "day_light_peak": (350, 650)},
        "SPRING": {"day_temp": (12, 22), "night_temp": (5, 14),  "humidity": (50, 75), "day_light_peak": (600, 1000)},
        "SUMMER": {"day_temp": (28, 40), "night_temp": (18, 26), "humidity": (40, 70), "day_light_peak": (900, 1600)},
        "AUTUMN": {"day_temp": (12, 22), "night_temp": (6, 14),  "humidity": (55, 80), "day_light_peak": (450, 900)},
    },
    "Bulgaria (Sofia)": {
        "WINTER": {"day_temp": (-3, 6),  "night_temp": (-10, 0), "humidity": (55, 80), "day_light_peak": (300, 600)},
        "SPRING": {"day_temp": (10, 20), "night_temp": (2, 10),  "humidity": (45, 70), "day_light_peak": (600, 1100)},
        "SUMMER": {"day_temp": (30, 42), "night_temp": (18, 26), "humidity": (35, 65), "day_light_peak": (950, 1700)},
        "AUTUMN": {"day_temp": (10, 20), "night_temp": (2, 10),  "humidity": (50, 80), "day_light_peak": (450, 900)},
    },
    "Bulgaria (Plovdiv)": {
        "WINTER": {"day_temp": (0, 8),   "night_temp": (-6, 2),  "humidity": (55, 80), "day_light_peak": (320, 650)},
        "SPRING": {"day_temp": (14, 24), "night_temp": (6, 14),  "humidity": (45, 70), "day_light_peak": (650, 1150)},
        "SUMMER": {"day_temp": (32, 44), "night_temp": (20, 28), "humidity": (30, 60), "day_light_peak": (1000, 1800)},
        "AUTUMN": {"day_temp": (14, 24), "night_temp": (6, 14),  "humidity": (50, 75), "day_light_peak": (480, 950)},
    },
}
