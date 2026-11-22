"""Setting sections shared by the first-run setup guide and the Settings screen."""
from __future__ import annotations

import os
from tkinter import filedialog

import customtkinter as ctk

import naming
from gui import theme
from gui.icons import icon
from gui.widgets import Field, StatusLine, WrapLabel, icon_tile, primary_button, secondary_button, shorten_path



class FolderPicker(ctk.CTkFrame):
    """Shows the chosen photos folder and a big "Choose folder" button."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.path = ""
        self.grid_columnconfigure(0, weight=1)

        self.pill = ctk.CTkFrame(self, fg_color=theme.FIELD, corner_radius=8, border_width=1,
                                 border_color=theme.BORDER, height=34)
        self.pill.grid(row=0, column=0, sticky="ew")
        self.pill.grid_propagate(False)
        self.pill.grid_columnconfigure(1, weight=1)
        self.pill.grid_rowconfigure(0, weight=1)
        self.pill_icon = ctk.CTkLabel(self.pill, text="", image=icon("folder", 18, theme.MUTED), width=20)
        self.pill_icon.grid(row=0, column=0, padx=(14, 10))
        self.path_label = ctk.CTkLabel(self.pill, text="", font=theme.font(14), anchor="w")
        self.path_label.grid(row=0, column=1, sticky="ew", padx=(0, 12))

        secondary_button(self, "Choose folder", self._choose, icon_name="folder-open", width=150, height=34).grid(
            row=0, column=1, padx=(10, 0))

        self.status = StatusLine(self)
        self.status.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.set_path("")

    def _choose(self) -> None:
        initial = self.path if self.path and os.path.isdir(self.path) else os.path.expanduser("~")
        chosen = filedialog.askdirectory(parent=self.winfo_toplevel(), initialdir=initial, mustexist=True,
                                         title="Choose the folder where the photo booth saves photos")
        if chosen:
            self.set_path(os.path.normpath(chosen))

    def set_path(self, path: str) -> None:
        self.path = path or ""
        self.pill.configure(border_color=theme.BORDER)
        ok = bool(self.path) and os.path.isdir(self.path)
        self.pill_icon.configure(image=icon("folder-check" if ok else "folder", 18,
                                            theme.SUCCESS if ok else theme.MUTED))
        if not self.path:
            self.path_label.configure(text="No folder chosen yet", text_color=theme.MUTED)
            self.status.show("info", "Pick the folder where your photo booth software saves photos "
                                     "(each photo named after the guest, like Hana.jpg).")
            return
        self.path_label.configure(text=shorten_path(self.path, 50), text_color=theme.TEXT)
        if not os.path.isdir(self.path):
            self.status.show("error", "This folder can't be found. If it's on a USB drive, plug it in.")
            return
        guests = naming.scan_folder(self.path)
        photos = sum(len(g.photos) for g in guests.values())
        if not guests:
            self.status.show("ok", "Folder connected. No photos yet. That's fine: new photos "
                                   "will show up as soon as the booth saves them.")
        else:
            self.status.show("ok", f"Looks good. Found {len(guests)} guest{'s' if len(guests) != 1 else ''} "
                                   f"and {photos} photo{'s' if photos != 1 else ''}.")

    def validate(self) -> str | None:
        error = None
        if not self.path:
            error = "Please choose the photos folder first."
        elif not os.path.isdir(self.path):
            error = "This folder can't be found. If it's on a USB drive, plug it in."
        if error:
            self.pill.configure(border_color=theme.ERROR)
            self.status.show("error", error)
        return error


class EventFields(ctk.CTkFrame):
    """Event name with a live preview of what guests will see."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.name = Field(self, "Event name", placeholder="e.g. Sara & Omar's Wedding",
                          on_change=self._update_preview)
        self.name.grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(self, text="PREVIEW: THE TOP OF YOUR GUEST'S PHOTOS PAGE", font=theme.font(11, "bold"),
                     text_color=theme.MUTED, anchor="w", height=16).grid(row=1, column=0, sticky="ew",
                                                                          pady=(14, 6))
        preview = ctk.CTkFrame(self, fg_color=theme.SOFT, corner_radius=10, border_width=0,
                               border_color=theme.BORDER)
        preview.grid(row=2, column=0, sticky="ew")
        preview.grid_columnconfigure(1, weight=1)
        icon_tile(preview, "camera", size=36, fg=theme.PRIMARY, color=theme.PRIMARY_TEXT).grid(row=0, column=0, rowspan=2, padx=(14, 12), pady=12)
        self.preview_label = ctk.CTkLabel(preview, text="", font=theme.font(14, "bold"), text_color=theme.TEXT,
                                          anchor="w", height=20)
        self.preview_label.grid(row=0, column=1, sticky="sew", padx=(0, 14), pady=(12, 0))
        ctk.CTkLabel(preview, text="Your photos are ready. Save them to your phone before you go.",
                     font=theme.font(13), text_color=theme.MUTED, anchor="w", height=18).grid(
            row=1, column=1, sticky="new", padx=(0, 14), pady=(0, 12))
        self._update_preview()

    def _update_preview(self) -> None:
        self.preview_label.configure(text=self.name.get() or "Your event name")

    def set(self, value: str) -> None:
        self.name.set(value)
        self._update_preview()

    def get(self) -> str:
        return self.name.get()

    def validate(self) -> str | None:
        if not self.get():
            self.name.set_error("Please give your event a name, e.g. \"Sara & Omar's Wedding\".")
            return "missing event name"
        return None
