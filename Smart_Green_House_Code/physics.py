# physics.py
import random
from dataclasses import dataclass
from typing import Dict

from config import (
    HEAT_RATE_C_PER_MIN, VENT_COOL_RATE_C_PER_MIN,
    WATER_SOIL_RATE_PER_MIN, MIST_HUM_RATE_PER_MIN,
    VENT_HUM_DROP_PER_MIN, LAMP_LUX_RATE_PER_MIN,
    LIGHT_MIN
)

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

@dataclass
class Ambient:
    temp: float
    humidity: float
    light_day: float
    light_night: float
    is_day: bool

class GreenhousePhysics:
    """
    Realistic-ish dynamics:
    - Environment pulls values slowly toward ambient.
    - Actuators modify rates.
    - Light can change fast (lamps), soil/humidity slower.
    """

    def __init__(self):
        # internal inertia
        self._last = None

    def step(self, state: Dict[str, float], actions: Dict[str, bool], ambient: Ambient, dt_min: float) -> Dict[str, float]:
        v = dict(state)

        # --- ambient targets ---
        amb_light = ambient.light_day if ambient.is_day else ambient.light_night

        # Drift toward ambient (small)
        # Temperature inertia
        v["temp"] += (ambient.temp - v["temp"]) * (0.01 * dt_min)
        # Humidity inertia
        v["humidity"] += (ambient.humidity - v["humidity"]) * (0.01 * dt_min)
        # Light inertia toward ambient
        v["light"] += (amb_light - v["light"]) * (0.03 * dt_min)

        # Soil dries slowly by default
        v["soil"] -= 0.02 * dt_min

        # --- actuator effects ---
        if actions.get("Heating"):
            # heats faster when far from ambient/target; keep stable
            v["temp"] += HEAT_RATE_C_PER_MIN * dt_min

        if actions.get("Ventilation") or actions.get("Windows"):
            # ventilation cools and reduces humidity
            v["temp"] -= VENT_COOL_RATE_C_PER_MIN * dt_min
            v["humidity"] -= VENT_HUM_DROP_PER_MIN * dt_min

        if actions.get("Watering"):
            # soil increases slowly, humidity a bit
            v["soil"] += WATER_SOIL_RATE_PER_MIN * dt_min
            v["humidity"] += 0.05 * dt_min

        if actions.get("Misting"):
            v["humidity"] += MIST_HUM_RATE_PER_MIN * dt_min
            # misting can cool slightly
            v["temp"] -= 0.02 * dt_min

        if actions.get("Lighting"):
            # lamps push toward at least LIGHT_MIN quickly, but not instant to max
            # add rate + extra boost if below LIGHT_MIN
            boost = 2.0 if v["light"] < LIGHT_MIN else 1.0
            v["light"] += LAMP_LUX_RATE_PER_MIN * boost * dt_min

        # rain in this model is mostly “outside”; keep near 0 unless scenario injects it elsewhere
        v["rain"] = clamp(v.get("rain", 0.0), 0.0, 20.0)

        # --- noise ---
        v["temp"] += random.uniform(-0.02, 0.02) * dt_min
        v["humidity"] += random.uniform(-0.05, 0.05) * dt_min
        v["light"] += random.uniform(-0.8, 0.8) * dt_min
        v["soil"] += random.uniform(-0.03, 0.03) * dt_min

        # --- clamp to reasonable ranges ---
        v["temp"] = clamp(v["temp"], -20.0, 60.0)
        v["humidity"] = clamp(v["humidity"], 0.0, 100.0)
        v["light"] = clamp(v["light"], 0.0, 2500.0)
        v["soil"] = clamp(v["soil"], 0.0, 100.0)

        return v
