# config.py

DB_NAME = "smart_greenhouse.db"
LOG_FILE = "greenhouse.log"

# ----------------------------
# UI / LOOPS
# ----------------------------
AUTO_INSERT_INTERVAL_SEC = 2.0   # simulation tick every N seconds
UI_FPS = 60                      # smooth UI refresh
GRAPH_REFRESH_SEC = 1.0          # refresh open graphs ~1/sec

# ----------------------------
# CONTROL BANDS (targets ± band)
# ----------------------------
TEMP_BAND_C = 2.0         # heating tries to keep within ±2C
HUM_BAND_PCT = 6.0        # ventilation/windows for high humidity
SOIL_BAND_PCT = 2.5       # watering hysteresis band
LIGHT_BAND_LUX = 60.0     # lighting hysteresis band

# HYSTERESIS (smaller than bands)
TEMP_HYST_C = 0.7
HUM_HYST_PCT = 3.0
SOIL_HYST_PCT = 2.0
LIGHT_HYST_LUX = 40.0

# Minimum ON times (strict actuators)
MIN_ON_VENT_SEC = 15 * 60
MIN_ON_WIN_SEC = 15 * 60
MIN_ON_WATER_SEC = 12 * 60
MIN_ON_MIST_SEC = 10 * 60
MIN_ON_LIGHT_SEC = 10 * 60

ALLOW_LIGHT_AT_NIGHT = True

# ----------------------------
# DEFAULT VALUES
# ----------------------------
DEFAULT_VALUES = {
    "temp": 22.0,
    "humidity": 55.0,
    "light": 350.0,
    "rain": 0.0,
    "soil": 45.0,
}

# ----------------------------
# CITY / SEASON (codes + labels)
# ----------------------------
CITIES = [
    {"code": "Ruse", "bg": "Русе", "en": "Ruse"},
    {"code": "Varna", "bg": "Варна", "en": "Varna"},
    {"code": "Burgas", "bg": "Бургас", "en": "Burgas"},
    {"code": "Sofia", "bg": "София", "en": "Sofia"},
    {"code": "Plovdiv", "bg": "Пловдив", "en": "Plovdiv"},
]
DEFAULT_CITY_CODE = "Ruse"

SEASONS = [
    {"code": "WINTER", "bg": "Зима", "en": "Winter"},
    {"code": "SPRING", "bg": "Пролет", "en": "Spring"},
    {"code": "SUMMER", "bg": "Лято", "en": "Summer"},
    {"code": "FALL",   "bg": "Есен", "en": "Fall"},
]
DEFAULT_SEASON_CODE = "WINTER"

# ----------------------------
# PLANTS (codes + labels + targets)
# ----------------------------
PLANTS = [
    {"code": "TOMATO", "bg": "Домати", "en": "Tomatoes",
     "temp_day": 24.0, "temp_night": 18.0, "hum": 60.0, "light_min": 250.0, "soil_min": 45.0},
    {"code": "CUCUMBER", "bg": "Краставици", "en": "Cucumbers",
     "temp_day": 25.0, "temp_night": 19.0, "hum": 70.0, "light_min": 250.0, "soil_min": 50.0},
    {"code": "PEPPER", "bg": "Пипер", "en": "Pepper",
     "temp_day": 24.0, "temp_night": 18.0, "hum": 60.0, "light_min": 250.0, "soil_min": 40.0},
    {"code": "LETTUCE", "bg": "Маруля", "en": "Lettuce",
     "temp_day": 18.0, "temp_night": 12.0, "hum": 65.0, "light_min": 200.0, "soil_min": 50.0},
    {"code": "STRAWBERRY", "bg": "Ягоди", "en": "Strawberries",
     "temp_day": 20.0, "temp_night": 14.0, "hum": 65.0, "light_min": 220.0, "soil_min": 45.0},
    {"code": "BASIL", "bg": "Босилек", "en": "Basil",
     "temp_day": 23.0, "temp_night": 17.0, "hum": 55.0, "light_min": 250.0, "soil_min": 40.0},
    {"code": "SPINACH", "bg": "Спанак", "en": "Spinach",
     "temp_day": 18.0, "temp_night": 12.0, "hum": 65.0, "light_min": 200.0, "soil_min": 50.0},
]
DEFAULT_PLANT_CODE = "TOMATO"

# ----------------------------
# ANOMALIES (codes + labels)
# ----------------------------
ANOMALIES = [
    "NORMAL",
    "DRY_AIR",
    "HUMID_AIR",
    "LOW_LIGHT",
    "HEAT_WAVE",
    "COLD_SNAP",
    "DRY_SOIL",
    "RAIN_FORECAST",
    "FAN_FAULT",
    "PUMP_FAULT",
    "MISTER_FAULT",
]

ANOMALY_LABELS = {
    "NORMAL": {"bg": "Нормално", "en": "Normal"},
    "DRY_AIR": {"bg": "Сух въздух", "en": "Dry air"},
    "HUMID_AIR": {"bg": "Влажен въздух", "en": "Humid air"},
    "LOW_LIGHT": {"bg": "Ниска светлина (облаци)", "en": "Low light (clouds)"},
    "HEAT_WAVE": {"bg": "Гореща вълна", "en": "Heat wave"},
    "COLD_SNAP": {"bg": "Студен фронт", "en": "Cold snap"},
    "DRY_SOIL": {"bg": "Суха почва", "en": "Dry soil"},
    "RAIN_FORECAST": {"bg": "Прогноза дъжд", "en": "Rain forecast"},
    "FAN_FAULT": {"bg": "Повреда вентилатор", "en": "Fan fault"},
    "PUMP_FAULT": {"bg": "Повреда помпа", "en": "Pump fault"},
    "MISTER_FAULT": {"bg": "Повреда овлажнител", "en": "Mister fault"},
}

# ----------------------------
# GRAPH RANGES
# ----------------------------
GRAPH_RANGES = ["last7", "6h", "24h", "all"]

# ----------------------------
# ACTION LABELS (internal keys)
# ----------------------------
ACTION_LABELS = {
    "Heating": {"bg": "Отопление", "en": "Heating", "emoji": "🔥"},
    "Ventilation": {"bg": "Вентилация", "en": "Ventilation", "emoji": "🌀"},
    "Windows": {"bg": "Прозорци", "en": "Windows", "emoji": "🪟"},
    "Watering": {"bg": "Поливане", "en": "Watering", "emoji": "💧"},
    "Misting": {"bg": "Овлажняване", "en": "Misting", "emoji": "🌫"},
    "Lighting": {"bg": "Осветление", "en": "Lighting", "emoji": "💡"},
    "RainProtection": {"bg": "Защита от дъжд", "en": "Rain protection", "emoji": "☔"},
    "Alarm": {"bg": "Аларма", "en": "Alarm", "emoji": "🚨"},
}

# ----------------------------
# MAINTENANCE THRESHOLDS (hours)
# ----------------------------
MAINTENANCE_THRESHOLDS_H = {
    "Ventilation": 1500.0,
    "Windows": 2000.0,
    "Watering": 1200.0,
    "Misting": 1200.0,
    "Lighting": 3000.0,
    "Heating": 2500.0,
}

# ----------------------------
# SIMULATOR / ENVIRONMENT
# ----------------------------
# Natural light ranges (lux)
NATURAL_LIGHT_DAY_RANGE = (500.0, 650.0)
NATURAL_LIGHT_NIGHT_RANGE = (120.0, 200.0)

# Lamp target range (lux) - slow and steady
LAMP_LIGHT_TARGET_RANGE = (450.0, 520.0)

# Rain (mm) indicator when forecast
RAIN_MM_WHEN_FORECAST = 3.5

# Random faults
RANDOM_FAULT_PROB = 0.02

# Temperature behavior at night: do not allow greenhouse to drop below ~8-10C (winter demo requirement)
MIN_NIGHT_TEMP_C = 8.0

# Rates tuned for: reach target in ~1-4 simulated hours (with minutes_per_tick = 15)
HEATING_RATE_C_PER_HOUR = 4.0      # +1C per 15min tick
WATER_SOIL_PCT_PER_HOUR = 6.0      # +1.5% per 15min tick
MIST_HUM_PCT_PER_HOUR = 7.0        # +1.75% per 15min tick
VENT_LEAK_MULT = 0.55              # vent/windows pull inside toward outside faster

# ----------------------------
# I18N (UI strings)
# ----------------------------
I18N = {
    "bg": {
        "app_title": "Smart Greenhouse - Курсов Проект",
        "lang": "Език",
        "controls": "Контроли",
        "auto_mode": "Автоматичен режим",
        "interval": "Интервал (сек):",
        "apply": "Приложи",
        "fullscreen": "Fullscreen / Windowed",
        "profiles": "Профили",
        "city": "Град:",
        "season": "Сезон:",
        "plant": "Растение:",
        "targets": "Цели",
        "time_demo": "Време (Demo)",
        "sim_time": "Симулирано време (ден/нощ)",
        "minutes_tick": "Минути / tick:",
        "set": "Задай",
        "reset_now": "Reset clock = NOW",
        "scenario": "Аномалии",
        "diagnostics": "Диагностика",
        "enable_faults": "Случайни повреди",
        "open_log": "Отвори лог",
        "manual": "Ръчни входове",
        "manual_enable": "Ръчни входове (override)",
        "graphs": "Графики",
        "range": "Обхват:",
        "show_temp": "Покажи: Температура",
        "show_hum": "Покажи: Влажност",
        "show_light": "Покажи: Светлина",
        "show_soil": "Покажи: Почва",
        "show_rain": "Покажи: Дъжд",
        "status_title": "Статус на оранжерията",
        "day": "ДЕН ☀️",
        "night": "НОЩ 🌙",
        "no_warnings": "Няма предупреждения.",
        "log_title": "Лог (последни записи)",
    },
    "en": {
        "app_title": "Smart Greenhouse - Course Project",
        "lang": "Language",
        "controls": "Controls",
        "auto_mode": "Auto mode",
        "interval": "Interval (sec):",
        "apply": "Apply",
        "fullscreen": "Fullscreen / Windowed",
        "profiles": "Profiles",
        "city": "City:",
        "season": "Season:",
        "plant": "Plant:",
        "targets": "Targets",
        "time_demo": "Time (Demo)",
        "sim_time": "Simulated time (day/night)",
        "minutes_tick": "Minutes / tick:",
        "set": "Set",
        "reset_now": "Reset clock = NOW",
        "scenario": "Anomalies",
        "diagnostics": "Diagnostics",
        "enable_faults": "Random faults",
        "open_log": "Open log",
        "manual": "Manual inputs",
        "manual_enable": "Manual inputs (override)",
        "graphs": "Graphs",
        "range": "Range:",
        "show_temp": "Show: Temperature",
        "show_hum": "Show: Humidity",
        "show_light": "Show: Light",
        "show_soil": "Show: Soil",
        "show_rain": "Show: Rain",
        "status_title": "Greenhouse Status",
        "day": "DAY ☀️",
        "night": "NIGHT 🌙",
        "no_warnings": "No warnings.",
        "log_title": "Log (latest entries)",
    },
}
