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

    # Scroll areas: hide the scrollbar while everything fits (a bar with nothing to scroll looks broken).
    from customtkinter import CTkScrollableFrame
    original_init = CTkScrollableFrame.__init__

    def _init_with_autohide(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        _autohide(self)

    CTkScrollableFrame.__init__ = _init_with_autohide


def _noop() -> None:
    return None


def _autohide(frame) -> None:
    canvas, bar = frame._parent_canvas, frame._scrollbar
    pending = []

    def update():
        pending.clear()
        try:
            box = canvas.bbox("all")
            needed = box is not None and (box[3] - box[1]) > canvas.winfo_height() + 2
            if needed and not bar.winfo_manager():
                bar.grid()
            elif not needed and bar.winfo_manager():
                bar.grid_remove()
                canvas.yview_moveto(0)
        except Exception:  # the window is closing
            pass

    def schedule(_event=None):
        if not pending:
            pending.append(frame.after(30, update))

    frame.bind("<Configure>", schedule, add="+")
    canvas.bind("<Configure>", schedule, add="+")
