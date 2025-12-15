import random
import datetime
from typing import Dict, Tuple

from config import DEFAULT_VALUES, CLIMATE_PROFILES

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

class SeasonalDemoEngine:
    """
    Realistic environment drift + actuator effects.
    - Light changes fast when Lighting is ON
    - Soil moisture increases slowly when Watering is ON
    - Humidity increases moderately when Misting is ON
    - Heating increases temperature gradually and maintains stability
    """
    ANOMALIES = [
        "NORMAL",
        "HEATWAVE",
        "COLD_SNAP",
        "LOW_LIGHT",
        "HIGH_HUMIDITY",
        "LOW_HUMIDITY",
        "DRY_SOIL",
        "RAIN_FORECAST",
    ]

    def __init__(self):
        self.location = list(CLIMATE_PROFILES.keys())[0]
        self.season = "WINTER"
        self.anomaly = "NORMAL"
        self.values = DEFAULT_VALUES.copy()

        # simulated clock
        self.use_sim_time = True
        self.sim_minutes_per_tick = 15
        self.sim_clock = datetime.datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    def set_profile(self, location: str, season: str):
        self.location = location
        self.season = season

    def set_sim_time(self, enabled: bool):
        self.use_sim_time = bool(enabled)

    def set_minutes_per_tick(self, minutes: int):
        self.sim_minutes_per_tick = max(1, int(minutes))

    def reset_sim_time(self, hour: int = 9, minute: int = 0):
        self.sim_clock = self.sim_clock.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def now(self) -> datetime.datetime:
        return self.sim_clock if self.use_sim_time else datetime.datetime.now()

    def tick_clock(self):
        if self.use_sim_time:
            self.sim_clock += datetime.timedelta(minutes=self.sim_minutes_per_tick)

    def is_day(self, now: datetime.datetime) -> bool:
        return 7 <= now.hour < 19

    def next_anomaly(self) -> str:
        idx = self.ANOMALIES.index(self.anomaly)
        self.anomaly = self.ANOMALIES[(idx + 1) % len(self.ANOMALIES)]
        return self.anomaly

    def set_anomaly(self, name: str):
        if name in self.ANOMALIES:
            self.anomaly = name

    def _rand_range(self, a: Tuple[float, float]) -> float:
        return random.uniform(a[0], a[1])

    def step(self, actions: Dict[str, bool], manual_override: Dict[str, float] | None = None) -> Dict[str, float]:
        # manual override means "use sliders as the current sensor state"
        if manual_override is not None:
            self.values = manual_override.copy()

        now = self.now()
        profile = CLIMATE_PROFILES[self.location][self.season]
        day = self.is_day(now)

        # Ambient targets by season + day/night
        amb_temp = self._rand_range(profile["day_temp"] if day else profile["night_temp"])
        amb_hum = self._rand_range(profile["humidity"])
        peak_light = self._rand_range(profile["day_light_peak"])
        amb_light = peak_light if day else random.uniform(10, 80)

        # Anomaly modifiers
        if self.anomaly == "HEATWAVE":
            amb_temp += 10
        elif self.anomaly == "COLD_SNAP":
            amb_temp -= 10
        elif self.anomaly == "LOW_LIGHT":
            amb_light = min(amb_light, 120.0)
        elif self.anomaly == "HIGH_HUMIDITY":
            amb_hum = min(95.0, amb_hum + 15)
        elif self.anomaly == "LOW_HUMIDITY":
            amb_hum = max(15.0, amb_hum - 20)
        elif self.anomaly == "DRY_SOIL":
            pass
        elif self.anomaly == "RAIN_FORECAST":
            pass

        v = self.values.copy()

        # Base drift toward ambient (small)
        v["temp"] = clamp(v["temp"] + (amb_temp - v["temp"]) * 0.03 + random.uniform(-0.08, 0.08), -10, 55)
        v["humidity"] = clamp(v["humidity"] + (amb_hum - v["humidity"]) * 0.03 + random.uniform(-0.3, 0.3), 5, 100)
        v["light"] = clamp(v["light"] + (amb_light - v["light"]) * 0.06 + random.uniform(-6, 6), 0, 2500)

        # Soil dries slowly; faster in summer/hot
        dry_rate = 0.06 + max(0.0, (v["temp"] - 20.0)) * 0.004
        if self.season == "SUMMER":
            dry_rate *= 1.3
        if self.anomaly == "DRY_SOIL":
            dry_rate *= 1.6
        v["soil"] = clamp(v["soil"] - dry_rate + random.uniform(-0.05, 0.05), 0, 100)

        # Rain mm mostly 0; forecast anomaly raises it a bit
        if self.anomaly == "RAIN_FORECAST":
            v["rain"] = clamp(v["rain"] + random.uniform(0.0, 0.2), 0, 5)
        else:
            v["rain"] = clamp(v["rain"] * 0.85 + random.uniform(0.0, 0.03), 0, 2)

        # ---------------- Actuator effects (realistic)
        if actions.get("Heating"):
            # warm up gradually; stronger if very cold
            v["temp"] = clamp(v["temp"] + 0.25 + max(0, (18 - v["temp"])) * 0.03, -10, 55)
            # heating reduces humidity a little
            v["humidity"] = clamp(v["humidity"] - 0.3, 5, 100)

        if actions.get("Ventilation"):
            # cool and dry down
            v["temp"] = clamp(v["temp"] - 0.35, -10, 55)
            v["humidity"] = clamp(v["humidity"] - 0.8, 5, 100)

        if actions.get("Windows"):
            # mild exchange
            v["temp"] = clamp(v["temp"] + (amb_temp - v["temp"]) * 0.06, -10, 55)
            v["humidity"] = clamp(v["humidity"] + (amb_hum - v["humidity"]) * 0.06, 5, 100)

        if actions.get("Watering"):
            # soil increases slowly; humidity slightly
            v["soil"] = clamp(v["soil"] + 0.7 + random.uniform(0.0, 0.3), 0, 100)
            v["humidity"] = clamp(v["humidity"] + 0.4, 5, 100)

        if actions.get("Misting"):
            # humidity rises faster; tiny soil effect
            v["humidity"] = clamp(v["humidity"] + 1.2 + random.uniform(0.0, 0.4), 5, 100)
            v["soil"] = clamp(v["soil"] + 0.1, 0, 100)

        if actions.get("Lighting"):
            # light increases fast (not instant)
            boost_target = 900.0 if day else 350.0
            v["light"] = clamp(v["light"] + (boost_target - v["light"]) * 0.35 + 30, 0, 2500)

        self.values = v
        self.tick_clock()
        return v
