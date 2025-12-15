import datetime
import time
from typing import Dict

import customtkinter as ctk

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.dates as mdates

try:
    import winsound
except ImportError:
    winsound = None

from database import DatabaseManager
from logic import GreenhouseLogic
from demo_engine import SeasonalDemoEngine
from config import ALERT_LIMITS, ALERT_COOLDOWN_SEC, AUTO_INSERT_INTERVAL_SEC, CLIMATE_PROFILES


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class SmartGreenhouseApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Smart Greenhouse - Course Project")
        self.geometry("1400x800")
        self.minsize(1200, 720)

        self.db = DatabaseManager()
        self.logic = GreenhouseLogic()
        self.demo = SeasonalDemoEngine()

        self.alert_limits = ALERT_LIMITS
        self.alert_cooldown = ALERT_COOLDOWN_SEC
        self._last_alert_ts = 0.0
        self._alarm_active = False

        self.auto_interval_sec = float(AUTO_INSERT_INTERVAL_SEC)

        self.var_auto = ctk.BooleanVar(value=True)

        # graph range
        self.var_graph_range = ctk.StringVar(value="6h")
        self._graph_windows = {}

        # simulated time controls
        self.var_sim_time = ctk.BooleanVar(value=True)

        # climate profile controls
        self.locations = list(CLIMATE_PROFILES.keys())
        self.seasons = ["WINTER", "SPRING", "SUMMER", "AUTUMN"]
        self.var_location = ctk.StringVar(value=self.locations[0])
        self.var_season = ctk.StringVar(value="WINTER")

        # anomaly
        self.anomalies = SeasonalDemoEngine.ANOMALIES
        self.var_anomaly = ctk.StringVar(value="NORMAL")

        # manual sliders
        self.manual: Dict[str, float] = {"temp": 22.0, "humidity": 55.0, "light": 350.0, "rain": 0.0, "soil": 45.0}
        self.var_rain_forecast = ctk.BooleanVar(value=False)

        self._build_layout()
        self._apply_profile()

        self.after(200, self._tick)

    # ---------------- Layout ----------------
    def _build_layout(self):
        self.grid_columnconfigure(0, weight=1)   # left
        self.grid_columnconfigure(1, weight=3)   # right
        self.grid_rowconfigure(0, weight=1)

        # LEFT: scrollable controls
        self.frame_controls = ctk.CTkScrollableFrame(self, corner_radius=16)
        self.frame_controls.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

        # RIGHT: dashboard
        self.frame_dash = ctk.CTkFrame(self, corner_radius=16)
        self.frame_dash.grid(row=0, column=1, padx=12, pady=12, sticky="nsew")
        self.frame_dash.grid_rowconfigure(0, weight=0)
        self.frame_dash.grid_rowconfigure(1, weight=1)
        self.frame_dash.grid_rowconfigure(2, weight=0)
        self.frame_dash.grid_columnconfigure(0, weight=1)

        # ---- Controls header
        ctk.CTkLabel(self.frame_controls, text="Controls", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(8, 10))

        # Auto mode
        row = ctk.CTkFrame(self.frame_controls)
        row.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(row, text="Auto mode (Seasonal Demo)", width=170).pack(side="left", padx=6)
        ctk.CTkSwitch(row, variable=self.var_auto, text="").pack(side="left")

        # Interval
        row = ctk.CTkFrame(self.frame_controls)
        row.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(row, text="Interval (sec):", width=120).pack(side="left", padx=6)
        self.ent_interval = ctk.CTkEntry(row, width=80)
        self.ent_interval.insert(0, str(self.auto_interval_sec))
        self.ent_interval.pack(side="left", padx=6)
        ctk.CTkButton(row, text="Apply", width=80, command=self._apply_interval).pack(side="left", padx=6)

        # Fullscreen toggle
        self.btn_full = ctk.CTkButton(self.frame_controls, text="Fullscreen", command=self._toggle_fullscreen)
        self.btn_full.pack(fill="x", padx=10, pady=(6, 12))

        # ---- Climate profile
        ctk.CTkLabel(self.frame_controls, text="Climate Profile", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(8, 6))
        row = ctk.CTkFrame(self.frame_controls)
        row.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(row, text="Location:", width=80).pack(side="left", padx=6)
        ctk.CTkOptionMenu(row, variable=self.var_location, values=self.locations, command=lambda _=None: self._apply_profile()).pack(side="left", padx=6, fill="x", expand=True)

        row = ctk.CTkFrame(self.frame_controls)
        row.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(row, text="Season:", width=80).pack(side="left", padx=6)
        ctk.CTkOptionMenu(row, variable=self.var_season, values=self.seasons, command=lambda _=None: self._apply_profile()).pack(side="left", padx=6, fill="x", expand=True)

        self.lbl_profile = ctk.CTkLabel(self.frame_controls, text="")
        self.lbl_profile.pack(anchor="w", padx=14, pady=(2, 10))

        # ---- Time (demo)
        ctk.CTkLabel(self.frame_controls, text="Time (Demo)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(8, 6))
        row = ctk.CTkFrame(self.frame_controls)
        row.pack(fill="x", padx=10, pady=4)
        ctk.CTkCheckBox(row, text="Simulated time (cycle Day/Night)", variable=self.var_sim_time, command=self._apply_time_mode).pack(side="left", padx=6)

        row = ctk.CTkFrame(self.frame_controls)
        row.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(row, text="Minutes / tick:", width=120).pack(side="left", padx=6)
        self.ent_minutes = ctk.CTkEntry(row, width=80)
        self.ent_minutes.insert(0, "15")
        self.ent_minutes.pack(side="left", padx=6)
        ctk.CTkButton(row, text="Set", width=80, command=self._apply_minutes).pack(side="left", padx=6)

        self.lbl_clock = ctk.CTkLabel(self.frame_controls, text="Sim clock: --")
        self.lbl_clock.pack(anchor="w", padx=14, pady=(4, 2))

        self.lbl_daynight = ctk.CTkLabel(self.frame_controls, text="Day/Night: --")
        self.lbl_daynight.pack(anchor="w", padx=14, pady=(0, 10))

        ctk.CTkButton(self.frame_controls, text="Reset 09:00", command=lambda: self._reset_clock(9, 0)).pack(fill="x", padx=10, pady=(0, 10))

        # ---- Scenario (anomalies)
        ctk.CTkLabel(self.frame_controls, text="Scenario (Anomalies)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(8, 6))
        self.lbl_anom = ctk.CTkLabel(self.frame_controls, text="NORMAL")
        self.lbl_anom.pack(pady=(0, 6))

        row = ctk.CTkFrame(self.frame_controls)
        row.pack(fill="x", padx=10, pady=4)
        ctk.CTkButton(row, text="Next anomaly", command=self._next_anomaly).pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkButton(row, text="Normal", command=self._set_normal).pack(side="left", expand=True, fill="x", padx=4)

        # ---- Manual inputs
        ctk.CTkLabel(self.frame_controls, text="Manual inputs", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(12, 6))

        self.sliders = {}
        self.slider_labels = {}

        self._add_slider("temp", "Temperature (°C)", -10, 55, self.manual["temp"], steps=650)
        self._add_slider("humidity", "Humidity (%)", 0, 100, self.manual["humidity"], steps=500)
        self._add_slider("light", "Light (lux)", 0, 2500, self.manual["light"], steps=500)
        self._add_slider("soil", "Soil moisture (%)", 0, 100, self.manual["soil"], steps=500)

        ctk.CTkCheckBox(self.frame_controls, text="Rain forecast", variable=self.var_rain_forecast).pack(pady=(6, 10), padx=10, anchor="w")

        # ---- Graphs
        ctk.CTkLabel(self.frame_controls, text="Graphs", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(12, 6))

        row = ctk.CTkFrame(self.frame_controls)
        row.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(row, text="Range:", width=60).pack(side="left", padx=6)
        ctk.CTkOptionMenu(row, variable=self.var_graph_range, values=["6h", "24h", "all"]).pack(side="left", padx=6, fill="x", expand=True)

        for key, title in [("temp", "Temperature"), ("humidity", "Humidity"), ("light", "Light"), ("soil", "Soil"), ("rain", "Rain")]:
            ctk.CTkButton(self.frame_controls, text=f"Show: {title}", command=lambda k=key, t=title: self.show_graph(k, t)).pack(fill="x", padx=10, pady=4)

        # ---- Dashboard (right)
        ctk.CTkLabel(self.frame_dash, text="Greenhouse Status", font=ctk.CTkFont(size=22, weight="bold")).grid(row=0, column=0, pady=(12, 6))

        # Top sensor line
        self.frame_sensors = ctk.CTkFrame(self.frame_dash, corner_radius=16)
        self.frame_sensors.grid(row=0, column=0, sticky="ew", padx=18, pady=(52, 10))
        for i in range(5):
            self.frame_sensors.grid_columnconfigure(i, weight=1)

        self.sensor_labels: Dict[str, ctk.CTkLabel] = {}
        self._sensor_card(0, "Temp", "temp", "°C", "🌡️")
        self._sensor_card(1, "Hum", "humidity", "%", "💧")
        self._sensor_card(2, "Light", "light", "lux", "💡")
        self._sensor_card(3, "Soil", "soil", "%", "🌱")
        self._sensor_card(4, "Rain", "rain", "", "🌧️")

        # Action tiles
        self.frame_actions = ctk.CTkFrame(self.frame_dash, corner_radius=16)
        self.frame_actions.grid(row=1, column=0, sticky="nsew", padx=18, pady=10)

        for r in range(3):
            self.frame_actions.grid_rowconfigure(r, weight=1)
        for c in range(3):
            self.frame_actions.grid_columnconfigure(c, weight=1)

        self.action_tiles = {}
        self._action_tile("Heating", 0, 0, "Heating", "🔥")
        self._action_tile("Ventilation", 0, 1, "Ventilation", "💨")
        self._action_tile("Windows", 0, 2, "Windows", "🪟")
        self._action_tile("Watering", 1, 0, "Watering", "💧")
        self._action_tile("Misting", 1, 1, "Misting", "🌫️")
        self._action_tile("Lighting", 1, 2, "Lighting", "💡")
        self._action_tile("RainProtection", 2, 0, "Rain Protect", "☂️")
        self._action_tile("Alarm", 2, 1, "ALARM", "🚨")

        spacer = ctk.CTkFrame(self.frame_actions, fg_color="transparent")
        spacer.grid(row=2, column=2, sticky="nsew")

        self.lbl_status = ctk.CTkLabel(self.frame_dash, text="", anchor="w")
        self.lbl_status.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))

    def _add_slider(self, key: str, label: str, lo: float, hi: float, default: float, steps: int = 500):
        ctk.CTkLabel(self.frame_controls, text=label).pack(anchor="w", padx=10)

        steps = max(1, int(steps))  # must be >= 1 for your CTk version
        s = ctk.CTkSlider(
            self.frame_controls,
            from_=float(lo),
            to=float(hi),
            number_of_steps=steps,
            command=lambda v, k=key: self._on_slider(k, v),
        )
        s.set(float(default))
        s.pack(fill="x", padx=10, pady=(0, 6))

        lbl = ctk.CTkLabel(self.frame_controls, text=f"{float(default):.1f}")
        lbl.pack(anchor="e", padx=14, pady=(0, 6))

        self.sliders[key] = s
        self.slider_labels[key] = lbl

    def _on_slider(self, key: str, value: float):
        self.manual[key] = float(value)
        if key in self.slider_labels:
            self.slider_labels[key].configure(text=f"{float(value):.1f}")

    def _sensor_card(self, col: int, title: str, key: str, unit: str, icon: str):
        f = ctk.CTkFrame(self.frame_sensors, corner_radius=14)
        f.grid(row=0, column=col, sticky="ew", padx=6, pady=8)
        ctk.CTkLabel(f, text=f"{icon}  {title}", font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(8, 2))
        lbl = ctk.CTkLabel(f, text=f"-- {unit}", font=ctk.CTkFont(size=14))
        lbl.pack(pady=(0, 8))
        self.sensor_labels[key] = lbl

    def _action_tile(self, key: str, r: int, c: int, text: str, icon: str):
        tile = ctk.CTkFrame(self.frame_actions, corner_radius=18)
        tile.grid(row=r, column=c, sticky="nsew", padx=10, pady=10)
        ctk.CTkLabel(tile, text=icon, font=ctk.CTkFont(size=28)).place(relx=0.5, rely=0.35, anchor="center")
        ctk.CTkLabel(tile, text=text, font=ctk.CTkFont(size=14, weight="bold")).place(relx=0.5, rely=0.68, anchor="center")
        state_lbl = ctk.CTkLabel(tile, text="OFF", font=ctk.CTkFont(size=12))
        state_lbl.place(relx=0.5, rely=0.82, anchor="center")
        self.action_tiles[key] = (tile, state_lbl)

    # ---------------- handlers ----------------
    def _apply_profile(self):
        loc = self.var_location.get()
        season = self.var_season.get()
        self.demo.set_profile(loc, season)
        self.lbl_profile.configure(text=f"Active: {loc} | {season}")

    def _apply_time_mode(self):
        self.demo.set_sim_time(bool(self.var_sim_time.get()))

    def _apply_minutes(self):
        try:
            mins = int(self.ent_minutes.get().strip())
            self.demo.set_minutes_per_tick(mins)
        except Exception:
            pass

    def _reset_clock(self, h: int, m: int):
        self.demo.reset_sim_time(h, m)

    def _apply_interval(self):
        try:
            v = float(self.ent_interval.get().strip())
            if v > 0:
                self.auto_interval_sec = v
        except Exception:
            pass

    def _toggle_fullscreen(self):
        is_full = bool(self.attributes("-fullscreen"))
        self.attributes("-fullscreen", not is_full)
        self.btn_full.configure(text="Windowed" if not is_full else "Fullscreen")

    def _next_anomaly(self):
        name = self.demo.next_anomaly()
        self.var_anomaly.set(name)
        self.lbl_anom.configure(text=name)

    def _set_normal(self):
        self.demo.set_anomaly("NORMAL")
        self.var_anomaly.set("NORMAL")
        self.lbl_anom.configure(text="NORMAL")

    def _range_to_hours(self):
        v = (self.var_graph_range.get() or "").strip().lower()
        if v == "6h":
            return 6
        if v == "24h":
            return 24
        return None

    # ---------------- sound ----------------
    def _play_alert_sound(self):
        now = time.time()
        if now - self._last_alert_ts < self.alert_cooldown:
            return
        self._last_alert_ts = now
        if winsound:
            winsound.Beep(1200, 200)
        else:
            try:
                self.bell()
            except Exception:
                pass

    def _update_tiles(self, actions: Dict[str, bool]):
        on_colors = {
            "Heating": "#E53935",
            "Ventilation": "#00ACC1",
            "Windows": "#FFB300",
            "Watering": "#1E88E5",
            "Misting": "#8E24AA",
            "Lighting": "#FDD835",
            "RainProtection": "#546E7A",
            "Alarm": "#B71C1C",
        }
        off_color = "#232323"

        for key, (tile, lbl) in self.action_tiles.items():
            active = bool(actions.get(key))
            tile.configure(fg_color=on_colors.get(key, "#2E7D32") if active else off_color)
            lbl.configure(text="ON" if active else "OFF")

    def _update_sensors(self, vals: Dict[str, float]):
        self.sensor_labels["temp"].configure(text=f"{vals['temp']:.1f} °C")
        self.sensor_labels["humidity"].configure(text=f"{vals['humidity']:.1f} %")
        self.sensor_labels["light"].configure(text=f"{vals['light']:.0f} lux")
        self.sensor_labels["soil"].configure(text=f"{vals['soil']:.1f} %")
        self.sensor_labels["rain"].configure(text="YES" if vals["rain"] > 0.2 else "NO")

    # ---------------- main loop ----------------
    def _tick(self):
        now = self.demo.now()
        day = self.demo.is_day(now)

        self.lbl_clock.configure(text=f"Sim clock: {now.strftime('%H:%M')}" if self.demo.use_sim_time else f"Real time: {now.strftime('%H:%M')}")
        self.lbl_daynight.configure(text=f"Day/Night: {'DAY ☀️' if day else 'NIGHT 🌙'}")

        if self.var_auto.get():
            self.demo.set_anomaly(self.var_anomaly.get())
            current_vals = self.demo.values.copy()
            rain_forecast = (self.var_anomaly.get() == "RAIN_FORECAST")
        else:
            self.demo.set_anomaly("NORMAL")
            current_vals = self.manual.copy()
            current_vals["rain"] = 1.0 if self.var_rain_forecast.get() else 0.0
            rain_forecast = bool(self.var_rain_forecast.get())

        actions, _reasons = self.logic.apply_rules(
            temp=current_vals["temp"],
            humidity=current_vals["humidity"],
            light=current_vals["light"],
            rain_forecast=rain_forecast,
            soil_moisture=current_vals["soil"],
            now=now,
        )

        # apply environment + actuators
        if self.var_auto.get():
            new_vals = self.demo.step(actions)
        else:
            new_vals = self.demo.step(actions, manual_override=current_vals)

        # save DB
        try:
            self.db.insert_reading(new_vals["temp"], new_vals["humidity"], new_vals["light"], new_vals["rain"], new_vals["soil"])
        except Exception:
            pass

        self._update_sensors(new_vals)
        self._update_tiles(actions)

        alarm_now = bool(actions.get("Alarm"))
        if alarm_now and not self._alarm_active:
            self._play_alert_sound()
        self._alarm_active = alarm_now

        ts = now.strftime("%H:%M:%S")
        self.lbl_status.configure(
            text=f"🕒 {ts} | T:{new_vals['temp']:.1f}°C | H:{new_vals['humidity']:.1f}% | L:{new_vals['light']:.0f}lx | S:{new_vals['soil']:.1f}% | R:{'YES' if new_vals['rain']>0.2 else 'NO'}"
        )

        self.after(int(self.auto_interval_sec * 1000), self._tick)

    # ---------------- Graph popup ----------------
    def show_graph(self, sensor_key: str, title: str):
        hours = self._range_to_hours()
        history = self.db.get_history(sensor_key, hours=hours, limit=5000)
        if not history:
            return

        times = [datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S") for t, _ in history]
        values = [v for _, v in history]

        top = self._graph_windows.get(sensor_key)
        if top is None or not top.winfo_exists():
            top = ctk.CTkToplevel(self)
            top.title(f"History: {title}")
            top.geometry("950x540")
            top.attributes("-topmost", True)

            container = ctk.CTkFrame(top, corner_radius=12)
            container.pack(fill="both", expand=True, padx=10, pady=10)

            fig = Figure(figsize=(9, 5), dpi=100)
            ax = fig.add_subplot(111)

            canvas = FigureCanvasTkAgg(fig, master=container)
            canvas.get_tk_widget().pack(fill="both", expand=True)

            toolbar = NavigationToolbar2Tk(canvas, container)
            toolbar.update()

            top._fig = fig
            top._ax = ax
            top._canvas = canvas

            self._graph_windows[sensor_key] = top

        ax = top._ax
        fig = top._fig
        canvas = top._canvas

        ax.clear()
        ax.plot(times, values, marker="o", markersize=3, linewidth=1.5)

        rng = self.var_graph_range.get()
        ax.set_title(f"{title} (range: {rng})")

        locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

        lim = ALERT_LIMITS.get(sensor_key)
        if lim and "min" in lim and "max" in lim:
            ax.axhline(lim["min"], linestyle="--", linewidth=1)
            ax.axhline(lim["max"], linestyle="--", linewidth=1)

        ax.grid(True, linestyle="--", alpha=0.35)
        fig.tight_layout()
        canvas.draw()

        top.lift()
        top.focus_force()

    def run(self):
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.mainloop()

    def _on_close(self):
        try:
            self.db.close()
        finally:
            self.destroy()
