"""First-run setup guide: Welcome → Photos folder → Event → All set."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import config
from config import Settings
from gui import theme
from gui.sections import EventFields, FolderPicker
from gui.widgets import (StatusLine, WrapLabel, icon_tile, primary_button, secondary_button, shorten_path,
                         show_page, title_label)

STEPS = ["welcome", "folder", "event", "done"]
STEP_TITLES = {"folder": "Photos folder", "event": "Your event"}
NUMBERED = ["folder", "event"]
COLUMN_WIDTH = 740


class SetupWizard(ctk.CTkFrame):
    def __init__(self, master, settings: Settings, on_finish: Callable[[], None]):
        super().__init__(master, fg_color=theme.BG)
        self.settings = settings
        self.on_finish = on_finish
        self.index = 0

        # A centred column with a FIXED width. If it could grow, it would resize again and again while
        # text wraps during start-up, leaving ghost edges on screen.
        column = ctk.CTkFrame(self, fg_color="transparent", width=COLUMN_WIDTH)
        column.place(relx=0.5, rely=0, relheight=1, anchor="n")
        column.grid_propagate(False)
        column.grid_columnconfigure(0, weight=1)
        column.grid_rowconfigure(1, weight=1)

        # Top: brand + step counter + progress
        top = ctk.CTkFrame(column, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(18, 12))
        top.grid_columnconfigure(2, weight=1)
        icon_tile(top, "camera", size=30, fg=theme.ACCENT, color=("#FFFFFF", "#FFFFFF")).grid(
            row=0, column=0, padx=(0, 10))
        ctk.CTkLabel(top, text=config.APP_NAME, font=theme.font(15, "bold"),
                     text_color=theme.TEXT).grid(row=0, column=1, sticky="w")
        self.step_label = ctk.CTkLabel(top, text="", font=theme.font(13), text_color=theme.MUTED)
        self.step_label.grid(row=0, column=2, sticky="e")
        self.progress = ctk.CTkProgressBar(top, height=6, corner_radius=3, progress_color=theme.ACCENT,
                                           fg_color=theme.SOFT)
        self.progress.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(14, 0))

        # Middle: card that holds the stacked pages
        self.card = ctk.CTkFrame(column, fg_color=theme.CARD, corner_radius=20, border_width=1,
                                 border_color=theme.BORDER)
        self.card.grid(row=1, column=0, sticky="nsew")
        self.card.grid_columnconfigure(0, weight=1)
        self.card.grid_rowconfigure(0, weight=1)

        # Bottom: navigation
        nav = ctk.CTkFrame(column, fg_color="transparent")
        nav.grid(row=2, column=0, sticky="ew", pady=(12, 18))
        nav.grid_columnconfigure(1, weight=1)
        self.back_button = secondary_button(nav, "Back", self.back, icon_name="arrow-left", width=110)
        self.back_button.grid(row=0, column=0, sticky="w")
        self.nav_status = StatusLine(nav, wraplength=380)
        self.nav_status.grid(row=0, column=1, sticky="ew", padx=16)
        self.next_button = primary_button(nav, "Continue", self.next, icon_name="arrow-right",
                                          icon_side="right", width=170)
        self.next_button.grid(row=0, column=2, sticky="e")

        # Build every page once and stack them; switching only raises one (no redraw stutter).
        self.pages: dict[str, ctk.CTkFrame] = {}
        self._build_page("welcome", self._fill_welcome, scroll=True)
        self._build_page("folder", self._fill_folder)
        self._build_page("event", self._fill_event)
        self.folder.set_path(settings.watch_folder)
        self.event.set(settings.event_name)

        root = self.winfo_toplevel()
        self._return_binding = root.bind("<Return>", self._on_return, add="+")
        self._show()

    def destroy(self) -> None:
        try:
            self.winfo_toplevel().unbind("<Return>", self._return_binding)
        except Exception:
            pass
        super().destroy()

    # ------------------------------------------------------------ pages
    def _build_page(self, name: str, fill: Callable, scroll: bool = False) -> None:
        # An opaque holder per page, all in the same grid cell, inset so the card's rounded corners show.
        holder = ctk.CTkFrame(self.card, fg_color=theme.CARD, corner_radius=0)
        holder.grid(row=0, column=0, sticky="nsew", padx=20, pady=(22, 16))
        holder.grid_columnconfigure(0, weight=1)
        holder.grid_rowconfigure(0, weight=1)
        if scroll:
            page = ctk.CTkScrollableFrame(holder, fg_color="transparent", scrollbar_button_color=theme.SOFT_HOVER)
            page.grid(row=0, column=0, sticky="nsew", padx=(14, 0))
        else:
            page = ctk.CTkFrame(holder, fg_color="transparent")
            page.grid(row=0, column=0, sticky="nsew", padx=(18, 26), pady=(4, 0))
        page.grid_columnconfigure(0, weight=1)
        fill(page)
        self.pages[name] = holder

    def _heading(self, page, icon_name: str, title: str, text: str, success: bool = False) -> None:
        if success:
            icon_tile(page, icon_name, size=52, fg=theme.SUCCESS_SOFT, color=theme.SUCCESS).grid(
                row=0, column=0, sticky="w")
        else:
            icon_tile(page, icon_name, size=52).grid(row=0, column=0, sticky="w")
        title_label(page, title, size=24).grid(row=1, column=0, sticky="w", pady=(14, 0))
        WrapLabel(page, text, size=14, wraplength=640).grid(row=2, column=0, sticky="ew", pady=(4, 20))

    def _fill_welcome(self, page) -> None:
        self._heading(page, "sparkles", f"Welcome to {config.APP_NAME}",
                      "Guests scan a QR code with their phone and save their photos straight away. "
                      "Setup takes about a minute.")
        for i, (icon_name, title, text) in enumerate([
            ("folder", "Choose the photos folder", "Where your photo booth saves each guest's pictures."),
            ("party-popper", "Name your event", "Guests see it on their phone."),
            ("scan-qr-code", "Show the QR code", "Guests scan it on any network: Wi-Fi or mobile data."),
        ]):
            row = ctk.CTkFrame(page, fg_color=theme.FIELD, corner_radius=12)
            row.grid(row=3 + i, column=0, sticky="ew", pady=(0, 8), padx=(0, 14))
            row.grid_columnconfigure(1, weight=1)
            icon_tile(row, icon_name, size=40, fg=theme.CARD).grid(row=0, column=0, rowspan=2,
                                                                  padx=(12, 14), pady=12)
            ctk.CTkLabel(row, text=title, font=theme.font(14, "bold"), text_color=theme.TEXT,
                         anchor="w", height=20).grid(row=0, column=1, sticky="sew", pady=(12, 0))
            ctk.CTkLabel(row, text=text, font=theme.font(13), text_color=theme.MUTED,
                         anchor="w", height=20).grid(row=1, column=1, sticky="new", pady=(0, 12))

    def _fill_folder(self, page) -> None:
        self._heading(page, "folder-open", "Where does the booth save photos?",
                      "Choose the folder your booth saves photos into. Photos are matched to guests by "
                      "name, so  Omnya & Fatma.jpg  and  Omnya & Fatma_1.jpg  go to the same guest.")
        self.folder = FolderPicker(page)
        self.folder.grid(row=3, column=0, sticky="ew")

    def _fill_event(self, page) -> None:
        self._heading(page, "party-popper", "What's the event called?",
                      "This appears at the top of the page guests see on their phone.")
        self.event = EventFields(page)
        self.event.grid(row=3, column=0, sticky="ew")

    def _fill_done(self, page) -> None:
        self._heading(page, "circle-check", "You're all set!",
                      "Everything is saved. You can change any of this later in Settings.", success=True)
        s = self.settings
        rows = [
            ("folder", "Photos folder", shorten_path(s.watch_folder, 44)),
            ("party-popper", "Event", s.event_name),
            ("globe", "Phones", "Any network (online link)"),
        ]
        box = ctk.CTkFrame(page, fg_color=theme.FIELD, corner_radius=14)
        box.grid(row=3, column=0, sticky="ew")
        box.grid_columnconfigure(2, weight=1)
        for i, (icon_name, label, value) in enumerate(rows):
            pad = (14 if i == 0 else 4, 14 if i == len(rows) - 1 else 4)
            icon_tile(box, icon_name, size=32, fg=theme.CARD).grid(row=i, column=0, padx=(14, 12), pady=pad)
            ctk.CTkLabel(box, text=label, font=theme.font(13), text_color=theme.MUTED, anchor="w",
                         width=110).grid(row=i, column=1, sticky="w", pady=pad)
            ctk.CTkLabel(box, text=value, font=theme.font(14, "bold"), text_color=theme.TEXT, anchor="w").grid(
                row=i, column=2, sticky="w", padx=(0, 14), pady=pad)

    # ------------------------------------------------------------ navigation
    def _show(self) -> None:
        step = STEPS[self.index]
        if step == "done":
            old = self.pages.pop("done", None)
            if old is not None:
                old.destroy()
            self._build_page("done", self._fill_done)
        show_page(self.pages[step])

        self.nav_status.clear()
        if 0 < self.index < len(STEPS) - 1:
            self.back_button.grid()
        else:
            self.back_button.grid_remove()  # nothing to go back to on the first and last page
        if step in NUMBERED:
            n = NUMBERED.index(step) + 1
            self.step_label.configure(text=f"Step {n} of {len(NUMBERED)}  ·  {STEP_TITLES[step]}")
            self.progress.set(n / len(NUMBERED))
        else:
            self.step_label.configure(text="")
            self.progress.set(0 if step == "welcome" else 1)
        self.next_button.configure(text={"welcome": "Let's start", "event": "Finish setup",
                                         "done": "Open the app"}.get(step, "Continue"))
        if step == "event":
            self.after(30, self.event.name.focus)

    def _on_return(self, _event=None) -> None:
        self.next()  # Enter = Continue

    def back(self) -> None:
        if self.index > 0:
            self.index -= 1
            self._show()

    def next(self) -> None:
        step = STEPS[self.index]
        if step == "folder" and self.folder.validate():
            return
        if step == "event" and (self.event.validate() or not self._finish()):
            return
        if step == "done":
            self.on_finish()
            return
        self.index += 1
        self._show()

    def _finish(self) -> bool:
        s = self.settings
        s.watch_folder = self.folder.path
        s.event_name = self.event.get()
        s.setup_complete = True
        try:
            config.save(s)
        except OSError as exc:
            self.nav_status.show("error", f"Couldn't save settings: {exc}")
            return False
        return True
