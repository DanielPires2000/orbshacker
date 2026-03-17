"""
timer.py – Fake game process: a simple countdown timer.

When orbshacker copies itself (or pythonw.exe) and renames it to a game's
executable name, the copy runs this timer. Discord sees the process name
and thinks the game is running.
"""

import tkinter as tk

WINDOW_TITLE     = "Timer"
WINDOW_SIZE      = "400x250"
BG_COLOR         = "#1a1a1a"
TEXT_COLOR        = "#e0e0e0"
ACCENT_COLOR     = "#4a9eff"
SECONDARY_COLOR  = "#666666"
DONE_COLOR       = "#ff6b6b"
TIMER_MINUTES    = 15


class TimerApp:
    def __init__(self, root: tk.Tk):
        self.root: tk.Tk = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_SIZE)
        self.root.resizable(False, False)
        self.root.configure(bg=BG_COLOR)

        self.remaining = TIMER_MINUTES * 60

        self.timer_label: tk.Label = tk.Label(
            root, text=f"{TIMER_MINUTES:02d}:00",
            font=("Consolas", 56, "bold"), fg=TEXT_COLOR, bg=BG_COLOR,
        )
        self.timer_label.pack(expand=True)

        self.status_label: tk.Label = tk.Label(
            root, text="Running",
            font=("Segoe UI", 10), fg=SECONDARY_COLOR, bg=BG_COLOR,
        )
        self.status_label.pack(side="bottom", pady=20)

        self._tick()

    def _tick(self):
        m, s = divmod(self.remaining, 60)
        self.timer_label.config(text=f"{m:02d}:{s:02d}")
        if self.remaining > 0:
            self.remaining -= 1
            self.root.after(1000, self._tick)
        else:
            self.timer_label.config(text="00:00", fg=DONE_COLOR)
            self.status_label.config(text="Complete", fg=DONE_COLOR)


def run_timer() -> None:
    """Entry point for the fake game process."""
    root = tk.Tk()
    TimerApp(root)
    root.mainloop()
