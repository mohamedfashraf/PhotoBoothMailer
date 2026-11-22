"""Settings screen, split into three sections: Event · Guest page · App."""
from __future__ import annotations

import webbrowser
from typing import Callable

import customtkinter as ctk

import branding
import config
import updater
from config import APP_VERSION, DEVELOPER, DEVELOPER_URL, Settings
from gui import theme
from gui.sections import EventFields, FolderPicker
from gui.widgets import (Card, Field, Segmented, StatusLine, WrapLabel, primary_button, run_in_background,
                         secondary_button, show_page, title_label)

APPEARANCE = {"System": "system", "Light": "light", "Dark": "dark"}
SECTIONS = ["Event", "Guest page", "App"]


def _label(master, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text=text, font=theme.font(12, "bold"), text_color=theme.TEXT, anchor="w", height=18)


class SettingsView(ctk.CTkFrame):
    def __init__(self, master, settings: Settings, on_saved: Callable[[], None],
                 on_run_setup: Callable[[], None]):
        super().__init__(master, fg_color="transparent")
        self.settings = settings
        self.on_saved = on_saved
        self._update_url = ""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header: title, section tabs, setup guide
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 0))
        header.grid_columnconfigure(0, weight=1)
        title_label(header, "Settings").grid(row=0, column=0, sticky="w")
        secondary_button(header, "Setup guide", on_run_setup, icon_name="rotate-ccw", width=140).grid(
            row=0, column=1, sticky="e")
        self.tabs = Segmented(self, values=SECTIONS, command=self.show_section)
        self.tabs.grid(row=1, column=0, sticky="w", padx=24, pady=(12, 8))

        # Sections, stacked; switching only raises one
        holder = ctk.CTkFrame(self, fg_color="transparent")
        holder.grid(row=2, column=0, sticky="nsew", padx=(14, 6))
        holder.grid_columnconfigure(0, weight=1)
        holder.grid_rowconfigure(0, weight=1)
        self.sections: dict[str, ctk.CTkScrollableFrame] = {}
        for name in SECTIONS:
            page = ctk.CTkScrollableFrame(holder, fg_color=theme.BG, scrollbar_button_color=theme.SOFT_HOVER)
            page.grid(row=0, column=0, sticky="nsew")
            page.grid_columnconfigure(0, weight=1)
            self.sections[name] = page
        self._build_event(self.sections["Event"])
        self._build_guest_page(self.sections["Guest page"])
        self._build_app(self.sections["App"])

        # Footer
        footer = ctk.CTkFrame(self, fg_color=theme.BG, corner_radius=0, height=52, border_width=0)
        footer.grid(row=3, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        self.status = StatusLine(footer)
        self.status.grid(row=0, column=0, sticky="ew", padx=24, pady=10)
        primary_button(footer, "Save changes", self.save, icon_name="save", width=150).grid(
            row=0, column=1, padx=24, pady=10)

        self.load()
        self.show_section("Event")

    def show_section(self, name: str) -> None:
        self.tabs.set(name)
        show_page(self.sections[name])

    # ------------------------------------------------------------ Event
    def _build_event(self, page) -> None:
        folder_card = Card(page, "Photos folder", "Where the photo booth saves each guest's photos.",
                           icon_name="folder")
        folder_card.grid(row=0, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.folder = FolderPicker(folder_card.body)
        self.folder.grid(row=0, column=0, sticky="ew")

        event_card = Card(page, "Event", "The name guests see on their phone.", icon_name="party-popper")
        event_card.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.event = EventFields(event_card.body)
        self.event.grid(row=0, column=0, sticky="ew")

    # ------------------------------------------------------------ Guest page
    def _build_guest_page(self, page) -> None:
        look = Card(page, "Look", "Colour and a short message on guests' phones.", icon_name="sparkles")
        look.grid(row=0, column=0, sticky="ew", padx=12, pady=(0, 12))
        _label(look.body, "Colour").grid(row=0, column=0, sticky="w")
        swatches = ctk.CTkFrame(look.body, fg_color="transparent")
        swatches.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self._color = ""
        self.swatches: dict[str, ctk.CTkButton] = {}
        for name, color in branding.PRESETS.items():
            button = ctk.CTkButton(swatches, text="", width=26, height=26, corner_radius=13, fg_color=color,
                                   hover_color=color, border_width=2, border_color=theme.CARD,
                                   command=lambda c=color: self._pick_color(c))
            button.pack(side="left", padx=(0, 6))
            self.swatches[color] = button
        self.color_name = ctk.CTkLabel(swatches, text="", font=theme.font(12), text_color=theme.MUTED)
        self.color_name.pack(side="left", padx=(6, 0))
        self.message = Field(look.body, "Message (optional)", placeholder="Thank you for celebrating with us!",
                             hint="Shown above the guest's photos. Up to 200 characters.")
        self.message.grid(row=2, column=0, sticky="ew", pady=(14, 0))

        insta = Card(page, "Instagram", "Ask guests to follow you before they see their photos.",
                     icon_name="heart")
        insta.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        row = ctk.CTkFrame(insta.body, fg_color="transparent")
        row.grid(row=0, column=0, sticky="w")
        _label(row, "Follow popup").pack(side="left")
        self.insta_toggle = Segmented(row, values=["On", "Off"], command=lambda _v: self._show_instagram())
        self.insta_toggle.pack(side="left", padx=(12, 0))
        self.insta_box = ctk.CTkFrame(insta.body, fg_color="transparent")
        self.insta_box.grid(row=1, column=0, sticky="ew")
        self.insta_box.grid_columnconfigure(0, weight=1)
        self.insta_url = Field(self.insta_box, "Your Instagram", placeholder="@yourstudio or instagram.com/yourstudio",
                               hint="Your account name or the link to your profile.")
        self.insta_url.grid(row=0, column=0, sticky="ew", pady=(14, 0))
        self.insta_message = Field(self.insta_box, "Popup text", placeholder=branding.INSTAGRAM_DEFAULT_MESSAGE,
                                   hint="Leave empty to use the text shown in grey.")
        self.insta_message.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        WrapLabel(self.insta_box, "Guests see it once, the first time they open the page. They can close it with "
                                  "× or \"Not now\" and still get their photos.", size=12).grid(
            row=2, column=0, sticky="ew", pady=(10, 0))

    def _show_instagram(self) -> None:
        if self.insta_toggle.get() == "On":
            self.insta_box.grid()
        else:
            self.insta_box.grid_remove()

    def _pick_color(self, color: str) -> None:
        self._color = color
        for value, button in self.swatches.items():
            button.configure(border_color=theme.TEXT if value.upper() == color.upper() else theme.CARD)
        name = next((n for n, v in branding.PRESETS.items() if v.upper() == color.upper()), "")
        self.color_name.configure(text=name)

    # ------------------------------------------------------------ App
    def _build_app(self, page) -> None:
        general = Card(page, "General", icon_name="settings")
        general.grid(row=0, column=0, sticky="ew", padx=12, pady=(0, 12))
        general.body.grid_columnconfigure((0, 1), weight=1, uniform="general")
        look = ctk.CTkFrame(general.body, fg_color="transparent")
        look.grid(row=0, column=0, sticky="new", padx=(0, 12))
        _label(look, "Appearance").pack(anchor="w")
        self.appearance = Segmented(look, values=list(APPEARANCE), command=self._on_appearance)
        self.appearance.pack(anchor="w", pady=(5, 0))
        self.port = Field(general.body, "Guest page port", placeholder="8000",
                          hint="Only change it if another program already uses this number.")
        self.port.grid(row=0, column=1, sticky="new", padx=(12, 0))

        about = Card(page, "About", icon_name="info")
        about.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        about.body.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(about.body, text=f"{config.APP_NAME}  ·  version {APP_VERSION}", font=theme.font(13, "bold"),
                     text_color=theme.TEXT, anchor="w").grid(row=0, column=0, sticky="w")
        made_by = ctk.CTkLabel(about.body, text=f"Made by {DEVELOPER}", font=theme.font(12, "bold"),
                               text_color=theme.MUTED, anchor="w", cursor="hand2")
        made_by.grid(row=1, column=0, sticky="w")
        made_by.bind("<Button-1>", lambda _e: webbrowser.open(DEVELOPER_URL))
        buttons = ctk.CTkFrame(about.body, fg_color="transparent")
        buttons.grid(row=0, column=1, rowspan=2, sticky="e")
        self.update_button = secondary_button(buttons, "Check for updates", self._check_updates,
                                              icon_name="rotate-ccw", width=170)
        self.update_button.pack(side="left")
        self.download_button = primary_button(buttons, "Download", self._open_update, icon_name="external-link",
                                              width=120)
        self.update_status = StatusLine(about.body)
        self.update_status.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.update_status.grid_remove()

    def _check_updates(self) -> None:
        self.update_button.configure(state="disabled", text="Checking…")
        self.download_button.pack_forget()
        self.update_status.grid()
        self.update_status.show("busy", "Asking GitHub for the newest version…")
        run_in_background(self, updater.latest_release, self._update_checked)

    def _update_checked(self, ok: bool, result) -> None:
        self.update_button.configure(state="normal", text="Check for updates")
        if not ok:
            message = str(result) if isinstance(result, updater.UpdateCheckError) else "Couldn't check right now."
            self.update_status.show("warning", message)
            return
        version, url = result
        if updater.is_newer(version):
            self._update_url = url
            self.update_status.show("ok", f"Version {version} is available. Press Download, then replace the old "
                                          f".exe with the new one.")
            self.download_button.pack(side="left", padx=(8, 0))
        else:
            self.update_status.show("ok", f"You have the newest version ({APP_VERSION}).")

    def _open_update(self) -> None:
        if self._update_url:
            webbrowser.open(self._update_url)

    # ------------------------------------------------------------ load / save
    def load(self) -> None:
        s = self.settings
        self.folder.set_path(s.watch_folder)
        self.event.set(s.event_name)
        self.port.set(s.server_port)
        self.appearance.set(next((k for k, v in APPEARANCE.items() if v == s.appearance), "System"))
        self._pick_color(s.brand_color if branding.valid_color(s.brand_color) else branding.DEFAULT_COLOR)
        self.message.set(s.brand_message)
        self.insta_toggle.set("On" if s.instagram_enabled else "Off")
        self.insta_url.set(s.instagram_url)
        self.insta_message.set(s.instagram_message)
        self._show_instagram()

    def _on_appearance(self, label: str) -> None:
        self.settings.appearance = APPEARANCE[label]
        theme.apply_appearance(self.settings.appearance)
        try:
            config.save(self.settings)
        except OSError:
            pass

    def save(self) -> None:
        problems = []  # (section, what)
        if self.folder.validate():
            problems.append(("Event", "photos folder"))
        if self.event.validate():
            problems.append(("Event", "event name"))
        instagram_on = self.insta_toggle.get() == "On"
        instagram = branding.instagram_url(self.insta_url.get())
        if instagram_on and not instagram:
            self.insta_url.set_error("Type your Instagram account, e.g. @yourstudio, or paste your profile link.")
            problems.append(("Guest page", "Instagram"))
        try:
            port = int(self.port.get() or 8000)
            if not 1024 <= port <= 65535:
                raise ValueError
        except ValueError:
            self.port.set_error("Use a number between 1024 and 65535, for example 8000.")
            problems.append(("App", "port"))
            port = self.settings.server_port

        if problems:
            self.show_section(problems[0][0])
            self.status.show("error", "Please check: " + ", ".join(what for _, what in problems) + ".")
            return

        port_changed = port != self.settings.server_port
        s = self.settings
        s.watch_folder = self.folder.path
        s.event_name = self.event.get()
        s.server_port = port
        s.brand_color = "" if self._color.upper() == branding.DEFAULT_COLOR.upper() else self._color
        s.brand_message = self.message.get()[:200]
        s.instagram_enabled = instagram_on
        s.instagram_url = instagram or self.insta_url.get()
        s.instagram_message = self.insta_message.get()[:120]
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
