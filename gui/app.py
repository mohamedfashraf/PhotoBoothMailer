"""Main window: setup guide on first launch, then sidebar + screens."""
from __future__ import annotations

import queue

import customtkinter as ctk

from config import APP_NAME, Settings, resource_path
import netutil
from db import Database
from server import GuestServer
from tunnel import Tunnel
from watcher import FolderWatcher
from gui import ctk_patches, icons, theme
from gui.icons import icon

ctk_patches.apply()
from gui.guests import GuestsView
from gui.qr_panel import QRPanel
from gui.qr_window import QRWindow
from gui.settings import SettingsView
from gui.setup_wizard import SetupWizard
from gui.widgets import Card, WrapLabel, icon_tile, secondary_button, shorten_path, show_page, title_label

NAV = [("guests", "Guests", "users"), ("qr", "QR screen", "qr-code"), ("settings", "Settings", "settings")]
MIN_SIZE = (860, 540)  # in customtkinter units (before Windows display scaling)


def _work_area(root) -> tuple[float, float]:
    """Usable screen size (without the taskbar) in customtkinter units."""
    try:
        import ctypes
        from ctypes import wintypes
        rect = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
        scale = ctk.ScalingTracker.get_window_scaling(root) or 1.0
        return (rect.right - rect.left) / scale, (rect.bottom - rect.top) / scale
    except Exception:
        return root.winfo_screenwidth(), root.winfo_screenheight() - 60


class App(ctk.CTk):
    def __init__(self, settings: Settings, force_setup: bool = False):
        super().__init__()
        # Start fully transparent. customtkinter only paints its rounded widgets once the window is
        # really on screen, so we let it paint while invisible and fade in when it's done.
        # That way nobody ever sees a half-drawn window.
        self.attributes("-alpha", 0.0)
        icons.reset_cache()
        self.settings = settings
        theme.pick_font_family(self)
        self.title(APP_NAME)
        self.configure(fg_color=theme.BG)
        self._set_window_icon()
        self.minsize(*MIN_SIZE)
        self._center(1040, 700)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._layout: ctk.CTkFrame | None = None
        self.views: dict[str, ctk.CTkFrame] = {}
        self.nav_buttons: dict[str, ctk.CTkButton] = {}

        # Background work (folder watcher) reports through this queue; the GUI reads it every 250 ms.
        self.db = Database()
        self.events: queue.Queue = queue.Queue()
        self.watcher: FolderWatcher | None = None
        self.server: GuestServer | None = None
        self.tunnel: Tunnel | None = None
        self.qr_window: QRWindow | None = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(250, self._poll_events)

        if force_setup or not settings.setup_complete:
            self.show_wizard()
        else:
            self.show_main()
        self.after(250, self._reveal)

    def _reveal(self) -> None:
        """Finish painting, then fade the window in and bring it to the front."""
        self.update_idletasks()
        self.lift()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))
        self.focus_force()
        self._fade_in(0.0)

    def _fade_in(self, alpha: float) -> None:
        alpha = min(1.0, alpha + 0.2)
        self.attributes("-alpha", alpha)
        if alpha < 1.0:
            self.after(16, lambda: self._fade_in(alpha))

    def _set_window_icon(self) -> None:
        ico = resource_path("assets/app.ico")
        if ico.exists():
            try:
                self.iconbitmap(default=str(ico))
            except Exception:
                pass

    def _center(self, width: int, height: int) -> None:
        """Open at a comfortable size (never more than ~75% of the screen), centred."""
        screen_w, screen_h = _work_area(self)
        width = int(max(MIN_SIZE[0], min(width, screen_w * 0.75)))
        height = int(max(MIN_SIZE[1], min(height, screen_h * 0.85)))
        x = int((screen_w - width) / 2)
        y = int(max(0, (screen_h - height) / 2))
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _swap_layout(self, build) -> None:
        """Build the next screen completely (not yet visible), then swap it in, then drop the old one.

        The old screen stays on display while the new one is built, so there's no half-drawn moment.
        """
        old = self._layout
        if old is not None:
            self.configure(cursor="watch")  # "working on it" while the next screen is built
            self.update_idletasks()
        self.views = {}
        self.nav_buttons = {}
        new = ctk.CTkFrame(self, fg_color=theme.BG, corner_radius=0)
        build(new)
        new.grid(row=0, column=0, sticky="nsew")
        self._layout = new
        if old is None:
            return
        # Let the new screen draw underneath the old one, then remove the old one.
        new.lower(old)
        self.update()
        old.destroy()
        self.configure(cursor="")

    # ------------------------------------------------------------ setup guide
    def show_wizard(self) -> None:
        self.stop_watcher()

        def build(parent):
            parent.grid_columnconfigure(0, weight=1)
            parent.grid_rowconfigure(0, weight=1)
            SetupWizard(parent, self.settings, on_finish=self.show_main).grid(row=0, column=0, sticky="nsew")
        self._swap_layout(build)

    # ------------------------------------------------------------ main layout
    def show_main(self) -> None:
        self._swap_layout(self._build_main)
        self.start_watcher()
        self.start_server()
        self.update_tunnel()

    # ------------------------------------------------------------ guest web page + QR screen
    def base_url(self) -> str:
        """Address phones use for the guest page; "" while the online link is still being set up."""
        if self.settings.online:
            return self.tunnel.url if self.tunnel is not None else ""
        return netutil.base_url(self.settings.server_port, self.settings.host_override)

    def url_for(self, token: str) -> str:
        base = self.base_url()
        return f"{base}/s/{token}" if base else ""

    def shared_url(self) -> str:
        base = self.base_url()
        return base + "/" if base else ""

    def update_tunnel(self) -> None:
        """Start or stop the online link to match the settings."""
        if self.settings.online and self.server is not None:
            if self.tunnel is None:
                self.tunnel = Tunnel(self.settings.server_port,
                                     on_change=lambda state, detail: self.events.put(("tunnel", (state, detail))))
                self.tunnel.start()
        elif self.tunnel is not None:
            self.tunnel.stop()
            self.tunnel = None
        self._refresh_qr()

    def start_server(self) -> None:
        if self.server is not None:
            return
        port = self.settings.server_port
        if not netutil.port_is_free(port):
            self._server_error(f"Port {port} is already used by another program. Close it, or pick another "
                               "port in Settings → More options and restart the app.")
            return
        self.server = GuestServer(self.settings, self.db,
                                  on_activity=lambda session: self.events.put(("activity", session)))
        try:
            self.server.start(port)
        except Exception as exc:  # noqa: BLE001
            self.server = None
            self._server_error(f"The guest page couldn't start: {exc}")

    def _server_error(self, message: str) -> None:
        panel = self.views.get("qr")
        if panel is not None:
            panel.set_server_error(message)

    def open_qr(self, session_id: int | None = None) -> None:
        if self.qr_window is None or not self.qr_window.winfo_exists():
            self.qr_window = QRWindow(self, self.settings, self.db, self.url_for, self.shared_url)
        else:
            self.qr_window.deiconify()
            self.qr_window.lift()
            self.qr_window.focus_force()
        if session_id is not None:
            self.qr_window.show_session(session_id)  # switches to per-guest mode
            if "qr" in self.views:
                self.views["qr"].refresh_mode()

    def _qr_address_changed(self, _event=None) -> None:
        self.update_tunnel()

    def _refresh_qr(self) -> None:
        if self.qr_window is not None and self.qr_window.winfo_exists():
            self.qr_window._render()
        if "qr" in self.views:
            self.views["qr"].refresh()

    # ------------------------------------------------------------ folder watcher
    def start_watcher(self) -> None:
        """(Re)start watching the photos folder from the settings."""
        folder = self.settings.watch_folder
        if self.watcher is not None and self.watcher.folder == folder and not self.watcher._stop.is_set():
            return
        self.stop_watcher()
        if not folder:
            return
        self.watcher = FolderWatcher(folder, self.db,
                                     on_guest=lambda s: self.events.put(("guest", s)),
                                     on_status=lambda ok: self.events.put(("folder", ok)))
        self.watcher.start()

    def stop_watcher(self) -> None:
        if self.watcher is not None:
            self.watcher.stop()
            self.watcher = None

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "guest":
                    if "guests" in self.views:
                        self.views["guests"].upsert(payload)
                    if self.qr_window is not None and self.qr_window.winfo_exists():
                        self.qr_window.on_session(payload)
                elif kind == "activity" and "guests" in self.views:
                    self.views["guests"].upsert(payload)  # guest opened or saved their photos
                elif kind == "tunnel":
                    if "qr" in self.views:
                        self.views["qr"].set_tunnel(*payload)
                    self._refresh_qr()
                elif kind == "folder" and self.nav_buttons:
                    self._show_folder_status(payload)
        except queue.Empty:
            pass
        self.after(250, self._poll_events)

    def _on_close(self) -> None:
        self.stop_watcher()
        if self.tunnel is not None:
            self.tunnel.stop()
        if self.server is not None:
            self.server.stop()
        self.destroy()

    def _settings_saved(self) -> None:
        self.start_watcher()  # restarts only if the folder changed
        self.refresh_sidebar()

    def _build_main(self, parent) -> None:
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(parent, fg_color=theme.SIDEBAR, corner_radius=0, width=232)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(len(NAV) + 1, weight=1)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(24, 26))
        icon_tile(brand, "camera", size=36, fg=theme.ACCENT, color=icons.WHITE).grid(row=0, column=0, rowspan=2)
        ctk.CTkLabel(brand, text="PhotoBooth", font=theme.font(15, "bold"), text_color=theme.TEXT,
                     anchor="w", height=18).grid(row=0, column=1, sticky="sw", padx=(12, 0))
        ctk.CTkLabel(brand, text="Photo sharing", font=theme.font(12), text_color=theme.MUTED,
                     anchor="w", height=16).grid(row=1, column=1, sticky="nw", padx=(12, 0))

        for i, (key, label, icon_name) in enumerate(NAV, start=1):
            button = ctk.CTkButton(sidebar, text=f"  {label}", anchor="w", height=42, corner_radius=10,
                                   font=theme.font(14, "bold"), fg_color="transparent",
                                   hover_color=theme.SOFT, text_color=theme.TEXT, compound="left",
                                   image=icon(icon_name, 18, theme.MUTED),
                                   command=lambda k=key: self.select(k))
            button.grid(row=i, column=0, sticky="ew", padx=12, pady=2)
            self.nav_buttons[key] = button

        event_box = ctk.CTkFrame(sidebar, fg_color=theme.FIELD, corner_radius=14)
        event_box.grid(row=len(NAV) + 2, column=0, sticky="ew", padx=12, pady=14)
        event_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(event_box, text="CURRENT EVENT", font=theme.font(10, "bold"),
                     text_color=theme.MUTED, anchor="w", height=14).grid(row=0, column=0, sticky="ew",
                                                                          padx=14, pady=(12, 2))
        self.event_label = WrapLabel(event_box, "", size=14, weight="bold", color=theme.TEXT, wraplength=180)
        self.event_label.grid(row=1, column=0, sticky="ew", padx=14)
        self.folder_label = ctk.CTkLabel(event_box, text="", font=theme.font(12), anchor="w", compound="left",
                                         height=18)
        self.folder_label.grid(row=2, column=0, sticky="ew", padx=14, pady=(6, 12))

        self.content = ctk.CTkFrame(parent, fg_color=theme.BG, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        # Build every screen up front (while still invisible), so switching tabs is instant.
        for key, _, _ in NAV:
            view = self._make_view(key)
            view.grid(row=0, column=0, sticky="nsew")
            self.views[key] = view
        self.refresh_sidebar()
        self.select("guests" if self.settings.is_ready else "settings")

    def refresh_sidebar(self) -> None:
        s = self.settings
        self.event_label.configure(text=s.event_name or "No event name yet")
        self._show_folder_status(s.folder_ok)
        for view in self.views.values():
            if hasattr(view, "refresh"):
                view.refresh()

    def _show_folder_status(self, ok: bool) -> None:
        if ok:
            self.folder_label.configure(text="  Watching photos folder", text_color=theme.SUCCESS,
                                        image=icon("folder-check", 14, theme.SUCCESS))
        else:
            self.folder_label.configure(text="  Photos folder missing", text_color=theme.ERROR,
                                        image=icon("circle-alert", 14, theme.ERROR))

    def select(self, key: str) -> None:
        for name, button in self.nav_buttons.items():
            active = name == key
            icon_name = next(i for k, _, i in NAV if k == name)
            button.configure(fg_color=theme.ACCENT_SOFT if active else "transparent",
                             text_color=theme.ACCENT_TEXT if active else theme.TEXT,
                             image=icon(icon_name, 18, theme.ACCENT_TEXT if active else theme.MUTED))
        show_page(self.views[key])

    def _make_view(self, key: str) -> ctk.CTkFrame:
        if key == "settings":
            return SettingsView(self.content, self.settings, on_saved=self._settings_saved,
                                on_run_setup=self.show_wizard)
        if key == "qr":
            panel = QRPanel(self.content, self.settings, self.db, open_qr=self.open_qr, url_for=self.url_for,
                            shared_url=self.shared_url, get_tunnel=lambda: self.tunnel,
                            on_change=self._qr_address_changed)
            return panel
        return GuestsView(self.content, self.settings, self.db, on_open=self.open_qr)


class EmptyState(ctk.CTkFrame):
    """A page header plus a friendly centred message."""

    def __init__(self, master, title: str, heading: str, icon_name: str, text: str,
                 subtitle: str = "", button: tuple[str, str] | None = None):
        super().__init__(master, fg_color=theme.BG, corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=32, pady=(28, 14))
        header.grid_columnconfigure(0, weight=1)
        title_label(header, title).grid(row=0, column=0, sticky="w")
        if subtitle:
            WrapLabel(header, subtitle, size=14).grid(row=1, column=0, sticky="ew", pady=(2, 0))

        card = Card(self)
        card.grid(row=1, column=0, sticky="nsew", padx=32, pady=(0, 32))
        inner = ctk.CTkFrame(card.body, fg_color="transparent")
        inner.place(relx=0.5, rely=0.46, anchor="center")
        icon_tile(inner, icon_name, size=72, icon_size=34).pack()
        self.heading = ctk.CTkLabel(inner, text=heading, font=theme.font(19, "bold"), text_color=theme.TEXT)
        self.heading.pack(pady=(16, 4))
        self.message = ctk.CTkLabel(inner, text=text, font=theme.font(14), text_color=theme.MUTED,
                                    justify="center", wraplength=440)
        self.message.pack()
        if button:
            secondary_button(inner, button[0], None, icon_name=button[1], width=190,
                             state="disabled").pack(pady=(18, 0))
            ctk.CTkLabel(inner, text="Coming in the next update", font=theme.font(12),
                         text_color=theme.MUTED).pack(pady=(6, 0))
