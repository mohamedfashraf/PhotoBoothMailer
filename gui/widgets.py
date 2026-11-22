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
                 weight: str = "normal", wraplength: int = 520, autowrap: bool = True, **kw):
        super().__init__(master, text=text, font=theme.font(size, weight), text_color=color,
                         anchor="w", justify="left", wraplength=wraplength, **kw)
        self._last_width = 0
        if autowrap:  # off for one-line labels that should keep their natural width
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


def title_label(master, text: str, size: int = 20) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text=text, font=theme.font(size, "bold"), text_color=theme.TEXT, anchor="w")


def icon_tile(master, name: str, size: int = 36, icon_size: int | None = None,
              fg=theme.SOFT, color=theme.TEXT, radius: int | None = None) -> ctk.CTkLabel:
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
        super().__init__(master, text="", size=12, compound="left", **kw)

    def show(self, kind: str, text: str) -> None:
        name, color = self._STYLES.get(kind, self._STYLES["info"])
        self.configure(text=f"  {text}" if name else text, text_color=color,
                       image=icon(name, 14, color) if name else None)

    def clear(self) -> None:
        self.configure(text="", image=None)


# ---------------------------------------------------------------- containers
class Card(ctk.CTkFrame):
    """White panel with a hairline border and an optional small icon, title and subtitle.

    Put content in `.body`.
    """

    def __init__(self, master, title: str | None = None, subtitle: str | None = None,
                 icon_name: str | None = None, **kw):
        super().__init__(master, fg_color=theme.CARD, corner_radius=12, border_width=1,
                         border_color=theme.BORDER, **kw)
        self.grid_columnconfigure(0, weight=1)
        has_header = bool(title)
        if title:
            header = ctk.CTkFrame(self, fg_color="transparent")
            header.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 0))
            header.grid_columnconfigure(1, weight=1)
            if icon_name:
                ctk.CTkLabel(header, text="", image=icon(icon_name, 16, theme.MUTED), width=16).grid(
                    row=0, column=0, sticky="w", padx=(0, 8))
            ctk.CTkLabel(header, text=title, font=theme.font(14, "bold"), text_color=theme.TEXT,
                         anchor="w", height=20).grid(row=0, column=1, sticky="ew")
            if subtitle:
                WrapLabel(header, subtitle, size=12, height=16).grid(row=1, column=0, columnspan=2, sticky="ew",
                                                                     pady=(2, 0))
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=18, pady=(10 if has_header else 14, 16))
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
    """The one main action on a screen: near-black (near-white in dark mode)."""
    kw.setdefault("height", 34)
    _with_icon(kw, icon_name, theme.PRIMARY_TEXT, icon_side, size=15)
    return ctk.CTkButton(master, text=text, command=command, fg_color=theme.PRIMARY,
                         hover_color=theme.PRIMARY_HOVER, text_color=theme.PRIMARY_TEXT,
                         text_color_disabled=theme.FAINT, corner_radius=8,
                         font=theme.font(13, "bold"), **kw)


def secondary_button(master, text: str, command: Callable | None = None, icon_name: str | None = None,
                     icon_side: str = "left", **kw) -> ctk.CTkButton:
    """Everything else: white with a hairline border."""
    kw.setdefault("height", 34)
    _with_icon(kw, icon_name, theme.TEXT, icon_side, size=15)
    return ctk.CTkButton(master, text=text, command=command, fg_color=theme.CARD, border_width=1,
                         border_color=theme.BORDER, hover_color=theme.SOFT, text_color=theme.TEXT,
                         text_color_disabled=theme.FAINT, corner_radius=8,
                         font=theme.font(13, "bold"), **kw)


def icon_button(master, icon_name: str, command: Callable | None = None, size: int = 34) -> ctk.CTkButton:
    """A square button with just an icon (e.g. refresh)."""
    return ctk.CTkButton(master, text="", image=icon(icon_name, 15, theme.MUTED), width=size, height=size,
                         fg_color=theme.CARD, border_width=1, border_color=theme.BORDER, hover_color=theme.SOFT,
                         corner_radius=8, command=command)


class Segmented(ctk.CTkFrame):
    """A pill-style choice (like iOS / macOS): a light grey track, the chosen option a raised white chip.

    Used like CTkSegmentedButton: Segmented(master, values=[...], command=fn); .set(v), .get(),
    .configure(values=[...]).
    """

    def __init__(self, master, values: list[str], command: Callable[[str], None] | None = None,
                 height: int = 30, font_size: int = 12, **kw):
        super().__init__(master, fg_color=theme.SOFT, corner_radius=9, **kw)
        self._command = command
        self._height = height
        self._font_size = font_size
        self._value = ""
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._build(list(values))

    def _build(self, values: list[str]) -> None:
        for button in self._buttons.values():
            button.destroy()
        self._buttons = {}
        for i, value in enumerate(values):
            button = ctk.CTkButton(self, text=value, height=self._height - 6, width=40, corner_radius=7,
                                   border_width=1, font=theme.font(self._font_size, "bold"),
                                   command=lambda v=value: self._click(v))
            button.grid(row=0, column=i, padx=(3 if i == 0 else 0, 3), pady=3)
            self._buttons[value] = button
        self._paint()

    def _click(self, value: str) -> None:
        if value == self._value:
            return
        self.set(value)
        if self._command:
            self._command(value)

    def _paint(self) -> None:
        for value, button in self._buttons.items():
            on = value == self._value
            button.configure(fg_color=theme.CARD if on else theme.SOFT,
                             border_color=theme.BORDER if on else theme.SOFT,
                             hover_color=theme.CARD if on else theme.SOFT_HOVER,
                             text_color=theme.TEXT if on else theme.MUTED)

    def set(self, value: str) -> None:
        self._value = value
        self._paint()

    def get(self) -> str:
        return self._value

    def configure(self, require_redraw=False, **kwargs):
        values = kwargs.pop("values", None)
        if values is not None and list(values) != list(self._buttons):
            self._build(list(values))
        kwargs.pop("height", None)
        kwargs.pop("width", None)
        if kwargs or require_redraw:
            super().configure(require_redraw=require_redraw, **kwargs)


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

        self.label = ctk.CTkLabel(self, text=label, font=theme.font(12, "bold"), text_color=theme.TEXT,
                                  anchor="w", height=18)
        self.label.grid(row=0, column=0, columnspan=2, sticky="w")

        self.entry = ctk.CTkEntry(self, placeholder_text=placeholder, height=34, corner_radius=8,
                                  border_width=1, border_color=theme.BORDER, fg_color=theme.FIELD,
                                  text_color=theme.TEXT, placeholder_text_color=theme.FAINT,
                                  font=theme.font(13), show="•" if secret else "")
        self.entry.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        self.entry.bind("<KeyRelease>", self._changed)

        if secret:
            self.eye = icon_button(self, "eye", self._toggle_secret)
            self.eye.grid(row=1, column=1, padx=(6, 0), pady=(5, 0))

        self.hint = WrapLabel(self, hint, size=12, wraplength=300)
        self.hint.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(3, 0))
        if not hint:
            self.hint.grid_remove()

    def _changed(self, _event=None) -> None:
        self.set_error(None)
        if self._on_change:
            self._on_change()

    def _toggle_secret(self) -> None:
        hidden = self.entry.cget("show") == "•"
        self.entry.configure(show="" if hidden else "•")
        self.eye.configure(image=icon("eye-off" if hidden else "eye", 15, theme.MUTED))

    def get(self) -> str:
        return self.entry.get().strip()

    def set(self, value) -> None:
        self.entry.delete(0, "end")
        if value not in (None, ""):
            self.entry.insert(0, str(value))
        elif self.focus_get() is not self.entry and hasattr(self.entry, "_activate_placeholder"):
            self.entry._activate_placeholder()  # show the grey example text again in an empty box

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
