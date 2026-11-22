"""Small performance fixes for customtkinter, applied once at startup.

CTkScrollbar._draw() ends with `canvas.update_idletasks()`. While a page with a scroll area is
being built, the scrollbar is redrawn dozens of times, and each forced update re-lays out and
redraws every rounded widget in the window. Opening Settings took ~3.5 s because of it.
Skipping that forced update (the scrollbar still redraws on the next idle cycle) makes it fast.
"""
from __future__ import annotations

_applied = False


def apply() -> None:
    global _applied
    if _applied:
        return
    _applied = True

    from customtkinter.windows.widgets.ctk_scrollbar import CTkScrollbar

    original_draw = CTkScrollbar._draw

    def _draw_without_forced_update(self, no_color_updates=False):
        canvas = self._canvas
        canvas.update_idletasks = _noop  # instance attribute shadows the method for this call only
        try:
            return original_draw(self, no_color_updates)
        finally:
            del canvas.update_idletasks

    CTkScrollbar._draw = _draw_without_forced_update


def _noop() -> None:
    return None
