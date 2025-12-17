# logic.py
from __future__ import annotations

import datetime as dt
from typing import Dict, List, Tuple

from config import (
    TEMP_BAND_C, HUM_BAND_PCT, SOIL_BAND_PCT, LIGHT_BAND_LUX,
    TEMP_HYST_C, HUM_HYST_PCT, SOIL_HYST_PCT, LIGHT_HYST_LUX,
    MIN_ON_VENT_SEC, MIN_ON_WIN_SEC, MIN_ON_WATER_SEC, MIN_ON_MIST_SEC, MIN_ON_LIGHT_SEC,
    ALLOW_LIGHT_AT_NIGHT,
)

class GreenhouseLogic:
    """
    Strict (hysteresis + minimum ON time) for:
      - Ventilation
      - Windows
      - Watering
      - Misting
      - Lighting

    Heating is NOT strict:
      - ON if temp < temp_target - TEMP_BAND_C
      - OFF if temp >= temp_target + TEMP_HYST_C (small hysteresis)
    """

    def __init__(self):
        self.actions = self.blank_actions()
        self._on_since: Dict[str, dt.datetime | None] = {k: None for k in self.actions.keys()}

    @staticmethod
    def blank_actions() -> Dict[str, bool]:
        return {
            "Heating": False,
            "Ventilation": False,
            "Windows": False,
            "Watering": False,
            "Misting": False,
            "Lighting": False,
            "RainProtection": False,
            "Alarm": False,
        }

    @staticmethod
    def is_night(now: dt.datetime) -> bool:
        return now.hour >= 20 or now.hour < 6

    def _min_on_ok(self, key: str, now: dt.datetime, min_sec: int) -> bool:
        started = self._on_since.get(key)
        if started is None:
            return True
        return (now - started).total_seconds() >= float(min_sec)

    def _set_act(self, act: Dict[str, bool], key: str, value: bool, now: dt.datetime):
        prev = self.actions.get(key, False)
        act[key] = value
        if value and not prev:
            self._on_since[key] = now
        if (not value) and prev:
            self._on_since[key] = None

    def compute(
        self,
        values: Dict[str, float],
        targets: Dict[str, float],
        rain_forecast: bool,
        faults: Dict[str, bool],
        now: dt.datetime,
    ) -> Tuple[Dict[str, bool], List[str]]:
        act = dict(self.actions)
        reasons: List[str] = []

        temp = float(values["temp"])
        hum = float(values["humidity"])
        light = float(values["light"])
        soil = float(values["soil"])

        t_tgt = float(targets["temp_target"])
        h_tgt = float(targets["hum_target"])
        l_min = float(targets["light_min"])
        s_min = float(targets["soil_min"])

        night = self.is_night(now)

        # -------------------------
        # Heating (NOT strict)
        # -------------------------
        heat_on = act["Heating"]
        if temp < (t_tgt - TEMP_BAND_C):
            heat_on = True
            reasons.append(f"Temp low ({temp:.1f} < {t_tgt - TEMP_BAND_C:.1f})")
        elif temp >= (t_tgt + TEMP_HYST_C):
            heat_on = False
        act["Heating"] = heat_on

        # -------------------------
        # STRICT: Ventilation
        # ON: temp > tgt + band OR hum > tgt + band
        # OFF: both below (tgt + band - hyst) AND min_on satisfied
        # -------------------------
        vent_on = act["Ventilation"]
        want_vent = (temp > (t_tgt + TEMP_BAND_C)) or (hum > (h_tgt + HUM_BAND_PCT))
        if want_vent:
            vent_on = True
            if temp > (t_tgt + TEMP_BAND_C):
                reasons.append(f"Temp high ({temp:.1f} > {t_tgt + TEMP_BAND_C:.1f})")
            if hum > (h_tgt + HUM_BAND_PCT):
                reasons.append(f"Humidity high ({hum:.1f} > {h_tgt + HUM_BAND_PCT:.1f})")
        else:
            ok_temp = temp <= (t_tgt + TEMP_BAND_C - TEMP_HYST_C)
            ok_hum = hum <= (h_tgt + HUM_BAND_PCT - HUM_HYST_PCT)
            if ok_temp and ok_hum and self._min_on_ok("Ventilation", now, MIN_ON_VENT_SEC):
                vent_on = False
        self._set_act(act, "Ventilation", vent_on, now)

        # -------------------------
        # STRICT: Windows (open with vent need, but close on rain forecast)
        # -------------------------
        win_on = act["Windows"]
        if rain_forecast:
            act["RainProtection"] = True
            if win_on and self._min_on_ok("Windows", now, MIN_ON_WIN_SEC):
                win_on = False
            else:
                win_on = False
            reasons.append("Rain forecast -> close windows")
        else:
            act["RainProtection"] = False
            want_open = want_vent
            if want_open:
                win_on = True
            else:
                ok_temp = temp <= (t_tgt + TEMP_BAND_C - TEMP_HYST_C)
                ok_hum = hum <= (h_tgt + HUM_BAND_PCT - HUM_HYST_PCT)
                if ok_temp and ok_hum and self._min_on_ok("Windows", now, MIN_ON_WIN_SEC):
                    win_on = False
        self._set_act(act, "Windows", win_on, now)

        # Night policy: if night and no real need, allow closing faster (still respect min_on)
        if night and not want_vent:
            if self._min_on_ok("Ventilation", now, MIN_ON_VENT_SEC):
                self._set_act(act, "Ventilation", False, now)
            if self._min_on_ok("Windows", now, MIN_ON_WIN_SEC):
                self._set_act(act, "Windows", False, now)

        # -------------------------
        # STRICT: Watering
        # ON: soil < soil_min
        # OFF: soil >= soil_min + band AND min_on ok
        # -------------------------
        water_on = act["Watering"]
        if soil < s_min:
            water_on = True
            reasons.append(f"Soil low ({soil:.1f} < {s_min:.1f})")
        else:
            if soil >= (s_min + SOIL_BAND_PCT) and self._min_on_ok("Watering", now, MIN_ON_WATER_SEC):
                water_on = False
        self._set_act(act, "Watering", water_on, now)

        # -------------------------
        # STRICT: Misting
        # ON: humidity < hum_target - band (low)
        # OFF: humidity >= (hum_target - band + hyst) AND min_on ok
        # -------------------------
        mist_on = act["Misting"]
        low_thr = h_tgt - HUM_BAND_PCT
        if hum < low_thr:
            mist_on = True
            reasons.append(f"Humidity low ({hum:.1f} < {low_thr:.1f})")
        else:
            if hum >= (low_thr + HUM_HYST_PCT) and self._min_on_ok("Misting", now, MIN_ON_MIST_SEC):
                mist_on = False
        self._set_act(act, "Misting", mist_on, now)

        # -------------------------
        # STRICT: Lighting
        # ON: light < light_min (and allowed)
        # OFF: light >= light_min + band AND min_on ok
        # -------------------------
        light_on = act["Lighting"]
        allow_now = (not night) or ALLOW_LIGHT_AT_NIGHT
        if allow_now and (light < l_min):
            light_on = True
            reasons.append(f"Light low ({light:.0f} < {l_min:.0f})")
        else:
            if light >= (l_min + LIGHT_BAND_LUX) and self._min_on_ok("Lighting", now, MIN_ON_LIGHT_SEC):
                light_on = False
        self._set_act(act, "Lighting", light_on, now)

        # Fault hints (do not force actions here, only reasons)
        if faults.get("fan_fault"):
            reasons.append("FAULT: fan_fault")
        if faults.get("pump_fault"):
            reasons.append("FAULT: pump_fault")
        if faults.get("mister_fault"):
            reasons.append("FAULT: mister_fault")

        # Alarm if any “real” reasons (excluding pure faults spam is ok too)
        act["Alarm"] = bool(reasons)

        self.actions = dict(act)
        return act, reasons
