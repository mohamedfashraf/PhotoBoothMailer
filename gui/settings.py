"""Settings screen (main window tab). Same sections as the setup guide, all on one page."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import config
from config import Settings
from gui import theme
from gui.sections import EventFields, FolderPicker
from gui.widgets import Card, Field, StatusLine, WrapLabel, primary_button, secondary_button, title_label

APPEARANCE = {"System": "system", "Light": "light", "Dark": "dark"}


class SettingsView(ctk.CTkFrame):
    def __init__(self, master, settings: Settings, on_saved: Callable[[], None],
                 on_run_setup: Callable[[], None]):
        super().__init__(master, fg_color="transparent")
        self.settings = settings
        self.on_saved = on_saved
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=36, pady=(30, 12))
        header.grid_columnconfigure(0, weight=1)
        title_label(header, "Settings").grid(row=0, column=0, sticky="w")
        WrapLabel(header, "Change anything here at any time. Press Save when you're done.", size=14).grid(
            row=1, column=0, sticky="ew", pady=(2, 0))
        secondary_button(header, "Run setup guide again", on_run_setup, icon_name="rotate-ccw", width=210).grid(
            row=0, column=1, rowspan=2, sticky="e")

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", scrollbar_button_color=theme.SOFT_HOVER)
        scroll.grid(row=1, column=0, sticky="nsew", padx=(24, 12))
        scroll.grid_columnconfigure(0, weight=1)

        folder_card = Card(scroll, "Photos folder", "The folder where the photo booth saves each guest's photos.", icon_name="folder")
        folder_card.grid(row=0, column=0, sticky="ew", padx=12, pady=(0, 16))
        self.folder = FolderPicker(folder_card.body)
        self.folder.grid(row=0, column=0, sticky="ew")

        event_card = Card(scroll, "Event", "The name guests see on their phone.", icon_name="party-popper")
        event_card.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 16))
        self.event = EventFields(event_card.body)
        self.event.grid(row=0, column=0, sticky="ew")

        adv_card = Card(scroll, "More options", icon_name="settings")
        adv_card.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 16))
        adv_card.body.grid_columnconfigure((0, 1), weight=1, uniform="adv")
        self.port = Field(adv_card.body, "Guest page port", placeholder="8000",
                          hint="Leave this at 8000 unless another program already uses it.")
        self.port.grid(row=0, column=0, sticky="new", padx=(0, 12))
        look = ctk.CTkFrame(adv_card.body, fg_color="transparent")
        look.grid(row=0, column=1, sticky="new", padx=(12, 0))
        ctk.CTkLabel(look, text="Look", font=theme.font(13, "bold"), text_color=theme.TEXT).pack(anchor="w")
        self.appearance = ctk.CTkSegmentedButton(
            look, values=list(APPEARANCE), command=self._on_appearance, height=42, font=theme.font(13, "bold"),
            selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER,
            unselected_color=theme.SOFT, unselected_hover_color=theme.SOFT_HOVER, fg_color=theme.SOFT)
        self.appearance.pack(anchor="w", pady=(6, 0))

        # Footer
        footer = ctk.CTkFrame(self, fg_color=theme.SIDEBAR, corner_radius=0, height=72, border_width=0)
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        self.status = StatusLine(footer)
        self.status.grid(row=0, column=0, sticky="ew", padx=36, pady=16)
        primary_button(footer, "Save changes", self.save, icon_name="save", width=176).grid(row=0, column=1, padx=36, pady=16)

        self.load()

    def load(self) -> None:
        s = self.settings
        self.folder.set_path(s.watch_folder)
        self.event.set(s.event_name)
        self.port.set(s.server_port)
        label = next((k for k, v in APPEARANCE.items() if v == s.appearance), "System")
        self.appearance.set(label)

    def _on_appearance(self, label: str) -> None:
        self.settings.appearance = APPEARANCE[label]
        theme.apply_appearance(self.settings.appearance)
        try:
            config.save(self.settings)
        except OSError:
            pass

    def save(self) -> None:
        problems = []
        if self.folder.validate():
            problems.append("photos folder")
        if self.event.validate():
            problems.append("event name")
        try:
            port = int(self.port.get() or 8000)
            if not 1024 <= port <= 65535:
                raise ValueError
        except ValueError:
            self.port.set_error("Use a number between 1024 and 65535, for example 8000.")
            problems.append("port")
            port = self.settings.server_port

        if problems:
            self.status.show("error", "Please check: " + ", ".join(problems) + ".")
            return

        port_changed = port != self.settings.server_port
        s = self.settings
        s.watch_folder = self.folder.path
        s.event_name = self.event.get()
        s.server_port = port
        try:
            config.save(s)
        except OSError as exc:
            self.status.show("error", f"Couldn't save settings: {exc}")
            return
        message = "Saved."
        if port_changed:
            message += " Restart the app to use the new port."
        self.status.show("ok", message)
        self.on_saved()
