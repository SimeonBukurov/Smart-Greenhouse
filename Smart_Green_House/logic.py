import datetime
from typing import Dict, List, Tuple

from config import LIGHT_MIN, SOIL_MIN, TEMP_HIGH, TEMP_LOW, HUMIDITY_LOW, HUMIDITY_HIGH

class GreenhouseLogic:
    """
    Stateful logic with latches:
    - Heating stays ON at least ~2 hours once triggered (unless overheating)
    - Watering / Lighting / Misting have shorter latches for realism
    """
    def __init__(self):
        self._latch_until: Dict[str, datetime.datetime] = {}

    @staticmethod
    def is_night_time(now: datetime.datetime) -> bool:
        return now.hour >= 20 or now.hour < 6

    def _latched(self, key: str, now: datetime.datetime) -> bool:
        t = self._latch_until.get(key)
        return t is not None and now < t

    def _latch(self, key: str, now: datetime.datetime, minutes: int) -> None:
        until = now + datetime.timedelta(minutes=int(minutes))
        prev = self._latch_until.get(key)
        if prev is None or until > prev:
            self._latch_until[key] = until

    def apply_rules(
        self,
        temp: float,
        humidity: float,
        light: float,
        rain_forecast: bool,
        soil_moisture: float,
        now: datetime.datetime,
    ) -> Tuple[Dict[str, bool], List[str]]:

        act = {
            "Heating": False,
            "Ventilation": False,
            "Windows": False,
            "Watering": False,
            "Misting": False,
            "Lighting": False,
            "RainProtection": False,
            "Alarm": False,
        }
        reasons: List[str] = []

        # ---------------- LIGHT: ALWAYS turn on if lux < LIGHT_MIN
        if light < LIGHT_MIN:
            act["Lighting"] = True
            self._latch("Lighting", now, minutes=30)
            reasons.append(f"Low light ({light:.0f} lux)")

        # Apply latch
        if self._latched("Lighting", now):
            act["Lighting"] = True

        # ---------------- TEMP
        if temp < TEMP_LOW:
            act["Heating"] = True
            self._latch("Heating", now, minutes=120)  # ~2 hours minimum run
            reasons.append(f"Low temp ({temp:.1f}°C)")

        # Keep heating latched unless overheating
        if self._latched("Heating", now) and temp < (TEMP_HIGH - 1.0):
            act["Heating"] = True

        if temp > TEMP_HIGH:
            act["Ventilation"] = True
            act["Windows"] = True
            reasons.append(f"High temp ({temp:.1f}°C)")

        # ---------------- HUMIDITY
        if humidity < HUMIDITY_LOW:
            act["Misting"] = True
            self._latch("Misting", now, minutes=20)
            reasons.append(f"Low humidity ({humidity:.1f}%)")

        if self._latched("Misting", now):
            act["Misting"] = True

        if humidity > HUMIDITY_HIGH:
            act["Ventilation"] = True
            act["Windows"] = True
            reasons.append(f"High humidity ({humidity:.1f}%)")

        # ---------------- SOIL
        if soil_moisture < SOIL_MIN:
            act["Watering"] = True
            self._latch("Watering", now, minutes=30)
            reasons.append(f"Low soil ({soil_moisture:.1f}%)")

        if self._latched("Watering", now):
            act["Watering"] = True

        # ---------------- RAIN forecast
        if rain_forecast:
            act["RainProtection"] = True
            act["Windows"] = False
            reasons.append("Rain forecast")

        # Night: keep windows closed unless ventilation needed
        if self.is_night_time(now) and not act["Ventilation"]:
            act["Windows"] = False

        # Alarm only for real problems (not “Heating normal work”):
        # alarm if temp is very high/low or humidity extreme or soil critical
        if temp < (TEMP_LOW - 3) or temp > (TEMP_HIGH + 3) or humidity < 30 or humidity > 90 or soil_moisture < (SOIL_MIN - 10):
            act["Alarm"] = True

        return act, reasons
