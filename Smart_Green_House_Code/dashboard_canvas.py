# dashboard_canvas.py
import customtkinter as ctk

OFF_BG = "#0b1730"  # deep navy
ON_COLORS = {
    "Heating": "#d32f2f",
    "Ventilation": "#00acc1",
    "Windows": "#ffb300",
    "Watering": "#1e88e5",
    "Misting": "#8e24aa",
    "Lighting": "#fdd835",
    "RainProtection": "#546e7a",
    "Alarm": "#b71c1c",
}

EMOJI = {
    "Heating": "🔥",
    "Ventilation": "🌀",
    "Windows": "🪟",
    "Watering": "💧",
    "Misting": "🌫️",
    "Lighting": "💡",
    "RainProtection": "☂️",
    "Alarm": "🚨",
}

class StatusDashboardCanvas(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, corner_radius=18)
        self.configure(fg_color="transparent")

        self.grid_columnconfigure((0,1,2), weight=1, uniform="c")
        self.grid_rowconfigure((0,1,2), weight=1, uniform="r")

        self.tiles = {}
        order = [
            "Heating","Ventilation","Windows",
            "Watering","Misting","Lighting",
            "RainProtection","Alarm",
        ]

        r = 0
        c = 0
        for key in order:
            tile = ctk.CTkFrame(self, corner_radius=18, fg_color=OFF_BG)
            tile.grid(row=r, column=c, padx=14, pady=14, sticky="nsew")
            tile.grid_propagate(False)

            icon = ctk.CTkLabel(tile, text=EMOJI.get(key,""), font=ctk.CTkFont(size=34, weight="bold"))
            icon.place(relx=0.5, rely=0.35, anchor="center")

            title = ctk.CTkLabel(tile, text=key, font=ctk.CTkFont(size=16, weight="bold"))
            title.place(relx=0.5, rely=0.62, anchor="center")

            state = ctk.CTkLabel(tile, text="OFF", font=ctk.CTkFont(size=13))
            state.place(relx=0.5, rely=0.80, anchor="center")

            self.tiles[key] = (tile, state)

            c += 1
            if c == 3:
                c = 0
                r += 1

        # Last row: center two tiles
        # Move RainProtection to row=2,col=0 and Alarm row=2,col=1 already via order,
        # keep col=2 empty for symmetry.
        spacer = ctk.CTkFrame(self, corner_radius=18, fg_color="transparent")
        spacer.grid(row=2, column=2, padx=14, pady=14, sticky="nsew")

    def update_actions(self, actions: dict):
        for key, (tile, state_lbl) in self.tiles.items():
            on = bool(actions.get(key, False))
            if on:
                tile.configure(fg_color=ON_COLORS.get(key, "#2e7d32"))
                state_lbl.configure(text="ON")
            else:
                tile.configure(fg_color=OFF_BG)
                state_lbl.configure(text="OFF")
