# simulator.py
from __future__ import annotations

import math
import datetime as dt
from dataclasses import dataclass
from typing import Dict, Tuple, Optional

from config import (
    NATURAL_LIGHT_DAY_RANGE, NATURAL_LIGHT_NIGHT_RANGE,
    LAMP_LIGHT_TARGET_RANGE,
    RANDOM_FAULT_PROB,
    RAIN_MM_WHEN_FORECAST,
    MIN_NIGHT_TEMP_C,
    HEATING_RATE_C_PER_HOUR,
    WATER_SOIL_PCT_PER_HOUR,
    MIST_HUM_PCT_PER_HOUR,
    VENT_LEAK_MULT,
)

# Approx sunrise/sunset by season (stable)
SEASON_SUN = {
    "WINTER": (7.5, 17.0),
    "SPRING": (6.5, 19.5),
    "SUMMER": (5.75, 20.75),
    "FALL":   (7.0, 18.5),
}

# Outside baseline by city+season (°C, %RH)
CITY_SEASON_OUTSIDE = {
    "Ruse":   {"WINTER": (1.5, 75.0), "SPRING": (15.0, 65.0), "SUMMER": (33.0, 50.0), "FALL": (16.0, 65.0)},
    "Varna":  {"WINTER": (5.5, 78.0), "SPRING": (16.0, 70.0), "SUMMER": (30.0, 55.0), "FALL": (18.0, 70.0)},
    "Burgas": {"WINTER": (5.5, 80.0), "SPRING": (16.0, 70.0), "SUMMER": (31.0, 55.0), "FALL": (18.0, 70.0)},
    "Sofia":  {"WINTER": (0.5, 70.0), "SPRING": (14.0, 60.0), "SUMMER": (32.0, 45.0), "FALL": (15.0, 60.0)},
    "Plovdiv":{"WINTER": (3.0, 70.0), "SPRING": (16.0, 60.0), "SUMMER": (35.0, 45.0), "FALL": (17.0, 60.0)},
}

def clamp(x: float, a: float, b: float) -> float:
    return max(a, min(b, x))

def hour_of_day(t: dt.datetime) -> float:
    return t.hour + t.minute / 60.0 + t.second / 3600.0

def lerp(a: float, b: float, k: float) -> float:
    return a + (b - a) * k

def natural_light_lux(season: str, t: dt.datetime) -> float:
    sunrise, sunset = SEASON_SUN.get(season, (7.5, 17.0))
    h = hour_of_day(t)
    if h < sunrise or h > sunset:
        return lerp(NATURAL_LIGHT_NIGHT_RANGE[0], NATURAL_LIGHT_NIGHT_RANGE[1], 0.5)

    day_len = max(0.1, (sunset - sunrise))
    x = (h - sunrise) / day_len
    y = math.sin(math.pi * x)  # 0->1->0
    peak = lerp(NATURAL_LIGHT_DAY_RANGE[0], NATURAL_LIGHT_DAY_RANGE[1], 0.75)
    return lerp(260.0, peak, y)

@dataclass
class Faults:
    fan_fault: bool = False
    pump_fault: bool = False
    mister_fault: bool = False

    def any(self) -> bool:
        return self.fan_fault or self.pump_fault or self.mister_fault

class EnvironmentModel:
    def __init__(self):
        self.faults = Faults()
        self.active_anomaly: str = "NORMAL"
        self.anomaly_until: Optional[dt.datetime] = None

    def set_anomaly(self, name: str, now: dt.datetime, duration_hours: float = 3.0) -> None:
        self.active_anomaly = name
        self.anomaly_until = now + dt.timedelta(hours=float(duration_hours))

    def clear_anomaly(self) -> None:
        self.active_anomaly = "NORMAL"
        self.anomaly_until = None

    def _anomaly_active(self, now: dt.datetime) -> bool:
        return self.active_anomaly != "NORMAL" and self.anomaly_until is not None and now <= self.anomaly_until

    def outside(self, city: str, season: str, now: dt.datetime) -> Tuple[float, float]:
        base_t, base_h = CITY_SEASON_OUTSIDE.get(city, {}).get(season, (10.0, 65.0))
        h = hour_of_day(now)
        swing = math.sin((h - 6.0) / 24.0 * 2 * math.pi)  # -1..1
        out_t = base_t + 3.2 * swing
        out_h = clamp(base_h - 7.0 * swing, 25.0, 95.0)
        return out_t, out_h

    def apply_tick(
        self,
        values: Dict[str, float],
        actions: Dict[str, bool],
        city_code: str,
        season_code: str,
        now: dt.datetime,
        minutes_per_tick: int,
        rain_forecast: bool,
    ) -> Tuple[Dict[str, float], Dict[str, str]]:
        dt_hours = max(0.01, minutes_per_tick / 60.0)
        out_t, out_h = self.outside(city_code, season_code, now)
        nat_lux = natural_light_lux(season_code, now)

        notes: Dict[str, str] = {}

        # auto clear anomaly
        if self.active_anomaly != "NORMAL" and (self.anomaly_until is None or now > self.anomaly_until):
            self.clear_anomaly()

        temp = float(values["temp"])
        hum = float(values["humidity"])
        lux = float(values["light"])
        soil = float(values["soil"])
        rain = float(values["rain"])

        # forecast indicator
        rain = RAIN_MM_WHEN_FORECAST if rain_forecast else 0.0

        # anomalies (gradual)
        if self._anomaly_active(now):
            a = self.active_anomaly
            if a == "DRY_AIR":
                hum = hum + (28.0 - hum) * clamp(0.30 * dt_hours, 0.0, 0.6)
                notes["anomaly"] = "Dry air event"
            elif a == "HUMID_AIR":
                hum = hum + (85.0 - hum) * clamp(0.22 * dt_hours, 0.0, 0.5)
                notes["anomaly"] = "Humid air event"
            elif a == "LOW_LIGHT":
                nat_lux *= 0.45
                notes["anomaly"] = "Low light (clouds)"
            elif a == "HEAT_WAVE":
                out_t += 8.0
                notes["anomaly"] = "Heat wave"
            elif a == "COLD_SNAP":
                out_t -= 10.0
                notes["anomaly"] = "Cold snap"
            elif a == "DRY_SOIL":
                soil = soil + (22.0 - soil) * clamp(0.22 * dt_hours, 0.0, 0.5)
                notes["anomaly"] = "Dry soil event"
            elif a == "RAIN_FORECAST":
                rain = RAIN_MM_WHEN_FORECAST
                notes["anomaly"] = "Storm forecast"
            elif a == "FAN_FAULT":
                self.faults.fan_fault = True
                notes["anomaly"] = "Fan fault injected"
            elif a == "PUMP_FAULT":
                self.faults.pump_fault = True
                notes["anomaly"] = "Pump fault injected"
            elif a == "MISTER_FAULT":
                self.faults.mister_fault = True
                notes["anomaly"] = "Mister fault injected"

        # greenhouse leakage toward outside
        leak_k = clamp(0.06 * dt_hours, 0.0, 0.12)
        temp = temp + (out_t - temp) * leak_k
        hum = hum + (out_h - hum) * clamp(0.04 * dt_hours, 0.0, 0.10)

        # night floor requirement (demo): keep greenhouse from dropping under ~8-10C
        is_night = now.hour >= 20 or now.hour < 6
        if is_night:
            temp = max(temp, MIN_NIGHT_TEMP_C)

        # natural light convergence
        lux = lux + (nat_lux - lux) * clamp(0.65 * dt_hours, 0.0, 0.85)

        # soil dries slowly
        soil = soil + (soil - 0.8) * (-0.015 * dt_hours)
        soil = clamp(soil, 0.0, 100.0)

        # actions
        if actions.get("Heating", False):
            # smooth steady increase: tuned to reach target in ~1-4h
            temp += clamp(HEATING_RATE_C_PER_HOUR * dt_hours, 0.0, 6.0)
            notes["Heating"] = "Heating ON"

        if actions.get("Ventilation", False) or actions.get("Windows", False):
            vent_eff = 0.55 if actions.get("Windows", False) else 0.40
            if self.faults.fan_fault and actions.get("Ventilation", False):
                vent_eff *= 0.25
                notes["Ventilation"] = "Fan fault reduces effect"
            k = clamp((vent_eff * VENT_LEAK_MULT) * dt_hours, 0.0, 0.75)
            temp = temp + (out_t - temp) * k
            hum = hum + (out_h - hum) * clamp(0.75 * k, 0.0, 0.75)

        if actions.get("Watering", False):
            inc = WATER_SOIL_PCT_PER_HOUR * dt_hours
            if self.faults.pump_fault:
                inc *= 0.25
                notes["Watering"] = "Pump fault limits flow"
            soil = clamp(soil + inc, 0.0, 100.0)
            hum = clamp(hum + 0.8 * dt_hours, 5.0, 98.0)

        if actions.get("Misting", False):
            inc = MIST_HUM_PCT_PER_HOUR * dt_hours
            if self.faults.mister_fault:
                inc *= 0.25
                notes["Misting"] = "Mister fault limits spray"
            hum = clamp(hum + inc, 5.0, 98.0)
            temp = temp - 0.25 * dt_hours

        # lighting: smooth approach to lamp target range
        if actions.get("Lighting", False):
            lamp_target = lerp(LAMP_LIGHT_TARGET_RANGE[0], LAMP_LIGHT_TARGET_RANGE[1], 0.6)
            lux = lux + (lamp_target - lux) * clamp(0.35 * (dt_hours / 0.25), 0.0, 0.7)  # ~1h to approach

        # clamp
        temp = clamp(temp, -20.0, 60.0)
        hum = clamp(hum, 5.0, 98.0)
        lux = clamp(lux, 0.0, 2000.0)

        return {
            "temp": float(temp),
            "humidity": float(hum),
            "light": float(lux),
            "rain": float(rain),
            "soil": float(soil),
        }, notes
