"""Small reusable building blocks so every screen looks consistent."""
from __future__ import annotations

import threading
import tkinter
import webbrowser
from typing import Callable

import customtkinter as ctk

from gui import theme
from gui.icons import WHITE, icon


# ---------------------------------------------------------------- labels
class WrapLabel(ctk.CTkLabel):
    """A label whose text wraps to whatever width it is given."""

    def __init__(self, master, text: str = "", size: int = 13, color=theme.MUTED,
                 weight: str = "normal", wraplength: int = 520, **kw):
        super().__init__(master, text=text, font=theme.font(size, weight), text_color=color,
                         anchor="w", justify="left", wraplength=wraplength, **kw)
        self._last_width = 0
        tkinter.Frame.bind(self, "<Configure>", self._rewrap, add="+")

    def _rewrap(self, event) -> None:
        try:
            scale = self._get_widget_scaling()
        except Exception:
            scale = 1.0
        width = int(event.width / scale) - 4
        if self.cget("image") is not None:
            width -= 26
        if width > 60 and abs(width - self._last_width) > 3:
            self._last_width = width
            self.configure(wraplength=width)


def title_label(master, text: str, size: int = 26) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text=text, font=theme.font(size, "bold"), text_color=theme.TEXT, anchor="w")


def icon_tile(master, name: str, size: int = 36, icon_size: int | None = None,
              fg=theme.ACCENT_SOFT, color=theme.ACCENT_TEXT, radius: int | None = None) -> ctk.CTkLabel:
    """An icon centred in a rounded, softly coloured square."""
    return ctk.CTkLabel(master, text="", image=icon(name, icon_size or round(size * 0.5), color),
                        width=size, height=size, fg_color=fg,
                        corner_radius=radius if radius is not None else round(size * 0.3))


class StatusLine(WrapLabel):
    """One line of feedback with an icon: success, error, warning, working, or plain info."""

    _STYLES = {
        "ok": ("circle-check", theme.SUCCESS),
        "error": ("circle-alert", theme.ERROR),
        "warning": ("triangle-alert", theme.WARNING),
        "busy": ("hourglass", theme.MUTED),
        "info": (None, theme.MUTED),
    }

    def __init__(self, master, **kw):
        super().__init__(master, text="", size=13, compound="left", **kw)

    def show(self, kind: str, text: str) -> None:
        name, color = self._STYLES.get(kind, self._STYLES["info"])
        self.configure(text=f"  {text}" if name else text, text_color=color,
                       image=icon(name, 16, color) if name else None)

    def clear(self) -> None:
        self.configure(text="", image=None)


# ---------------------------------------------------------------- containers
class Card(ctk.CTkFrame):
    """White rounded panel with an optional icon, title and subtitle. Put content in `.body`."""

    def __init__(self, master, title: str | None = None, subtitle: str | None = None,
                 icon_name: str | None = None, **kw):
        super().__init__(master, fg_color=theme.CARD, corner_radius=16, border_width=1,
                         border_color=theme.BORDER, **kw)
        self.grid_columnconfigure(0, weight=1)
        has_header = bool(title)
        if title:
            header = ctk.CTkFrame(self, fg_color="transparent")
            header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
            header.grid_columnconfigure(1, weight=1)
            col = 0
            if icon_name:
                icon_tile(header, icon_name, size=34).grid(row=0, column=0, rowspan=2, sticky="n",
                                                            padx=(0, 14))
                col = 1
            ctk.CTkLabel(header, text=title, font=theme.font(16, "bold"), text_color=theme.TEXT,
                         anchor="w", height=20).grid(row=0, column=col, sticky="ew")
            if subtitle:
                WrapLabel(header, subtitle, height=18).grid(row=1, column=col, sticky="ew", pady=(1, 0))
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=24, pady=(18 if has_header else 20, 22))
        self.body.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)


# ---------------------------------------------------------------- buttons
def _with_icon(kw: dict, icon_name: str | None, color, side: str, size: int = 16) -> dict:
    if icon_name:
        kw["image"] = icon(icon_name, size, color)
        kw["compound"] = side
    return kw


def primary_button(master, text: str, command: Callable | None = None, icon_name: str | None = None,
                   icon_side: str = "left", **kw) -> ctk.CTkButton:
    kw.setdefault("height", 42)
    _with_icon(kw, icon_name, WHITE, icon_side)
    return ctk.CTkButton(master, text=text, command=command, fg_color=theme.ACCENT,
                         hover_color=theme.ACCENT_HOVER, text_color="#FFFFFF",
                         text_color_disabled=("#E4E4FF", "#C9C9F5"), corner_radius=10,
                         font=theme.font(14, "bold"), **kw)


def secondary_button(master, text: str, command: Callable | None = None, icon_name: str | None = None,
                     icon_side: str = "left", **kw) -> ctk.CTkButton:
    kw.setdefault("height", 42)
    _with_icon(kw, icon_name, theme.TEXT, icon_side)
    return ctk.CTkButton(master, text=text, command=command, fg_color=theme.SOFT,
                         hover_color=theme.SOFT_HOVER, text_color=theme.TEXT,
                         text_color_disabled=theme.MUTED, corner_radius=10,
                         font=theme.font(14, "bold"), **kw)


def link_button(master, text: str, url: str, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(master, text=text, command=lambda: webbrowser.open(url),
                         image=icon("external-link", 14, theme.ACCENT_TEXT), compound="right",
                         fg_color=theme.CARD, hover_color=theme.SOFT_HOVER, text_color=theme.ACCENT_TEXT,
                         border_width=1, border_color=theme.BORDER, corner_radius=8, height=30,
                         font=theme.font(12, "bold"), **kw)


# ---------------------------------------------------------------- inputs
class Field(ctk.CTkFrame):
    """Label + text box + hint line (the hint turns red to show an error)."""

    def __init__(self, master, label: str, hint: str = "", placeholder: str = "", secret: bool = False,
                 on_change: Callable[[], None] | None = None):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self._hint_text = hint
        self._on_change = on_change

        self.label = ctk.CTkLabel(self, text=label, font=theme.font(13, "bold"), text_color=theme.TEXT,
                                  anchor="w", height=20)
        self.label.grid(row=0, column=0, columnspan=2, sticky="w")

        self.entry = ctk.CTkEntry(self, placeholder_text=placeholder, height=42, corner_radius=10,
                                  border_width=1, border_color=theme.BORDER, fg_color=theme.FIELD,
                                  text_color=theme.TEXT, placeholder_text_color=theme.MUTED,
                                  font=theme.font(14), show="•" if secret else "")
        self.entry.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.entry.bind("<KeyRelease>", self._changed)

        if secret:
            self.eye = ctk.CTkButton(self, text="", image=icon("eye", 18, theme.MUTED), width=42, height=42,
                                     corner_radius=10, fg_color=theme.SOFT, hover_color=theme.SOFT_HOVER,
                                     command=self._toggle_secret)
            self.eye.grid(row=1, column=1, padx=(8, 0), pady=(6, 0))

        self.hint = WrapLabel(self, hint, size=12, wraplength=300)
        self.hint.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        if not hint:
            self.hint.grid_remove()

    def _changed(self, _event=None) -> None:
        self.set_error(None)
        if self._on_change:
            self._on_change()

    def _toggle_secret(self) -> None:
        hidden = self.entry.cget("show") == "•"
        self.entry.configure(show="" if hidden else "•")
        self.eye.configure(image=icon("eye-off" if hidden else "eye", 18, theme.MUTED))

    def get(self) -> str:
        return self.entry.get().strip()

    def set(self, value) -> None:
        self.entry.delete(0, "end")
        if value not in (None, ""):
            self.entry.insert(0, str(value))

    def focus(self) -> None:
        self.entry.focus_set()

    def set_label(self, label: str, hint: str = "", placeholder: str = "") -> None:
        self.label.configure(text=label)
        self._hint_text = hint
        self.entry.configure(placeholder_text=placeholder)
        self.set_error(None)

    def set_error(self, message: str | None) -> None:
        if message:
            self.entry.configure(border_color=theme.ERROR)
            self.hint.configure(text=message, text_color=theme.ERROR)
            self.hint.grid()
        else:
            self.entry.configure(border_color=theme.BORDER)
            self.hint.configure(text=self._hint_text, text_color=theme.MUTED)
            if self._hint_text:
                self.hint.grid()
            else:
                self.hint.grid_remove()


# ---------------------------------------------------------------- page switching without lag
def show_page(page) -> None:
    """Bring a stacked page to the front.

    All pages are gridded once into the same cell; switching just raises one. Re-gridding
    customtkinter widgets forces every rounded corner to redraw, which is what caused the
    visible stutter when pressing Next.
    """
    getattr(page, "_parent_frame", page).tkraise()


# ---------------------------------------------------------------- threading helper
def run_in_background(widget, work: Callable[[], object], on_done: Callable[[bool, object], None]) -> None:
    """Run `work` in a thread, then call on_done(ok, result_or_exception) on the GUI thread."""
    box: dict = {}

    def worker() -> None:
        try:
            box["result"] = (True, work())
        except BaseException as exc:  # noqa: BLE001 - surfaced to the user
            box["result"] = (False, exc)

    def poll() -> None:
        if "result" in box:
            on_done(*box["result"])
            return
        try:
            widget.after(100, poll)
        except tkinter.TclError:
            pass  # window closed meanwhile

    threading.Thread(target=worker, daemon=True).start()
    widget.after(100, poll)


def rtl_fix(text: str) -> str:
    """Tk draws Arabic letters correctly but puts right-to-left WORDS in the wrong order.

    For names written in Arabic (no Latin letters), reverse the word order so 'محمد علي' displays
    as typed. Mixed or Latin text is left unchanged.
    """
    has_rtl = any("֐" <= ch <= "ࣿ" for ch in text)
    has_latin = any(ch.isascii() and ch.isalpha() for ch in text)
    if has_rtl and not has_latin:
        return " ".join(reversed(text.split()))
    return text


def shorten_path(path: str, limit: int = 64) -> str:
    if len(path) <= limit:
        return path
    keep = limit - 1
    return path[: keep // 2 - 4] + "…" + path[-(keep // 2 + 4):]
