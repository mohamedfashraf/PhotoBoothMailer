"""Settings screen (main window tab). Same sections as the setup guide, all on one page."""
from __future__ import annotations

from typing import Callable

import os
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

import branding
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

        brand_card = Card(scroll, "Guest page look", "Your event's colour, logo and a short message, shown on "
                                                     "guests' phones.", icon_name="sparkles")
        brand_card.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 16))
        self._build_branding(brand_card.body)

        adv_card = Card(scroll, "More options", icon_name="settings")
        adv_card.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 16))
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

    # ------------------------------------------------------------ branding
    def _build_branding(self, body) -> None:
        body.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(body, text="Colour", font=theme.font(13, "bold"), text_color=theme.TEXT,
                     anchor="w").grid(row=0, column=0, sticky="w")
        swatches = ctk.CTkFrame(body, fg_color="transparent")
        swatches.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self._color = ""
        self.swatches: dict[str, ctk.CTkButton] = {}
        for name, color in branding.PRESETS.items():
            button = ctk.CTkButton(swatches, text="", width=34, height=34, corner_radius=17, fg_color=color,
                                   hover_color=color, border_width=3, border_color=theme.CARD,
                                   command=lambda c=color: self._pick_color(c))
            button.pack(side="left", padx=(0, 8))
            self.swatches[color] = button
        self.color_name = ctk.CTkLabel(swatches, text="", font=theme.font(13), text_color=theme.MUTED)
        self.color_name.pack(side="left", padx=(6, 0))

        ctk.CTkLabel(body, text="Logo (optional)", font=theme.font(13, "bold"), text_color=theme.TEXT,
                     anchor="w").grid(row=2, column=0, sticky="w", pady=(16, 0))
        logo_row = ctk.CTkFrame(body, fg_color="transparent")
        logo_row.grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.logo_preview = ctk.CTkLabel(logo_row, text="No logo", width=64, height=64, corner_radius=12,
                                         fg_color=theme.FIELD, text_color=theme.MUTED, font=theme.font(11))
        self.logo_preview.pack(side="left")
        secondary_button(logo_row, "Choose image", self._choose_logo, icon_name="image", width=160).pack(
            side="left", padx=(12, 0))
        self.logo_remove = secondary_button(logo_row, "Remove", self._remove_logo, width=100)
        self.logo_remove.pack(side="left", padx=(8, 0))
        WrapLabel(body, "A PNG with a transparent background looks best, e.g. the couple's monogram. It replaces "
                        "the camera icon on the guest page and appears on the QR screen.", size=12).grid(
            row=4, column=0, sticky="ew", pady=(6, 0))

        self.message = Field(body, "Message (optional)", placeholder="Thank you for celebrating with us!",
                             hint="Shown above the guest's photos. Up to 200 characters.")
        self.message.grid(row=5, column=0, sticky="ew", pady=(16, 0))

    def _pick_color(self, color: str) -> None:
        self._color = color
        for value, button in self.swatches.items():
            button.configure(border_color=theme.TEXT if value.upper() == color.upper() else theme.CARD)
        name = next((n for n, v in branding.PRESETS.items() if v.upper() == color.upper()), "")
        self.color_name.configure(text=name)

    def _show_logo(self) -> None:
        if branding.has_logo():
            with Image.open(branding.logo_path()) as img:
                img.load()
                w, h = img.size
                scale = 56 / max(w, h)
                image = ctk.CTkImage(light_image=img.copy(), size=(max(1, int(w * scale)), max(1, int(h * scale))))
            self.logo_preview.configure(image=image, text="")
            self.logo_remove.configure(state="normal")
        else:
            self.logo_preview.configure(image=None, text="No logo")
            self.logo_remove.configure(state="disabled")

    def _choose_logo(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(), title="Choose a logo", initialdir=os.path.join(os.path.expanduser("~"), "Pictures"),
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")])
        if not path:
            return
        try:
            branding.save_logo(path)
        except Exception:  # not an image, unreadable...
            self.status.show("error", "That file couldn't be opened as an image. Try a PNG or JPG.")
            return
        self._show_logo()
        self.status.show("ok", "Logo updated. Guests see it straight away.")
        self.on_saved()

    def _remove_logo(self) -> None:
        branding.remove_logo()
        self._show_logo()
        self.status.show("ok", "Logo removed.")
        self.on_saved()

    def load(self) -> None:
        s = self.settings
        self.folder.set_path(s.watch_folder)
        self.event.set(s.event_name)
        self.port.set(s.server_port)
        label = next((k for k, v in APPEARANCE.items() if v == s.appearance), "System")
        self.appearance.set(label)
        self._pick_color(s.brand_color if branding.valid_color(s.brand_color) else branding.DEFAULT_COLOR)
        self.message.set(s.brand_message)
        self._show_logo()

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
        s.brand_color = "" if self._color.upper() == branding.DEFAULT_COLOR.upper() else self._color
        s.brand_message = self.message.get()[:200]
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
