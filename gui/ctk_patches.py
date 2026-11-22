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

    # Resizing the window: customtkinter redraws every rounded widget (on every tab, even hidden ones)
    # for every pixel the window changes, which made dragging the window edge lag ~0.5 s per step.
    # Instead, remember which widgets changed size and redraw them all once, shortly after the size
    # stops changing.
    from customtkinter.windows.widgets.core_widget_classes.ctk_base_class import CTkBaseClass

    def _update_dimensions_deferred(self, event):
        width = self._reverse_widget_scaling(event.width)
        height = self._reverse_widget_scaling(event.height)
        if round(self._current_width) != round(width) or round(self._current_height) != round(height):
            self._current_width = width
            self._current_height = height
            _redraw_later(self)

    CTkBaseClass._update_dimensions_event = _update_dimensions_deferred


def _noop() -> None:
    return None


REDRAW_DELAY_MS = 70
_dirty: dict = {}  # widget id -> widget whose size changed and still needs a redraw
_flush_job: dict = {}  # toplevel -> pending after() id


def _redraw_later(widget) -> None:
    _dirty[id(widget)] = widget
    try:
        root = widget.winfo_toplevel()
        job = _flush_job.pop(root, None)
        if job is not None:
            root.after_cancel(job)
        _flush_job[root] = root.after(REDRAW_DELAY_MS, lambda: _flush(root))
    except Exception:  # widget already destroyed
        _dirty.pop(id(widget), None)


def _flush(root) -> None:
    _flush_job.pop(root, None)
    widgets = list(_dirty.values())
    _dirty.clear()
    for widget in widgets:
        try:
            if widget.winfo_exists():
                widget._draw(no_color_updates=True)
        except Exception:
            pass


def flush_redraws() -> None:
    """Draw everything that's waiting right now (used by tests and screenshots)."""
    for root in list(_flush_job):
        try:
            root.after_cancel(_flush_job[root])
        except Exception:
            pass
        _flush(root)


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
