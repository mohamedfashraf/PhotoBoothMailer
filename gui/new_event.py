""""New event" window: give the next event a name and a photos folder, and close the current guest list."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from config import APP_NAME, Settings
from gui import theme
from gui.sections import FolderPicker
from gui.widgets import Field, StatusLine, WrapLabel, icon_tile, primary_button, secondary_button, title_label


class NewEventDialog(ctk.CTkToplevel):
    def __init__(self, master, settings: Settings, guest_count: int, on_start: Callable[[str, str], None]):
        super().__init__(master)
        self.settings = settings
        self.on_start = on_start
        self.title(f"New event · {APP_NAME}")
        self.configure(fg_color=theme.BG)
        self.resizable(False, False)
        self.transient(master)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=28, pady=24)
        body.grid_columnconfigure(0, weight=1)
        icon_tile(body, "party-popper", size=48).grid(row=0, column=0, sticky="w")
        title_label(body, "Start a new event", size=22).grid(row=1, column=0, sticky="w", pady=(12, 0))
        current = settings.event_name or "the current event"
        WrapLabel(body, f"The guest list of \"{current}\" ({guest_count} guest{'s' if guest_count != 1 else ''}) "
                        "is closed and its QR codes and links stop working. No photos are deleted.",
                  size=13, wraplength=460).grid(row=2, column=0, sticky="ew", pady=(4, 16))

        self.name = Field(body, "New event name", placeholder="e.g. Laila & Karim's Engagement")
        self.name.grid(row=3, column=0, sticky="ew")
        ctk.CTkLabel(body, text="Photos folder", font=theme.font(13, "bold"), text_color=theme.TEXT,
                     anchor="w").grid(row=4, column=0, sticky="w", pady=(14, 6))
        self.folder = FolderPicker(body)
        self.folder.grid(row=5, column=0, sticky="ew")
        self.folder.set_path(settings.watch_folder)
        WrapLabel(body, "Tip: use a new, empty folder for each event. Photos already in the folder show up "
                        "as guests of the new event.", size=12, wraplength=460).grid(
            row=6, column=0, sticky="ew", pady=(8, 0))

        self.status = StatusLine(body)
        self.status.grid(row=7, column=0, sticky="ew", pady=(12, 0))
        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.grid(row=8, column=0, sticky="e", pady=(12, 0))
        secondary_button(buttons, "Cancel", self.destroy, width=110).pack(side="left")
        primary_button(buttons, "Start new event", self._start, icon_name="sparkles", width=190).pack(
            side="left", padx=(10, 0))

        self.bind("<Return>", lambda _e: self._start())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(120, self._show)

    def _show(self) -> None:
        self.update_idletasks()
        master = self.master
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.lift()
        self.focus_force()
        self.grab_set()  # finish or cancel this first
        self.name.focus()

    def _start(self) -> None:
        name = self.name.get()
        if not name:
            self.name.set_error("Please give the new event a name.")
            return
        if self.folder.validate():
            return
        self.grab_release()
        self.destroy()
        self.on_start(name, self.folder.path)
