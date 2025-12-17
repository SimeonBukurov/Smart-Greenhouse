# gui.py
from __future__ import annotations

import matplotlib
matplotlib.use("TkAgg")

import datetime as dt
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates

from config import (
    DB_NAME, AUTO_INSERT_INTERVAL_SEC,
    UI_FPS, GRAPH_REFRESH_SEC,
    CITIES, SEASONS, PLANTS,
    DEFAULT_CITY_CODE, DEFAULT_SEASON_CODE, DEFAULT_PLANT_CODE,
    DEFAULT_VALUES,
    ANOMALIES, ANOMALY_LABELS,
    GRAPH_RANGES,
    MAINTENANCE_THRESHOLDS_H,
    ACTION_LABELS,
    I18N,
)
from database import DatabaseManager
from simulator import EnvironmentModel
from logic import GreenhouseLogic
from logger import EventLogger


def fmt_dt(ts: dt.datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%S")

def parse_ts(ts_str: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts_str)


@dataclass
class GraphWindow:
    top: ctk.CTkToplevel
    fig: Figure
    ax: object
    canvas: FigureCanvasTkAgg
    sensor_key: str
    title: str


class CollapsibleSection(ctk.CTkFrame):
    def __init__(self, master, title: str, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._open = ctk.BooleanVar(value=True)

        self.header = ctk.CTkFrame(self, corner_radius=10)
        self.header.pack(fill="x", pady=(6, 4))

        self.btn = ctk.CTkButton(
            self.header, text=title, anchor="w", height=32,
            command=self.toggle
        )
        self.btn.pack(fill="x", padx=6, pady=6)

        self.body = ctk.CTkFrame(self, corner_radius=10)
        self.body.pack(fill="x", padx=2, pady=(0, 6))

    def set_title(self, text: str) -> None:
        try:
            self.btn.configure(text=text)
        except Exception:
            pass

    def toggle(self):
        if self._open.get():
            self.body.pack_forget()
            self._open.set(False)
        else:
            self.body.pack(fill="x", padx=2, pady=(0, 6))
            self._open.set(True)


class SmartGreenhouseApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.logger = EventLogger()

        # i18n
        self.lang_var = ctk.StringVar(value="bg")
        self._i18n_widgets: Dict[str, List[Tuple[object, str]]] = {}

        self.title(self._t("app_title"))
        self.geometry("1400x800")
        self.minsize(1200, 700)

        # core
        self.db = DatabaseManager(DB_NAME)
        self.model = EnvironmentModel()
        self.logic = GreenhouseLogic()

        # state
        self.auto_mode = ctk.BooleanVar(value=True)
        self.sim_time_enabled = ctk.BooleanVar(value=True)
        self.minutes_per_tick = ctk.IntVar(value=15)
        self.tick_interval_sec = ctk.DoubleVar(value=AUTO_INSERT_INTERVAL_SEC)

        self.manual_override = ctk.BooleanVar(value=False)
        self.rain_forecast = ctk.BooleanVar(value=False)
        self.enable_random_faults = ctk.BooleanVar(value=False)

        # selections (store codes)
        self.city_code = ctk.StringVar(value=DEFAULT_CITY_CODE)
        self.season_code = ctk.StringVar(value=DEFAULT_SEASON_CODE)
        self.plant_code = ctk.StringVar(value=DEFAULT_PLANT_CODE)

        # anomalies: store CODE, but menu shows labels
        self.anomaly_code = ctk.StringVar(value="NORMAL")
        self.graph_range_var = ctk.StringVar(value="last7")

        # simulated clock
        self.sim_clock: dt.datetime = dt.datetime.now().replace(second=0, microsecond=0)

        # values
        self.values: Dict[str, float] = dict(DEFAULT_VALUES)

        # smooth UI values
        self.target_values: Dict[str, float] = dict(self.values)
        self.display_values: Dict[str, float] = dict(self.values)
        self._last_ui_ts = dt.datetime.now()

        # last computed
        self._latest_actions: Dict[str, bool] = GreenhouseLogic.blank_actions()
        self._latest_targets: Dict[str, float] = {"temp_target": 0, "hum_target": 0, "light_min": 0, "soil_min": 0}
        self._latest_reasons: List[str] = []
        self._latest_notes: Dict[str, str] = {}

        # maintenance
        self.runtime_h: Dict[str, float] = {k: 0.0 for k in MAINTENANCE_THRESHOLDS_H.keys()}
        self._maintenance_warnings: List[str] = []

        # ui vars
        self.diagnostics_text = ctk.StringVar(value=self._t("no_warnings"))
        self.status_line = ctk.StringVar(value="")
        self.clock_line = ctk.StringVar(value="")

        # graph windows
        self._graph_windows: Dict[str, GraphWindow] = {}
        self._last_graph_refresh_ts = dt.datetime.min

        # build UI
        self._build_layout()
        self._apply_language()

        # start loops
        self._ui_loop()
        self._tick_loop()

    # ---------------- i18n ----------------
    def _t(self, key: str) -> str:
        lang = self.lang_var.get()
        return I18N.get(lang, I18N["bg"]).get(key, key)

    def _bind_i18n(self, key: str, widget, option: str):
        self._i18n_widgets.setdefault(key, []).append((widget, option))

    def _apply_language(self):
        self.title(self._t("app_title"))
        for key, items in self._i18n_widgets.items():
            txt = self._t(key)
            for w, opt in items:
                try:
                    w.configure(**{opt: txt})
                except Exception:
                    pass

        # update section titles
        self.sec_lang.set_title(self._t("lang"))
        self.sec_controls.set_title(self._t("controls"))
        self.sec_profiles.set_title(self._t("profiles"))
        self.sec_time.set_title(self._t("time_demo"))
        self.sec_anom.set_title(self._t("scenario"))
        self.sec_diag.set_title(self._t("diagnostics"))
        self.sec_manual.set_title(self._t("manual"))
        self.sec_graphs.set_title(self._t("graphs"))

        # update dropdown labels
        self._refresh_city_menu()
        self._refresh_season_menu()
        self._refresh_plant_menu()
        self._refresh_anomaly_menu()

        # update action tile titles
        for k, refs in self.action_tiles.items():
            title = ACTION_LABELS[k]["bg"] if self.lang_var.get() == "bg" else ACTION_LABELS[k]["en"]
            refs["title"].configure(text=title)

        self._update_targets_line()

    # ---------------- layout ----------------
    def _build_layout(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.left = ctk.CTkScrollableFrame(self, width=360, corner_radius=14)
        self.left.grid(row=0, column=0, sticky="nsw", padx=10, pady=10)

        self.right = ctk.CTkFrame(self, corner_radius=14)
        self.right.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        self.right.grid_columnconfigure(0, weight=1)
        self.right.grid_rowconfigure(2, weight=1)

        self._build_left()
        self._build_right()

    def _build_left(self):
        p = self.left

        # Language
        self.sec_lang = CollapsibleSection(p, "Език")
        self.sec_lang.pack(fill="x", padx=6, pady=(6, 0))
        body = self.sec_lang.body

        self.lang_menu = ctk.CTkOptionMenu(body, values=["bg", "en"], variable=self.lang_var,
                                           command=lambda _: self._apply_language())
        self.lang_menu.pack(fill="x", padx=10, pady=(10, 10))

        # Controls
        self.sec_controls = CollapsibleSection(p, "Контроли")
        self.sec_controls.pack(fill="x", padx=6, pady=(6, 0))
        b = self.sec_controls.body

        sw = ctk.CTkSwitch(b, text=self._t("auto_mode"), variable=self.auto_mode)
        sw.pack(anchor="w", padx=10, pady=(10, 6))
        self._bind_i18n("auto_mode", sw, "text")

        row = ctk.CTkFrame(b, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 10))
        lbl = ctk.CTkLabel(row, text=self._t("interval"))
        lbl.pack(side="left")
        self._bind_i18n("interval", lbl, "text")

        self.interval_entry = ctk.CTkEntry(row, width=90)
        self.interval_entry.insert(0, str(self.tick_interval_sec.get()))
        self.interval_entry.pack(side="left", padx=8)

        btn = ctk.CTkButton(row, text=self._t("apply"), width=80, command=self._apply_interval)
        btn.pack(side="left")
        self._bind_i18n("apply", btn, "text")

        fs = ctk.CTkButton(b, text=self._t("fullscreen"), command=self._toggle_fullscreen)
        fs.pack(fill="x", padx=10, pady=(0, 10))
        self._bind_i18n("fullscreen", fs, "text")

        # Profiles
        self.sec_profiles = CollapsibleSection(p, "Профили")
        self.sec_profiles.pack(fill="x", padx=6, pady=(6, 0))
        b = self.sec_profiles.body

        # city
        crow = ctk.CTkFrame(b, fg_color="transparent")
        crow.pack(fill="x", padx=10, pady=(10, 6))
        cl = ctk.CTkLabel(crow, text=self._t("city"))
        cl.pack(side="left")
        self._bind_i18n("city", cl, "text")

        self.city_menu = ctk.CTkOptionMenu(crow, values=["..."], command=self._on_city_select)
        self.city_menu.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # season
        srow = ctk.CTkFrame(b, fg_color="transparent")
        srow.pack(fill="x", padx=10, pady=(0, 6))
        sl = ctk.CTkLabel(srow, text=self._t("season"))
        sl.pack(side="left")
        self._bind_i18n("season", sl, "text")

        self.season_menu = ctk.CTkOptionMenu(srow, values=["..."], command=self._on_season_select)
        self.season_menu.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # plant
        prow = ctk.CTkFrame(b, fg_color="transparent")
        prow.pack(fill="x", padx=10, pady=(0, 6))
        pl = ctk.CTkLabel(prow, text=self._t("plant"))
        pl.pack(side="left")
        self._bind_i18n("plant", pl, "text")

        self.plant_menu = ctk.CTkOptionMenu(prow, values=["..."], command=self._on_plant_select)
        self.plant_menu.pack(side="right", fill="x", expand=True, padx=(10, 0))

        self.targets_line_lbl = ctk.CTkLabel(b, text="", font=("Roboto", 11), wraplength=320, justify="left")
        self.targets_line_lbl.pack(anchor="w", padx=10, pady=(6, 10))

        # Time
        self.sec_time = CollapsibleSection(p, "Време (Demo)")
        self.sec_time.pack(fill="x", padx=6, pady=(6, 0))
        b = self.sec_time.body

        st = ctk.CTkSwitch(b, text=self._t("sim_time"), variable=self.sim_time_enabled)
        st.pack(anchor="w", padx=10, pady=(10, 6))
        self._bind_i18n("sim_time", st, "text")

        trow = ctk.CTkFrame(b, fg_color="transparent")
        trow.pack(fill="x", padx=10, pady=(0, 6))
        tl = ctk.CTkLabel(trow, text=self._t("minutes_tick"))
        tl.pack(side="left")
        self._bind_i18n("minutes_tick", tl, "text")

        self.tick_entry = ctk.CTkEntry(trow, width=90)
        self.tick_entry.insert(0, str(self.minutes_per_tick.get()))
        self.tick_entry.pack(side="left", padx=8)

        tb = ctk.CTkButton(trow, text=self._t("set"), width=80, command=self._apply_minutes_per_tick)
        tb.pack(side="left")
        self._bind_i18n("set", tb, "text")

        rn = ctk.CTkButton(b, text=self._t("reset_now"), command=self._reset_clock_now)
        rn.pack(fill="x", padx=10, pady=(0, 10))
        self._bind_i18n("reset_now", rn, "text")

        self.clock_label = ctk.CTkLabel(b, textvariable=self.clock_line, font=("Roboto", 11))
        self.clock_label.pack(anchor="w", padx=10, pady=(0, 10))

        # Anomalies
        self.sec_anom = CollapsibleSection(p, "Аномалии")
        self.sec_anom.pack(fill="x", padx=6, pady=(6, 0))
        b = self.sec_anom.body

        self.anomaly_menu = ctk.CTkOptionMenu(b, values=["..."], command=self._on_anomaly_select)
        self.anomaly_menu.pack(fill="x", padx=10, pady=(10, 6))

        ab = ctk.CTkButton(b, text=self._t("apply"), command=self._apply_anomaly)
        ab.pack(fill="x", padx=10, pady=(0, 10))
        self._bind_i18n("apply", ab, "text")

        # Diagnostics + Log
        self.sec_diag = CollapsibleSection(p, "Диагностика")
        self.sec_diag.pack(fill="x", padx=6, pady=(6, 0))
        b = self.sec_diag.body

        ef = ctk.CTkSwitch(b, text=self._t("enable_faults"), variable=self.enable_random_faults)
        ef.pack(anchor="w", padx=10, pady=(10, 6))
        self._bind_i18n("enable_faults", ef, "text")

        self.diag_label = ctk.CTkLabel(b, textvariable=self.diagnostics_text, font=("Roboto", 11),
                                       wraplength=320, justify="left")
        self.diag_label.pack(anchor="w", padx=10, pady=(0, 10))

        ol = ctk.CTkButton(b, text=self._t("open_log"), command=self._open_log_window)
        ol.pack(fill="x", padx=10, pady=(0, 10))
        self._bind_i18n("open_log", ol, "text")

        # Manual inputs (collapsed by default)
        self.sec_manual = CollapsibleSection(p, "Ръчни входове")
        self.sec_manual.pack(fill="x", padx=6, pady=(6, 0))
        self.sec_manual.toggle()  # collapse initially
        b = self.sec_manual.body

        mo = ctk.CTkSwitch(b, text=self._t("manual_enable"), variable=self.manual_override,
                          command=self._apply_manual_enable)
        mo.pack(anchor="w", padx=10, pady=(10, 6))
        self._bind_i18n("manual_enable", mo, "text")

        self.sliders: Dict[str, ctk.CTkSlider] = {}
        self.slider_labels: Dict[str, ctk.CTkLabel] = {}
        self._add_slider(b, "temp", "Temperature (°C)", -10, 55, self.values["temp"])
        self._add_slider(b, "humidity", "Humidity (%)", 5, 98, self.values["humidity"])
        self._add_slider(b, "light", "Light (lux)", 0, 2000, self.values["light"])
        self._add_slider(b, "soil", "Soil moisture (%)", 0, 100, self.values["soil"])

        rf = ctk.CTkCheckBox(b, text="Rain forecast", variable=self.rain_forecast)
        rf.pack(anchor="w", padx=10, pady=(6, 10))

        # Graphs
        self.sec_graphs = CollapsibleSection(p, "Графики")
        self.sec_graphs.pack(fill="x", padx=6, pady=(6, 10))
        b = self.sec_graphs.body

        grow = ctk.CTkFrame(b, fg_color="transparent")
        grow.pack(fill="x", padx=10, pady=(10, 6))
        grl = ctk.CTkLabel(grow, text=self._t("range"))
        grl.pack(side="left")
        self._bind_i18n("range", grl, "text")

        ctk.CTkOptionMenu(grow, values=GRAPH_RANGES, variable=self.graph_range_var).pack(side="left", padx=8, fill="x", expand=True)

        b1 = ctk.CTkButton(b, text=self._t("show_temp"), command=lambda: self.show_graph("temp", "Temperature (°C)"))
        b2 = ctk.CTkButton(b, text=self._t("show_hum"), command=lambda: self.show_graph("humidity", "Humidity (%)"))
        b3 = ctk.CTkButton(b, text=self._t("show_light"), command=lambda: self.show_graph("light", "Light (lux)"))
        b4 = ctk.CTkButton(b, text=self._t("show_soil"), command=lambda: self.show_graph("soil", "Soil moisture (%)"))
        b5 = ctk.CTkButton(b, text=self._t("show_rain"), command=lambda: self.show_graph("rain", "Rain (mm)"))
        for key, btn in [("show_temp", b1), ("show_hum", b2), ("show_light", b3), ("show_soil", b4), ("show_rain", b5)]:
            btn.pack(fill="x", padx=10, pady=4)
            self._bind_i18n(key, btn, "text")

        # init menus after creation
        self._refresh_city_menu()
        self._refresh_season_menu()
        self._refresh_plant_menu()
        self._refresh_anomaly_menu()
        self._apply_manual_enable()

    def _build_right(self):
        title = ctk.CTkLabel(self.right, text=self._t("status_title"), font=("Roboto", 22, "bold"))
        title.grid(row=0, column=0, sticky="n", pady=(14, 8))
        self._bind_i18n("status_title", title, "text")

        sensor_strip = ctk.CTkFrame(self.right, corner_radius=14)
        sensor_strip.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
        for c in range(5):
            sensor_strip.grid_columnconfigure(c, weight=1)

        self.sensor_cards: Dict[str, ctk.CTkLabel] = {}
        self._make_sensor_card(sensor_strip, 0, "🌡 Temp", "temp", "°C")
        self._make_sensor_card(sensor_strip, 1, "💧 Hum", "humidity", "%")
        self._make_sensor_card(sensor_strip, 2, "💡 Light", "light", "lux")
        self._make_sensor_card(sensor_strip, 3, "🌱 Soil", "soil", "%")
        self._make_sensor_card(sensor_strip, 4, "🌧 Rain", "rain", "mm")

        grid = ctk.CTkFrame(self.right, corner_radius=14)
        grid.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 10))
        for r in range(3):
            grid.grid_rowconfigure(r, weight=1)
        for c in range(3):
            grid.grid_columnconfigure(c, weight=1)

        self.action_tiles: Dict[str, Dict[str, object]] = {}

        self._make_action_tile(grid, 0, 0, "Heating", off="#081a3a", on="#d32f2f")
        self._make_action_tile(grid, 0, 1, "Ventilation", off="#081a3a", on="#00acc1")
        self._make_action_tile(grid, 0, 2, "Windows", off="#081a3a", on="#ffb300")

        self._make_action_tile(grid, 1, 0, "Watering", off="#081a3a", on="#1e88e5")
        self._make_action_tile(grid, 1, 1, "Misting", off="#081a3a", on="#8e24aa")
        self._make_action_tile(grid, 1, 2, "Lighting", off="#081a3a", on="#fdd835")

        self._make_action_tile(grid, 2, 0, "RainProtection", off="#081a3a", on="#3949ab")
        self._make_action_tile(grid, 2, 1, "Alarm", off="#081a3a", on="#b71c1c")

        self.status_label = ctk.CTkLabel(self.right, textvariable=self.status_line, font=("Roboto", 11))
        self.status_label.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 10))

    def _make_sensor_card(self, parent, col: int, title: str, key: str, unit: str):
        card = ctk.CTkFrame(parent, corner_radius=14)
        card.grid(row=0, column=col, sticky="ew", padx=8, pady=8)
        ctk.CTkLabel(card, text=title, font=("Roboto", 12, "bold")).pack(pady=(10, 2))
        lbl = ctk.CTkLabel(card, text=f"-- {unit}", font=("Roboto", 13))
        lbl.pack(pady=(0, 10))
        self.sensor_cards[key] = lbl

    def _make_action_tile(self, parent, r: int, c: int, key: str, off: str, on: str):
        tile = ctk.CTkFrame(parent, corner_radius=18, fg_color=off)
        tile.grid(row=r, column=c, sticky="nsew", padx=10, pady=10)

        emoji = ACTION_LABELS[key]["emoji"]
        icon = ctk.CTkLabel(tile, text=emoji, font=("Segoe UI Emoji", 28))
        icon.pack(pady=(18, 6))

        title_text = ACTION_LABELS[key]["bg"] if self.lang_var.get() == "bg" else ACTION_LABELS[key]["en"]
        title = ctk.CTkLabel(tile, text=title_text, font=("Roboto", 14, "bold"))
        title.pack(pady=(0, 4))

        state = ctk.CTkLabel(tile, text="OFF", font=("Roboto", 12))
        state.pack(pady=(0, 18))

        self.action_tiles[key] = {"frame": tile, "title": title, "state": state, "off": off, "on": on}

    # ---------------- menus (codes<->labels) ----------------
    def _refresh_city_menu(self):
        lang = self.lang_var.get()
        values = [c[lang] for c in CITIES]
        current_code = self.city_code.get()
        current_label = next((c[lang] for c in CITIES if c["code"] == current_code), values[0])
        self.city_menu.configure(values=values)
        self.city_menu.set(current_label)

    def _on_city_select(self, label: str):
        lang = self.lang_var.get()
        code = next((c["code"] for c in CITIES if c[lang] == label), DEFAULT_CITY_CODE)
        self.city_code.set(code)

    def _refresh_season_menu(self):
        lang = self.lang_var.get()
        values = [s[lang] for s in SEASONS]
        current_code = self.season_code.get()
        current_label = next((s[lang] for s in SEASONS if s["code"] == current_code), values[0])
        self.season_menu.configure(values=values)
        self.season_menu.set(current_label)

    def _on_season_select(self, label: str):
        lang = self.lang_var.get()
        code = next((s["code"] for s in SEASONS if s[lang] == label), DEFAULT_SEASON_CODE)
        self.season_code.set(code)

    def _refresh_plant_menu(self):
        lang = self.lang_var.get()
        values = [p[lang] for p in PLANTS]
        current_code = self.plant_code.get()
        current_label = next((p[lang] for p in PLANTS if p["code"] == current_code), values[0])
        self.plant_menu.configure(values=values)
        self.plant_menu.set(current_label)
        self._update_targets_line()

    def _on_plant_select(self, label: str):
        lang = self.lang_var.get()
        code = next((p["code"] for p in PLANTS if p[lang] == label), DEFAULT_PLANT_CODE)
        self.plant_code.set(code)
        self._update_targets_line()

    def _refresh_anomaly_menu(self):
        lang = self.lang_var.get()
        values = [ANOMALY_LABELS[a][lang] for a in ANOMALIES]
        cur_code = self.anomaly_code.get()
        cur_label = ANOMALY_LABELS.get(cur_code, ANOMALY_LABELS["NORMAL"])[lang]
        self.anomaly_menu.configure(values=values)
        self.anomaly_menu.set(cur_label)

    def _on_anomaly_select(self, label: str):
        lang = self.lang_var.get()
        code = next((a for a in ANOMALIES if ANOMALY_LABELS[a][lang] == label), "NORMAL")
        self.anomaly_code.set(code)

    # ---------------- manual sliders ----------------
    def _add_slider(self, parent, key: str, title: str, vmin: float, vmax: float, default: float):
        ctk.CTkLabel(parent, text=title, font=("Roboto", 12, "bold")).pack(anchor="w", padx=10, pady=(6, 0))
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 4))

        s = ctk.CTkSlider(row, from_=vmin, to=vmax, number_of_steps=200,
                          command=lambda val, k=key: self._on_slider(k, val))
        s.set(default)
        s.pack(side="left", fill="x", expand=True)

        lbl = ctk.CTkLabel(row, text=f"{default:.1f}", width=70)
        lbl.pack(side="left", padx=8)

        self.sliders[key] = s
        self.slider_labels[key] = lbl

    def _apply_manual_enable(self):
        enabled = bool(self.manual_override.get())
        for s in self.sliders.values():
            try:
                s.configure(state="normal" if enabled else "disabled")
            except Exception:
                pass

    def _on_slider(self, key: str, val: float):
        v = float(val)
        self.slider_labels[key].configure(text=f"{v:.1f}")

        # IMPORTANT FIX:
        # sliders only change real model values when manual_override is ON.
        if not self.manual_override.get():
            return

        self.values[key] = v
        self.target_values[key] = v
        self.display_values[key] = v

    # ---------------- callbacks ----------------
    def _apply_interval(self):
        try:
            v = float(self.interval_entry.get().strip())
            v = max(0.2, min(10.0, v))
            self.tick_interval_sec.set(v)
            self.interval_entry.delete(0, "end")
            self.interval_entry.insert(0, str(v))
        except Exception:
            pass

    def _apply_minutes_per_tick(self):
        try:
            v = int(self.tick_entry.get().strip())
            v = max(1, min(120, v))
            self.minutes_per_tick.set(v)
            self.tick_entry.delete(0, "end")
            self.tick_entry.insert(0, str(v))
        except Exception:
            pass

    def _reset_clock_now(self):
        self.sim_clock = dt.datetime.now().replace(second=0, microsecond=0)

    def _toggle_fullscreen(self):
        self.attributes("-fullscreen", not bool(self.attributes("-fullscreen")))

    def _apply_anomaly(self):
        code = self.anomaly_code.get()
        if code == "NORMAL":
            self.model.clear_anomaly()
            self.logger.log("Anomaly cleared -> NORMAL")
        else:
            self.model.set_anomaly(code, self.sim_clock, duration_hours=3.0)
            self.logger.log(f"Anomaly set -> {code}")

    def _open_log_window(self):
        top = ctk.CTkToplevel(self)
        top.title(self._t("log_title"))
        top.geometry("900x520")

        box = ctk.CTkTextbox(top, wrap="word")
        box.pack(fill="both", expand=True, padx=10, pady=10)

        box.insert("1.0", self.logger.tail(250))
        box.configure(state="disabled")

    # ---------------- targets / maintenance ----------------
    def _get_plant(self) -> Dict[str, float]:
        code = self.plant_code.get()
        return next((p for p in PLANTS if p["code"] == code), PLANTS[0])

    def _targets_for_now(self, now: dt.datetime) -> Dict[str, float]:
        plant = self._get_plant()
        night = GreenhouseLogic.is_night(now)
        t_target = plant["temp_night"] if night else plant["temp_day"]
        return {
            "temp_target": float(t_target),
            "hum_target": float(plant["hum"]),
            "light_min": float(plant["light_min"]),
            "soil_min": float(plant["soil_min"]),
        }

    def _update_targets_line(self):
        plant = self._get_plant()
        prefix = self._t("targets")
        if self.lang_var.get() == "bg":
            txt = (f"{prefix}: Ден {plant['temp_day']}°C / Нощ {plant['temp_night']}°C | "
                   f"Влажн {plant['hum']}% | Min светл {plant['light_min']} lux | Min почва {plant['soil_min']}%")
        else:
            txt = (f"{prefix}: Day {plant['temp_day']}°C / Night {plant['temp_night']}°C | "
                   f"Hum {plant['hum']}% | Light min {plant['light_min']} lux | Soil min {plant['soil_min']}%")
        self.targets_line_lbl.configure(text=txt)

    def _update_maintenance(self, actions: Dict[str, bool], minutes_per_tick: int) -> List[str]:
        dt_h = minutes_per_tick / 60.0
        for k in self.runtime_h.keys():
            if actions.get(k, False):
                self.runtime_h[k] += dt_h

        warnings = []
        for k, thr in MAINTENANCE_THRESHOLDS_H.items():
            if self.runtime_h.get(k, 0.0) >= thr:
                warnings.append(f"Maintenance: {k} {self.runtime_h[k]:.0f}h (thr {thr:.0f}h)")
        return warnings

    # ---------------- SIM loop ----------------
    def _tick_loop(self):
        # advance simulated time
        if self.sim_time_enabled.get():
            self.sim_clock = self.sim_clock + dt.timedelta(minutes=int(self.minutes_per_tick.get()))
        else:
            self.sim_clock = dt.datetime.now().replace(second=0, microsecond=0)

        targets = self._targets_for_now(self.sim_clock)

        # faults
        faults = {
            "fan_fault": self.model.faults.fan_fault,
            "pump_fault": self.model.faults.pump_fault,
            "mister_fault": self.model.faults.mister_fault,
        }

        # auto actions
        if self.auto_mode.get():
            actions, reasons = self.logic.compute(
                values=self.values,
                targets=targets,
                rain_forecast=self.rain_forecast.get() or (self.model.active_anomaly == "RAIN_FORECAST"),
                faults=faults,
                now=self.sim_clock,
            )
        else:
            actions = GreenhouseLogic.blank_actions()
            reasons = ["Manual mode"]

        # optional random faults
        if self.enable_random_faults.get():
            import random
            if random.random() < 0.02:
                pick = random.choice(["fan_fault", "pump_fault", "mister_fault"])
                setattr(self.model.faults, pick, True)
                self.logger.log(f"Random fault injected -> {pick}")

        # maintenance warnings
        maintenance = self._update_maintenance(actions, int(self.minutes_per_tick.get()))

        # apply environment
        rain_fc = self.rain_forecast.get() or (self.model.active_anomaly == "RAIN_FORECAST")
        new_vals, notes = self.model.apply_tick(
            values=self.values,
            actions=actions,
            city_code=self.city_code.get(),
            season_code=self.season_code.get(),
            now=self.sim_clock,
            minutes_per_tick=int(self.minutes_per_tick.get()),
            rain_forecast=rain_fc,
        )

        # update real model values
        self.values.update(new_vals)

        # smooth UI targets (not instantly)
        self.target_values.update(new_vals)

        # keep sliders in sync ONLY if manual_override is ON (otherwise leave them as-is)
        if self.manual_override.get():
            for k in ["temp", "humidity", "light", "soil"]:
                try:
                    self.sliders[k].set(float(self.values[k]))
                    self.slider_labels[k].configure(text=f"{float(self.values[k]):.1f}")
                except Exception:
                    pass

        # save to DB
        ts = self.sim_clock.replace(microsecond=0)
        self.db.insert_reading(
            self.values["temp"], self.values["humidity"], self.values["light"], self.values["rain"], self.values["soil"],
            ts=ts
        )

        # store latest UI info
        self._latest_actions = dict(actions)
        self._latest_targets = dict(targets)
        self._latest_reasons = list(reasons)
        self._latest_notes = dict(notes)
        self._latest_notes["_maintenance"] = " | ".join(maintenance[:2]) if maintenance else ""

        # LOG: anomaly + reasons when something important is ON
        if self.model.active_anomaly != "NORMAL" and "anomaly" in notes:
            self.logger.log(f"Anomaly active -> {self.model.active_anomaly} ({notes['anomaly']})")
        if reasons:
            # keep it short
            self.logger.log("Reasons: " + "; ".join(reasons[:3]))

        # schedule next tick
        delay_ms = int(max(200, self.tick_interval_sec.get() * 1000))
        self.after(delay_ms, self._tick_loop)

    # ---------------- UI loop (60 FPS) ----------------
    def _ui_loop(self):
        now = dt.datetime.now()
        dt_s = (now - self._last_ui_ts).total_seconds()
        self._last_ui_ts = now

        # smooth factor
        fps = float(UI_FPS)
        base_alpha = 0.12
        alpha = 1.0 - (1.0 - base_alpha) ** max(1.0, dt_s * fps)
        alpha = max(0.02, min(0.35, alpha))

        for k in ["temp", "humidity", "light", "rain", "soil"]:
            cur = float(self.display_values.get(k, 0.0))
            tgt = float(self.target_values.get(k, cur))
            self.display_values[k] = cur + (tgt - cur) * alpha

        self._update_clock()
        self._update_sensors()
        self._update_actions()
        self._update_diagnostics()

        # graphs refresh ~1/sec
        if (now - self._last_graph_refresh_ts).total_seconds() >= float(GRAPH_REFRESH_SEC):
            self._refresh_open_graphs()
            self._last_graph_refresh_ts = now

        self.after(int(1000 / UI_FPS), self._ui_loop)

    def _update_clock(self):
        night = GreenhouseLogic.is_night(self.sim_clock)
        dn = self._t("night") if night else self._t("day")
        self.clock_line.set(f"Sim clock: {fmt_dt(self.sim_clock)}\n{dn}")

    def _update_sensors(self):
        v = self.display_values
        self.sensor_cards["temp"].configure(text=f"{v['temp']:.1f} °C")
        self.sensor_cards["humidity"].configure(text=f"{v['humidity']:.1f} %")
        self.sensor_cards["light"].configure(text=f"{v['light']:.0f} lux")
        self.sensor_cards["soil"].configure(text=f"{v['soil']:.1f} %")
        self.sensor_cards["rain"].configure(text=f"{v['rain']:.1f} mm" if v["rain"] > 0.1 else "NO")

        t = self._latest_targets
        self.status_line.set(
            f"{self.sim_clock.strftime('%H:%M')} | "
            f"T:{v['temp']:.1f}°C (tgt {t['temp_target']:.1f}) | "
            f"H:{v['humidity']:.1f}% (tgt {t['hum_target']:.0f}) | "
            f"L:{v['light']:.0f}lx (min {t['light_min']:.0f}) | "
            f"S:{v['soil']:.1f}% (min {t['soil_min']:.0f})"
        )

    def _update_actions(self):
        actions = self._latest_actions
        for k, refs in self.action_tiles.items():
            on = bool(actions.get(k, False))
            refs["frame"].configure(fg_color=refs["on"] if on else refs["off"])
            refs["state"].configure(text="ON" if on else "OFF")

    def _update_diagnostics(self):
        msgs: List[str] = []

        if self.model.active_anomaly != "NORMAL":
            lang = self.lang_var.get()
            label = ANOMALY_LABELS.get(self.model.active_anomaly, {"bg": self.model.active_anomaly, "en": self.model.active_anomaly})[lang]
            msgs.append(f"Anomaly: {label}")

        if self._latest_notes.get("anomaly"):
            msgs.append(self._latest_notes["anomaly"])

        if self.model.faults.fan_fault:
            msgs.append("FAULT: Fan issue.")
        if self.model.faults.pump_fault:
            msgs.append("FAULT: Pump issue.")
        if self.model.faults.mister_fault:
            msgs.append("FAULT: Mister issue.")

        if self._latest_notes.get("_maintenance"):
            msgs.append(self._latest_notes["_maintenance"])

        self.diagnostics_text.set(" | ".join(msgs) if msgs else self._t("no_warnings"))

    # ---------------- graphs ----------------
    def show_graph(self, sensor_key: str, title: str):
        if sensor_key in self._graph_windows:
            try:
                self._graph_windows[sensor_key].top.lift()
                return
            except Exception:
                self._graph_windows.pop(sensor_key, None)

        top = ctk.CTkToplevel(self)
        top.title(f"History: {title}")
        top.geometry("950x520")

        fig = Figure(figsize=(9, 4.6), dpi=100)
        ax = fig.add_subplot(111)
        ax.set_title(f"{title} (range: {self.graph_range_var.get()})")
        ax.grid(True, alpha=0.3)

        canvas = FigureCanvasTkAgg(fig, master=top)
        canvas.get_tk_widget().pack(fill="both", expand=True)

        gw = GraphWindow(top=top, fig=fig, ax=ax, canvas=canvas, sensor_key=sensor_key, title=title)
        self._graph_windows[sensor_key] = gw

        def on_close():
            self._graph_windows.pop(sensor_key, None)
            top.destroy()

        top.protocol("WM_DELETE_WINDOW", on_close)
        self._draw_graph(gw)

    def _fetch_series(self, sensor_key: str):
        mode = self.graph_range_var.get()
        if mode == "all":
            rows = self.db.fetch_all()
        elif mode == "last7":
            rows = self.db.fetch_last_n(7)
        else:
            now = self.sim_clock.replace(microsecond=0)
            hours = 6 if mode == "6h" else 24
            since = now - dt.timedelta(hours=hours)
            rows = self.db.fetch_since(fmt_dt(since))

        xs = [parse_ts(r[0]) for r in rows]
        idx = {"temp": 1, "humidity": 2, "light": 3, "rain": 4, "soil": 5}[sensor_key]
        ys = [float(r[idx]) for r in rows]
        return xs, ys

    def _draw_graph(self, gw: GraphWindow):
        ax = gw.ax
        ax.clear()

        xs, ys = self._fetch_series(gw.sensor_key)
        ax.plot(xs, ys, linewidth=2)

        ax.set_title(f"{gw.title} (range: {self.graph_range_var.get()})")
        ax.grid(True, alpha=0.3)

        locator = mdates.AutoDateLocator()
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M\n%d-%b"))
        gw.fig.autofmt_xdate(rotation=0)

        gw.canvas.draw_idle()

    def _refresh_open_graphs(self):
        for k, gw in list(self._graph_windows.items()):
            try:
                self._draw_graph(gw)
            except Exception:
                self._graph_windows.pop(k, None)
