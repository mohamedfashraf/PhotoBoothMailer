"""The "QR screen" tab: open the guest-facing QR window and check the guest page is reachable."""
from __future__ import annotations

import os
import webbrowser
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

import config
import netutil
import tunnel as tunnel_mod
from config import Settings
from db import Database
from gui import theme
from gui.qr_window import make_poster
from gui.widgets import Card, StatusLine, WrapLabel, icon_tile, primary_button, secondary_button, title_label

AUTO = "Automatic"
CONNECTIONS = {"online": "Any network (online link)", "wifi": "Same Wi-Fi only"}
CONNECTION_TEXT = {
    "online": "Recommended. Phones can be on any Wi-Fi or on mobile data. The laptop needs internet. "
              "The link is new every time the app starts.",
    "wifi": "No internet needed, but every phone must join the same Wi-Fi or hotspot as this laptop.",
}
MODES = {"shared": "One QR for everyone", "guest": "A QR per guest"}
MODE_TEXT = {
    "shared": "Guests scan the same code, type their name and pick their photos. Show it on the QR screen, "
              "or print the poster and put it next to the booth.",
    "guest": "Each guest gets their own code, shown on the QR screen as soon as their photos are ready. "
             "Staff point the guest to the screen; no typing needed.",
}


class QRPanel(ctk.CTkFrame):
    def __init__(self, master, settings: Settings, db: Database, open_qr: Callable[[], None],
                 url_for: Callable[[str], str], shared_url: Callable[[], str], get_tunnel: Callable = lambda: None,
                 on_change: Callable[[], None] = lambda: None):
        super().__init__(master, fg_color=theme.BG, corner_radius=0)
        self.settings = settings
        self.db = db
        self.url_for = url_for
        self.shared_url = shared_url
        self.get_tunnel = get_tunnel
        self.on_change = on_change  # mode, address or connection changed
        self._tunnel_detail = ""
        self.server_error = ""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=32, pady=(28, 14))
        header.grid_columnconfigure(0, weight=1)
        title_label(header, "QR screen").grid(row=0, column=0, sticky="w")
        WrapLabel(header, "The big QR code your guests scan to get their photos.", size=14).grid(
            row=1, column=0, sticky="ew", pady=(2, 0))

        # Hero card
        # Everything below the title scrolls, so it also fits small laptop screens.
        body = ctk.CTkScrollableFrame(self, fg_color="transparent", scrollbar_button_color=theme.SOFT_HOVER)
        body.grid(row=1, column=0, sticky="nsew", padx=(20, 8))
        body.grid_columnconfigure(0, weight=1)
        hero = Card(body)
        hero.grid(row=0, column=0, sticky="ew", padx=12, pady=(0, 16))
        hero.body.grid_columnconfigure(1, weight=1)
        icon_tile(hero.body, "scan-qr-code", size=64, icon_size=30).grid(row=0, column=0, rowspan=3, sticky="n",
                                                                         padx=(0, 18))
        ctk.CTkLabel(hero.body, text="Show the QR code to your guests", font=theme.font(18, "bold"),
                     text_color=theme.TEXT, anchor="w").grid(row=0, column=1, sticky="ew")
        self.mode = ctk.CTkSegmentedButton(
            hero.body, values=list(MODES.values()), command=self._on_mode, height=38, font=theme.font(13, "bold"),
            selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER, fg_color=theme.SOFT,
            unselected_color=theme.SOFT, unselected_hover_color=theme.SOFT_HOVER, text_color=theme.TEXT)
        self.mode.grid(row=1, column=1, sticky="w", pady=(8, 0))
        self.mode_text = WrapLabel(hero.body, "", size=14)
        self.mode_text.grid(row=2, column=1, sticky="ew", pady=(8, 12))
        buttons = ctk.CTkFrame(hero.body, fg_color="transparent")
        buttons.grid(row=3, column=1, sticky="w")
        primary_button(buttons, "Open QR screen", open_qr, icon_name="qr-code", width=190).pack(side="left")
        self.poster_button = secondary_button(buttons, "Save poster to print", self._save_poster,
                                              icon_name="save", width=210)
        self.poster_button.pack(side="left", padx=(10, 0))
        self.hero_status = StatusLine(hero.body)
        self.hero_status.grid(row=4, column=1, sticky="ew", pady=(10, 0))
        self.hero_status.grid_remove()  # only shown after saving the poster
        WrapLabel(hero.body, "Keys on the QR screen:  ←  →  previous / next guest   ·   F11  full screen   ·   "
                             "Esc  leave full screen", size=12).grid(row=5, column=1, sticky="ew", pady=(6, 0))
        self._show_mode()

        # How phones reach the guest page
        net = Card(body, "How phones connect", "Choose how guests' phones open their photos page.",
                   icon_name="globe")
        net.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 24))
        self.connection = ctk.CTkSegmentedButton(
            net.body, values=list(CONNECTIONS.values()), command=self._on_connection, height=38,
            font=theme.font(13, "bold"), selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER,
            fg_color=theme.SOFT, unselected_color=theme.SOFT, unselected_hover_color=theme.SOFT_HOVER,
            text_color=theme.TEXT)
        self.connection.grid(row=0, column=0, sticky="w")
        self.connection_text = WrapLabel(net.body, "", size=13)
        self.connection_text.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.status = StatusLine(net.body)
        self.status.grid(row=2, column=0, sticky="ew", pady=(14, 0))

        # Wi-Fi only: which address of this laptop goes in the QR code
        self.wifi_box = ctk.CTkFrame(net.body, fg_color="transparent")
        self.wifi_box.grid(row=3, column=0, sticky="ew")
        self.wifi_box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.wifi_box, text="Address in the QR code", font=theme.font(13, "bold"),
                     text_color=theme.TEXT, anchor="w").grid(row=0, column=0, sticky="w", pady=(16, 6))
        self.address = ctk.CTkSegmentedButton(
            self.wifi_box, values=[AUTO], command=self._on_address, height=38, font=theme.font(13, "bold"),
            selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER, fg_color=theme.SOFT,
            unselected_color=theme.SOFT, unselected_hover_color=theme.SOFT_HOVER, text_color=theme.TEXT)
        self.address.grid(row=1, column=0, sticky="w")
        WrapLabel(self.wifi_box, "Leave this on Automatic. Only pick another address if phones can't open the page. "
                                 f"Using the laptop's own hotspot? Pick {netutil.HOTSPOT_IP} if it's listed.",
                  size=12).grid(row=2, column=0, sticky="ew", pady=(6, 0))

        row = ctk.CTkFrame(net.body, fg_color="transparent")
        row.grid(row=4, column=0, sticky="w", pady=(16, 0))
        secondary_button(row, "Open guest page on this laptop", self._open_test_page, icon_name="external-link",
                         width=270).pack(side="left")
        secondary_button(row, "Refresh", self.refresh, icon_name="rotate-ccw", width=120).pack(side="left", padx=(10, 0))
        WrapLabel(net.body, "If Windows asks whether to allow network access, click Allow.", size=12).grid(
            row=5, column=0, sticky="ew", pady=(12, 0))
        self.refresh()

    # ------------------------------------------------------------ actions
    def refresh(self) -> None:
        online = self.settings.online
        self.connection.set(CONNECTIONS["online" if online else "wifi"])
        self.connection_text.configure(text=CONNECTION_TEXT["online" if online else "wifi"])
        if online:
            self.wifi_box.grid_remove()
        else:
            self.wifi_box.grid()
        ips = netutil.lan_ips()
        values = [AUTO] + ips[:3]
        if self.settings.host_override and self.settings.host_override not in values:
            values.append(self.settings.host_override)
        self.address.configure(values=values)
        self.address.set(self.settings.host_override or AUTO)

        if self.server_error:
            self.status.show("error", self.server_error)
        elif online:
            tunnel = self.get_tunnel()
            state = tunnel.state if tunnel else tunnel_mod.STARTING
            if state == tunnel_mod.ONLINE:
                self.status.show("ok", f"Online. Phones can use any Wi-Fi or mobile data.  {tunnel.url}")
            elif state == tunnel_mod.DOWNLOADING:
                self.status.show("info", "Setting up the online link for the first time "
                                         f"(downloading, {self._tunnel_detail or 0}%)…")
            elif state == tunnel_mod.ERROR:
                self.status.show("warning", self._tunnel_detail or "The online link isn't working right now.")
            else:
                self.status.show("info", "Getting the online link ready… (a few seconds)")
        elif not ips:
            self.status.show("warning", "This laptop isn't connected to a network. Connect to Wi-Fi or turn on "
                                        "Mobile Hotspot, then press Refresh.")
        else:
            base = netutil.base_url(self.settings.server_port, self.settings.host_override)
            self.status.show("ok", f"Guest page is running at {base}")

    def set_tunnel(self, state: str, detail: str) -> None:
        self._tunnel_detail = detail
        self.refresh()

    def _on_connection(self, label: str) -> None:
        self.settings.connection = next(k for k, v in CONNECTIONS.items() if v == label)
        try:
            config.save(self.settings)
        except OSError:
            pass
        self.on_change()  # the app starts or stops the online link

    def set_server_error(self, message: str) -> None:
        self.server_error = message
        self.refresh()

    def _on_address(self, value: str) -> None:
        self.settings.host_override = "" if value == AUTO else value
        try:
            config.save(self.settings)
        except OSError:
            pass
        self.refresh()
        self.on_change()

    def _on_mode(self, label: str) -> None:
        self.settings.qr_mode = next(k for k, v in MODES.items() if v == label)
        self.settings.guest_search = True  # name search is what the shared code opens
        try:
            config.save(self.settings)
        except OSError:
            pass
        self._show_mode()
        self.on_change()

    def _show_mode(self) -> None:
        mode = self.settings.qr_mode if self.settings.qr_mode in MODES else "shared"
        self.mode.set(MODES[mode])
        self.mode_text.configure(text=MODE_TEXT[mode])
        self.hero_status.grid_remove()
        if mode == "shared":
            self.poster_button.pack(side="left", padx=(10, 0))
        else:
            self.poster_button.pack_forget()

    def refresh_mode(self) -> None:
        self._show_mode()

    def _save_poster(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(), title="Save the QR poster", defaultextension=".png",
            initialfile="PhotoBooth QR poster.png", initialdir=os.path.join(os.path.expanduser("~"), "Pictures"),
            filetypes=[("PNG image", "*.png")])
        if not path:
            return
        url = self.shared_url()
        if not url:
            self.hero_status.grid()
            self.hero_status.show("warning", "The online link isn't ready yet. Wait a few seconds and try again.")
            return
        try:
            make_poster(url, self.settings.event_name).save(path)
        except OSError as exc:
            self.hero_status.grid()
            self.hero_status.show("error", f"Could not save the poster: {exc}")
            return
        self.hero_status.grid()
        note = (" The online link changes when the app restarts, so print it after starting the app on "
                "event day (or use Same Wi-Fi only)." if self.settings.online else "")
        self.hero_status.show("ok", f"Poster saved: {path}. Open it and print it (A4).{note}")

    def _open_test_page(self) -> None:
        sessions = self.db.ready_sessions(self.settings.watch_folder) if self.settings.watch_folder else []
        if not self.shared_url():
            self.status.show("info", "The online link isn't ready yet. Wait a few seconds.")
            return
        if self.settings.qr_mode == "shared":
            webbrowser.open(self.shared_url())
            return
        if not sessions:
            self.status.show("info", "No guests are ready yet. Add photos to the folder first.")
            return
        webbrowser.open(self.url_for(sessions[-1]["token"]))
