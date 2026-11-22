"""The guest-facing QR screen, in its own window. Two modes (Settings: qr_mode):

- shared: ONE QR code for everyone. Guests scan it, type their name and pick their photos.
- guest:  a QR code per guest, following new guests automatically as soon as their photos are ready.

Per-guest mode:
- Previous / Next (or ← →) re-shows an older guest's code. While you look back, new guests don't
  interrupt; a "Show newest" button appears instead.
- F11 or the button toggles fullscreen (for a second monitor or tablet). Esc leaves fullscreen.
"""
from __future__ import annotations

import os
from typing import Callable

import customtkinter as ctk
import qrcode
from PIL import Image, ImageDraw, ImageFont

from config import APP_NAME, Settings, resource_path
from db import STATUS_READY, Database
from gui import theme
from gui.icons import icon
from gui.widgets import icon_tile, rtl_fix

QR_DARK = "#15161C"
CONTROLS_HEIGHT = 84  # room kept free at the bottom for the floating toolbar (not in full screen)
TOOLBAR_HIDE_MS = 2500


def make_qr(url: str, px: int) -> Image.Image:
    """Crisp QR image exactly px×px (whole-pixel modules, white quiet zone)."""
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0, box_size=1)
    qr.add_data(url)
    qr.make(fit=True)
    modules = qr.make_image(fill_color=QR_DARK, back_color="white").get_image().convert("RGB")
    n = modules.width
    scale = max(1, px // n)
    sharp = modules.resize((n * scale, n * scale), Image.NEAREST)
    canvas = Image.new("RGB", (px, px), "white")
    canvas.paste(sharp, ((px - sharp.width) // 2, (px - sharp.height) // 2))
    return canvas


def make_poster(url: str, event_name: str) -> Image.Image:
    """A printable A4 sign (150 dpi) with the shared QR code."""
    width, height = 1240, 1754
    poster = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(poster)

    def font(size: int, bold: bool = False):
        for name in (("segoeuib.ttf", "arialbd.ttf") if bold else ("segoeui.ttf", "arial.ttf")):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    draw.rectangle([0, 0, width, 22], fill="#5B5BF7")
    if event_name:
        draw.text((width // 2, 190), event_name, font=font(52, True), fill="#686C7E", anchor="mm")
    draw.text((width // 2, 300), "Get your photos!", font=font(110, True), fill="#15161C", anchor="mm")
    qr = make_qr(url, 820)
    poster.paste(qr, ((width - 820) // 2, 420))
    steps = ["1   Scan with your phone camera", "2   Type your name", "3   Save your photos"]
    step_font = font(56, True)
    left = (width - max(draw.textlength(step, font=step_font) for step in steps)) / 2  # numbers line up
    for i, step in enumerate(steps):
        draw.text((left, 1350 + i * 90), step, font=step_font, fill="#15161C", anchor="lm")
    draw.text((width // 2, 1660), "Connect to the event Wi-Fi first if the page doesn't open.",
              font=font(36), fill="#686C7E", anchor="mm")
    return poster


class QRWindow(ctk.CTkToplevel):
    def __init__(self, master, settings: Settings, db: Database, url_for: Callable[[str], str],
                 shared_url: Callable[[], str]):
        super().__init__(master)
        self.attributes("-alpha", 0.0)  # appear only once fully drawn
        self.settings = settings
        self.db = db
        self.url_for = url_for
        self.shared_url = shared_url
        self.sessions: list[dict] = []
        self.index = -1
        self.follow_newest = True
        self._render_job = None
        self._last_render_key = None
        self._fullscreen = False

        self.title(f"QR screen · {APP_NAME}")
        self.configure(fg_color=theme.BG)
        self.minsize(360, 460)
        self._place_window()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Stage: what guests see
        self.stage = ctk.CTkFrame(self, fg_color=theme.BG, corner_radius=0)
        self.stage.grid(row=0, column=0, sticky="nsew")
        self.content = ctk.CTkFrame(self.stage, fg_color="transparent")
        self.content.place(relx=0.5, rely=0.5, anchor="center")
        self.event_label = ctk.CTkLabel(self.content, text="", font=theme.font(15, "bold"), text_color=theme.MUTED)
        self.event_label.pack()
        self.headline = ctk.CTkLabel(self.content, text="Scan to get your photos", text_color=theme.TEXT,
                                     font=theme.font(30, "bold"))
        self.headline.pack(pady=(2, 16))
        self.qr_card = ctk.CTkFrame(self.content, fg_color=("#FFFFFF", "#FFFFFF"), corner_radius=28)
        self.qr_card.pack()
        self.qr_label = ctk.CTkLabel(self.qr_card, text="")
        self.qr_label.pack(padx=24, pady=24)
        self.name_label = ctk.CTkLabel(self.content, text="", text_color=theme.TEXT, font=theme.font(36, "bold"))
        self.name_label.pack(pady=(18, 0))
        self.hint_label = ctk.CTkLabel(self.content, text="Point your phone camera at the code",
                                       font=theme.font(15), text_color=theme.MUTED)
        self.hint_label.pack(pady=(2, 0))

        # Empty state (no ready guests yet)
        self.empty = ctk.CTkFrame(self.stage, fg_color="transparent")
        icon_tile(self.empty, "camera", size=84, icon_size=40).pack()
        self.empty_title = ctk.CTkLabel(self.empty, text="Waiting for the first guest…", font=theme.font(24, "bold"),
                                        text_color=theme.TEXT)
        self.empty_title.pack(pady=(18, 4))
        self.empty_event = ctk.CTkLabel(self.empty, text="", font=theme.font(15), text_color=theme.MUTED)
        self.empty_event.pack()
        self.empty_progress = ctk.CTkProgressBar(self.empty, width=260, height=6, corner_radius=3, mode="indeterminate",
                                                 progress_color=theme.ACCENT, fg_color=theme.SOFT)

        # Staff toolbar: a small floating pill at the bottom. In full screen it hides itself and
        # comes back for a moment when the mouse moves.
        self.controls = ctk.CTkFrame(self.stage, fg_color=theme.CARD, corner_radius=18, border_width=1,
                                     border_color=theme.BORDER)
        self.prev_button = self._tool_button("", "chevron-left", self.previous, width=40)
        self.prev_button.grid(row=0, column=0, padx=(6, 0), pady=6)
        self.counter = ctk.CTkLabel(self.controls, text="", font=theme.font(13, "bold"), text_color=theme.MUTED,
                                    width=64)
        self.counter.grid(row=0, column=1)
        self.next_button = self._tool_button("", "chevron-right", self.next, width=40)
        self.next_button.grid(row=0, column=2, pady=6)
        self.sep1 = ctk.CTkFrame(self.controls, width=1, height=24, fg_color=theme.BORDER)
        self.sep1.grid(row=0, column=3, padx=6)
        self.newest_button = ctk.CTkButton(
            self.controls, text="  Newest guest", image=icon("sparkles", 16, theme.ACCENT_TEXT), compound="left",
            command=self.show_newest, height=40, corner_radius=12, fg_color=theme.ACCENT_SOFT,
            hover_color=theme.SOFT_HOVER, text_color=theme.ACCENT_TEXT, font=theme.font(13, "bold"), width=150)
        self.newest_button.grid(row=0, column=4, padx=(0, 6))
        self.newest_button.grid_remove()
        self.full_button = self._tool_button("  Full screen", "maximize", self.toggle_fullscreen, width=140)
        self.full_button.grid(row=0, column=5, padx=(0, 6), pady=6)
        self.controls.place(relx=0.5, rely=1.0, y=-18, anchor="s")
        self._toolbar_job = None
        self.esc_hint = ctk.CTkLabel(self.stage, text="  Move the mouse to show controls  ·  Esc to leave full screen  ",
                                     font=theme.font(13), text_color=theme.MUTED, fg_color=theme.CARD,
                                     corner_radius=10, height=34)

        self.bind("<Configure>", self._on_resize, add="+")
        self.bind("<Left>", lambda _e: self.previous())
        self.bind("<Right>", lambda _e: self.next())
        self.bind("<F11>", lambda _e: self.toggle_fullscreen())
        self.bind("<Escape>", lambda _e: self._fullscreen and self.toggle_fullscreen())
        self.bind("<Motion>", self._on_mouse_move, add="+")

        self.reload()
        # CTkToplevel resets its icon shortly after opening; set ours afterwards.
        self.after(260, self._set_icon)
        self.after(220, self._reveal)

    def _hide_progress(self) -> None:
        if self.empty_progress.winfo_manager():
            self.empty_progress.stop()
            self.empty_progress.pack_forget()

    def _set_icon(self) -> None:
        ico = resource_path("assets/app.ico")
        if ico.exists():
            try:
                self.iconbitmap(str(ico))
            except Exception:
                pass

    def _reveal(self) -> None:
        self.update_idletasks()
        self.attributes("-alpha", 1.0)
        self.lift()
        self.focus_force()

    def _place_window(self) -> None:
        """Open at a modest size (staff can maximise it or press Full screen), next to the main window."""
        from gui.app import _work_area  # real usable screen size, correct with Windows display scaling
        master = self.master
        scale = ctk.ScalingTracker.get_window_scaling(self) or 1.0
        sw, sh = _work_area(master)
        width = int(min(480, sw * 0.45))
        height = int(min(620, sh * 0.75))
        try:  # to the right of the main window when there's room, else centred
            x = int((master.winfo_rootx() + master.winfo_width()) / scale - width / 2)
        except Exception:
            x = int((sw - width) / 2)
        x = max(0, min(x, int(sw - width)))
        y = max(0, int((sh - height) / 2))
        self.geometry(f"{width}x{height}+{x}+{y}")

    # ------------------------------------------------------------ data
    def reload(self) -> None:
        current_id = self.current["id"] if self.current else None
        self.sessions = self.db.ready_sessions(self.settings.watch_folder) if self.settings.watch_folder else []
        if self.follow_newest or current_id is None:
            self.index = len(self.sessions) - 1
        else:
            ids = [s["id"] for s in self.sessions]
            self.index = ids.index(current_id) if current_id in ids else len(self.sessions) - 1
        self._render()

    @property
    def current(self) -> dict | None:
        return self.sessions[self.index] if 0 <= self.index < len(self.sessions) else None

    def on_session(self, session: dict) -> None:
        """Live update from the folder watcher."""
        if session["status"] != STATUS_READY:
            return
        ids = [s["id"] for s in self.sessions]
        if session["id"] in ids:
            self.sessions[ids.index(session["id"])] = session
            if session["photo_count"] == 0:
                self.reload()
                return
        elif session["photo_count"] > 0:
            self.sessions.append(session)
            if self.follow_newest:
                self.index = len(self.sessions) - 1
        self._render()

    def show_session(self, session_id: int) -> None:
        """Show a specific guest (e.g. double-clicked in the Guests list): switches to per-guest mode."""
        self.settings.qr_mode = "guest"
        self.reload()
        ids = [s["id"] for s in self.sessions]
        if session_id in ids:
            self.index = ids.index(session_id)
            self.follow_newest = self.index == len(self.sessions) - 1
            self._render()

    # ------------------------------------------------------------ navigation
    def previous(self) -> None:
        if self.index > 0:
            self.index -= 1
            self.follow_newest = False
            self._render()

    def next(self) -> None:
        if self.index < len(self.sessions) - 1:
            self.index += 1
            self.follow_newest = self.index == len(self.sessions) - 1
            self._render()

    def show_newest(self) -> None:
        self.follow_newest = True
        self.index = len(self.sessions) - 1
        self._render()

    def _tool_button(self, text: str, icon_name: str, command, width: int) -> ctk.CTkButton:
        return ctk.CTkButton(self.controls, text=text, image=icon(icon_name, 18, theme.TEXT), compound="left",
                             command=command, width=width, height=40, corner_radius=12, fg_color="transparent",
                             hover_color=theme.SOFT, text_color=theme.TEXT, text_color_disabled=theme.MUTED,
                             font=theme.font(13, "bold"))

    def toggle_fullscreen(self) -> None:
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self._saved_geometry = self.geometry()
            self.attributes("-fullscreen", True)
            self._cover_monitor()
            self.full_button.configure(text="  Exit full screen", image=icon("minimize", 18, theme.TEXT), width=170)
            self.controls.place_forget()
            self.esc_hint.place(relx=0.5, rely=1.0, y=-18, anchor="s")
            self.after(3500, lambda: self._fullscreen and self.esc_hint.place_forget())
        else:
            self.attributes("-fullscreen", False)
            if getattr(self, "_saved_geometry", None):
                self.geometry(self._saved_geometry)
            self.full_button.configure(text="  Full screen", image=icon("maximize", 18, theme.TEXT), width=140)
            self.esc_hint.place_forget()
            self.controls.place(relx=0.5, rely=1.0, y=-18, anchor="s")
        self._schedule_render()

    def _cover_monitor(self) -> None:
        """Make full screen really cover the whole monitor.

        With Windows display scaling (e.g. 150%), Tk's own full screen only covers part of the screen
        (the top-left 2/3). Ask Windows for the monitor's real size and resize the window to it.
        """
        if os.name != "nt":
            return
        try:
            import ctypes
            from ctypes import wintypes

            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                            ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

            user32 = ctypes.windll.user32
            self.update_idletasks()
            hwnd = user32.GetParent(self.winfo_id())
            monitor = user32.MonitorFromWindow(hwnd, 2)  # the monitor the window is on
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            user32.GetMonitorInfoW(monitor, ctypes.byref(info))
            r = info.rcMonitor
            user32.SetWindowPos(hwnd, 0, r.left, r.top, r.right - r.left, r.bottom - r.top, 0x0040 | 0x0004)
        except Exception:
            pass

    def _centre_offset(self) -> int:
        """Centre the content in the space above the floating toolbar (whole screen in full screen)."""
        return 0 if self._fullscreen else -CONTROLS_HEIGHT // 2

    def _on_mouse_move(self, _event=None) -> None:
        if not self._fullscreen:
            return
        self.esc_hint.place_forget()
        self.controls.place(relx=0.5, rely=1.0, y=-18, anchor="s")
        if self._toolbar_job is not None:
            self.after_cancel(self._toolbar_job)
        self._toolbar_job = self.after(TOOLBAR_HIDE_MS, self._hide_toolbar)

    def _hide_toolbar(self) -> None:
        self._toolbar_job = None
        if self._fullscreen:
            self.controls.place_forget()

    # ------------------------------------------------------------ drawing
    def _on_resize(self, event) -> None:
        if event.widget is self:
            self._schedule_render()

    def _schedule_render(self) -> None:
        if self._render_job is not None:
            self.after_cancel(self._render_job)
        self._render_job = self.after(80, self._render)

    def _render(self) -> None:
        self._render_job = None
        shared = self.settings.qr_mode == "shared"
        session = None if shared else self.current
        event = self.settings.event_name or ""
        count = len(self.sessions)

        # Controls (per-guest navigation only makes sense in per-guest mode)
        for widget in (self.prev_button, self.counter, self.next_button, self.sep1):
            if shared:
                widget.grid_remove()
            else:
                widget.grid()
        self.counter.configure(text=f"{self.index + 1} of {count}" if count else "–")
        self.prev_button.configure(state="normal" if self.index > 0 else "disabled")
        self.next_button.configure(state="normal" if 0 <= self.index < count - 1 else "disabled")
        if not shared and not self.follow_newest and count and self.index < count - 1:
            self.newest_button.grid()
        else:
            self.newest_button.grid_remove()

        url = ""
        if shared:
            url = self.shared_url()
        elif session is not None:
            url = self.url_for(session["token"])
        if (session is not None or shared) and not url:
            # Online link still connecting: never show a QR code that wouldn't work.
            self.content.place_forget()
            self.empty_title.configure(text="Getting the online link ready…")
            self.empty_event.configure(text="This takes a few seconds. Check the laptop's internet if it takes longer.")
            if not self.empty_progress.winfo_manager():
                self.empty_progress.pack(pady=(18, 0))
                self.empty_progress.start()
            self.empty.place(relx=0.5, rely=0.5, y=self._centre_offset(), anchor="center")
            self._last_render_key = None
            return
        if session is None and not shared:
            self.content.place_forget()
            self._hide_progress()
            self.empty_title.configure(text="Waiting for the first guest…")
            self.empty_event.configure(text=event)
            self.empty.place(relx=0.5, rely=0.5, y=self._centre_offset(), anchor="center")
            return
        self.empty.place_forget()
        self._hide_progress()
        self.content.place(relx=0.5, rely=0.5, y=self._centre_offset(), anchor="center")

        # Size the QR to the window (in customtkinter units), leaving room for the text.
        scale = ctk.ScalingTracker.get_widget_scaling(self) or 1.0
        width = self.winfo_width() / scale
        height = self.winfo_height() / scale - (0 if self._fullscreen else CONTROLS_HEIGHT)
        # Text above and below the code takes ~240 units (its fonts grow with the code), and the white
        # frame adds 1/8 of the code size. Keep a small margin so nothing touches the screen edge.
        side = int(max(160, min(width * 0.8, (height - 250) / 1.3, 900)))
        name_size = int(max(26, min(56, side / 9)))

        key = (url, side, scale)
        if key != self._last_render_key:
            px = int(round(side * scale))
            image = make_qr(url, px)
            self.qr_label.configure(image=ctk.CTkImage(light_image=image, dark_image=image, size=(side, side)))
            self._last_render_key = key
        self.qr_card.configure(corner_radius=max(16, side // 16))
        self.qr_label.pack_configure(padx=max(14, side // 16), pady=max(14, side // 16))
        self.event_label.configure(text=event)
        self.headline.configure(text="Get your photos" if shared else "Scan to get your photos",
                                font=theme.font(int(max(22, min(40, side / 14))), "bold"))
        if shared:
            self.name_label.configure(text="Scan, then type your name", font=theme.font(int(name_size * 0.75), "bold"))
            self.hint_label.configure(text="Point your phone camera at the code. Your photos will be waiting.")
        else:
            self.name_label.configure(text=rtl_fix(session["name"]), font=theme.font(name_size, "bold"))
            self.hint_label.configure(text="Point your phone camera at the code")
