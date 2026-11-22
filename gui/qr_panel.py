"""The "QR screen" tab.

Top to bottom:
  - header with the main action (Open QR screen)
  - a status banner: can guests' phones reach the photos right now?
  - "What guests scan": one QR for everyone (name search, poster) or one QR per guest
  - "How phones connect": online link (optional permanent address) or same Wi-Fi
"""
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
from gui.icons import icon
from gui.qr_window import make_poster
from gui.widgets import (Card, Field, StatusLine, WrapLabel, link_button, primary_button, secondary_button,
                         title_label)

AUTO = "Automatic"
MODES = {"shared": "One QR for everyone", "guest": "A QR per guest"}
MODE_TEXT = {
    "shared": "Everyone scans the same code, types their name and saves their photos.",
    "guest": "Each guest gets their own code on the QR screen as soon as their photos are ready. No typing.",
}
CONNECTIONS = {"online": "Any network", "wifi": "Same Wi-Fi only"}
CONNECTION_TEXT = {
    "online": "Phones can use any Wi-Fi or mobile data. The laptop needs internet. "
              "The link changes each time the app starts.",
    "permanent": "Phones can use any Wi-Fi or mobile data. The laptop needs internet. "
                 "Your permanent address never changes.",
    "wifi": "No internet needed, but every phone must join the same Wi-Fi or hotspot as this laptop.",
}
PERMANENT_STEPS = (
    "Needs your own domain (like mywedding-photos.com, about $10 a year) on a free Cloudflare account.\n"
    "1.  Cloudflare → Zero Trust → Networks → Tunnels → Create a tunnel → Cloudflared.\n"
    "2.  Copy the token: the long text after --token in the install command (don't run it).\n"
    "3.  Add a public hostname, e.g. photos + your domain. Service: HTTP, URL: localhost:{port}\n"
    "4.  Paste the address and token below and press Save."
)

# Status banner looks: (icon, icon colour, tile colour)
WARNING_SOFT = ("#FEF3C7", "#3A2A0C")
ERROR_SOFT = ("#FDE8E8", "#3B1616")
BANNER = {
    "ok": ("circle-check", theme.SUCCESS, theme.SUCCESS_SOFT),
    "busy": ("hourglass", theme.ACCENT_TEXT, theme.ACCENT_SOFT),
    "warning": ("triangle-alert", theme.WARNING, WARNING_SOFT),
    "error": ("triangle-alert", theme.ERROR, ERROR_SOFT),
}


def _segmented(master, values, command) -> ctk.CTkSegmentedButton:
    return ctk.CTkSegmentedButton(
        master, values=values, command=command, height=32, font=theme.font(13, "bold"),
        selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER, fg_color=theme.SOFT,
        unselected_color=theme.SOFT, unselected_hover_color=theme.SOFT_HOVER, text_color=theme.TEXT)


def _section_label(master, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text=text, font=theme.font(13, "bold"), text_color=theme.TEXT, anchor="w")


def _divider(master) -> ctk.CTkFrame:
    """A small gap between sections of a card (a 1px line doesn't draw reliably in customtkinter)."""
    return ctk.CTkFrame(master, height=2, fg_color="transparent")


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

        # ---- header: title + the main action
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)
        title_label(header, "QR screen").grid(row=0, column=0, sticky="w")
        WrapLabel(header, "What guests scan, and how their phones reach the photos.", size=13).grid(
            row=1, column=0, sticky="ew", pady=(2, 0))
        primary_button(header, "Open QR screen", open_qr, icon_name="qr-code", width=170).grid(
            row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))

        body = ctk.CTkScrollableFrame(self, fg_color="transparent", scrollbar_button_color=theme.SOFT_HOVER)
        body.grid(row=1, column=0, sticky="nsew", padx=(12, 6))
        body.grid_columnconfigure(0, weight=1)

        # ---- status banner
        banner = ctk.CTkFrame(body, fg_color=theme.CARD, corner_radius=16, border_width=1, border_color=theme.BORDER)
        banner.grid(row=0, column=0, sticky="ew", padx=12, pady=(0, 12))
        banner.grid_columnconfigure(1, weight=1)
        self.banner_icon = ctk.CTkLabel(banner, text="", width=38, height=38, corner_radius=11)
        self.banner_icon.grid(row=0, column=0, rowspan=2, padx=(16, 12), pady=12)
        self.banner_title = ctk.CTkLabel(banner, text="", font=theme.font(15, "bold"), text_color=theme.TEXT,
                                         anchor="w", height=20)
        self.banner_title.grid(row=0, column=1, sticky="sew", pady=(12, 0))
        self.banner_text = WrapLabel(banner, "", size=13)
        self.banner_text.grid(row=1, column=1, sticky="new", pady=(1, 12))
        self.progress = ctk.CTkProgressBar(banner, height=4, corner_radius=2, progress_color=theme.ACCENT,
                                           fg_color=theme.SOFT, mode="indeterminate")
        self.progress.grid(row=2, column=0, columnspan=3, sticky="ew", padx=16, pady=(0, 12))
        self.progress.grid_remove()
        actions = ctk.CTkFrame(banner, fg_color="transparent")
        actions.grid(row=0, column=2, rowspan=2, padx=(12, 16))
        secondary_button(actions, "Test", self._open_test_page, icon_name="external-link", height=36,
                         width=96).pack(side="left")
        ctk.CTkButton(actions, text="", image=icon("rotate-ccw", 16, theme.MUTED), width=36, height=36,
                      corner_radius=10, fg_color=theme.SOFT, hover_color=theme.SOFT_HOVER,
                      command=self.refresh).pack(side="left", padx=(6, 0))

        # ---- what guests scan
        scan = Card(body, "What guests scan", icon_name="scan-qr-code")
        scan.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.mode = _segmented(scan.body, list(MODES.values()), self._on_mode)
        self.mode.grid(row=0, column=0, sticky="w")
        self.mode_text = WrapLabel(scan.body, "", size=13)
        self.mode_text.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        self.shared_box = ctk.CTkFrame(scan.body, fg_color="transparent")
        self.shared_box.grid(row=2, column=0, sticky="ew")
        self.shared_box.grid_columnconfigure(0, weight=1)
        _divider(self.shared_box).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        search_row = ctk.CTkFrame(self.shared_box, fg_color="transparent")
        search_row.grid(row=1, column=0, sticky="w")
        _section_label(search_row, "Name search").pack(side="left")
        self.search_choice = _segmented(search_row, ["On", "Off"], self._on_search)
        self.search_choice.configure(height=30, width=110)
        self.search_choice.pack(side="left", padx=(12, 0))
        self.search_text = WrapLabel(self.shared_box, "", size=12)
        self.search_text.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self.poster_button = secondary_button(self.shared_box, "Save poster", self._save_poster,
                                              icon_name="save", width=150, height=36)
        self.poster_button.grid(row=1, column=1, rowspan=2, sticky="e", padx=(16, 0))
        self.scan_status = StatusLine(scan.body)
        self.scan_status.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.scan_status.grid_remove()

        # ---- how phones connect
        net = Card(body, "How phones connect", icon_name="globe")
        net.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 16))
        self.connection = _segmented(net.body, list(CONNECTIONS.values()), self._on_connection)
        self.connection.grid(row=0, column=0, sticky="w")
        self.connection_text = WrapLabel(net.body, "", size=13)
        self.connection_text.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        # online: optional permanent address
        self.perm_box = ctk.CTkFrame(net.body, fg_color="transparent")
        self.perm_box.grid(row=2, column=0, sticky="ew")
        self.perm_box.grid_columnconfigure(0, weight=1)
        _divider(self.perm_box).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        _section_label(self.perm_box, "Permanent address").grid(row=1, column=0, sticky="w")
        self.perm_summary = WrapLabel(self.perm_box, "", size=12)
        self.perm_summary.grid(row=2, column=0, sticky="ew", pady=(2, 0))
        self.perm_toggle = secondary_button(self.perm_box, "Set up", self._toggle_permanent, height=36, width=110)
        self.perm_toggle.grid(row=1, column=1, rowspan=2, sticky="e", padx=(16, 0))

        self.perm_form = ctk.CTkFrame(self.perm_box, fg_color=theme.FIELD, corner_radius=12)
        self.perm_form.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self.perm_form.grid_columnconfigure((0, 1), weight=1, uniform="perm")
        self.perm_steps = WrapLabel(self.perm_form, "", size=12)
        self.perm_steps.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(14, 0))
        link_button(self.perm_form, "Open Cloudflare", "https://one.dash.cloudflare.com/").grid(
            row=1, column=0, sticky="w", padx=16, pady=(8, 12))
        self.perm_host = Field(self.perm_form, "Your address", placeholder="photos.mywedding.com")
        self.perm_host.grid(row=2, column=0, sticky="new", padx=(16, 8))
        self.perm_token = Field(self.perm_form, "Tunnel token", placeholder="eyJhIjoi…", secret=True)
        self.perm_token.grid(row=2, column=1, sticky="new", padx=(8, 16))
        buttons = ctk.CTkFrame(self.perm_form, fg_color="transparent")
        buttons.grid(row=3, column=0, columnspan=2, sticky="w", padx=16, pady=(12, 16))
        primary_button(buttons, "Save", self._save_permanent, icon_name="save", width=110, height=36).pack(side="left")
        self.perm_remove = secondary_button(buttons, "Use the free link instead", self._remove_permanent,
                                            width=210, height=36)
        self.perm_remove.pack(side="left", padx=(10, 0))
        self.perm_status = StatusLine(self.perm_form)
        self.perm_status.grid(row=4, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 14))
        self.perm_form.grid_remove()

        # Wi-Fi: which address goes in the QR code
        self.wifi_box = ctk.CTkFrame(net.body, fg_color="transparent")
        self.wifi_box.grid(row=3, column=0, sticky="ew")
        self.wifi_box.grid_columnconfigure(0, weight=1)
        _divider(self.wifi_box).grid(row=0, column=0, sticky="ew", pady=(10, 6))
        _section_label(self.wifi_box, "Laptop address in the QR code").grid(row=1, column=0, sticky="w")
        self.address = _segmented(self.wifi_box, [AUTO], self._on_address)
        self.address.grid(row=2, column=0, sticky="w", pady=(6, 0))
        WrapLabel(self.wifi_box, f"Keep Automatic unless phones can't open the page. Laptop hotspot? Pick "
                                 f"{netutil.HOTSPOT_IP}. If Windows asks to allow network access, click Allow.",
                  size=12).grid(row=3, column=0, sticky="ew", pady=(6, 0))

        self._show_mode()
        self.refresh()

    # ------------------------------------------------------------ status
    def refresh(self) -> None:
        s = self.settings
        online, permanent = s.online, s.permanent_link
        self.connection.set(CONNECTIONS["online" if online else "wifi"])
        self.connection_text.configure(text=CONNECTION_TEXT["wifi" if not online else
                                                            "permanent" if permanent else "online"])
        if online:
            self.wifi_box.grid_remove()
            self.perm_box.grid()
        else:
            self.wifi_box.grid()
            self.perm_box.grid_remove()
        self.perm_summary.configure(
            text=f"In use: https://{s.tunnel_hostname}" if permanent else
            "Optional: the same address every time, so printed posters keep working. Needs your own domain.")
        self.perm_toggle.configure(text="Change" if permanent else "Set up")
        self.perm_steps.configure(text=PERMANENT_STEPS.format(port=s.server_port))

        ips = netutil.lan_ips()
        values = [AUTO] + ips[:3]
        if s.host_override and s.host_override not in values:
            values.append(s.host_override)
        self.address.configure(values=values)
        self.address.set(s.host_override or AUTO)

        if self.server_error:
            self._banner("error", "The guest page isn't running", self.server_error)
        elif online:
            tunnel = self.get_tunnel()
            state = tunnel.state if tunnel else tunnel_mod.STARTING
            if state == tunnel_mod.ONLINE:
                self._banner("ok", "Ready: guests can scan from any network", tunnel.url)
            elif state == tunnel_mod.DOWNLOADING:
                try:
                    percent = int(self._tunnel_detail or 0)
                except ValueError:
                    percent = 0
                self._banner("busy", "Setting up the online link (first time only)",
                             f"Downloading… {percent}%", progress=percent / 100)
            elif state == tunnel_mod.ERROR:
                self._banner("warning", "The online link isn't working right now",
                             self._tunnel_detail or "Reconnecting…", progress="busy")
            else:
                self._banner("busy", "Getting the online link ready…", "This takes a few seconds.", progress="busy")
        elif not ips:
            self._banner("warning", "This laptop isn't on a network",
                         "Connect to Wi-Fi or turn on Mobile Hotspot, then press refresh.")
        else:
            base = netutil.base_url(s.server_port, s.host_override)
            self._banner("ok", "Ready: phones on the same Wi-Fi can scan", base)

    def _banner(self, kind: str, title: str, text: str, progress=None) -> None:
        icon_name, color, tile = BANNER[kind]
        self.banner_icon.configure(image=icon(icon_name, 22, color), fg_color=tile)
        self.banner_title.configure(text=title)
        self.banner_text.configure(text=text)
        if progress is None:
            self.progress.stop()
            self.progress.grid_remove()
            return
        self.progress.grid()
        if progress == "busy":
            if self.progress.cget("mode") != "indeterminate":
                self.progress.configure(mode="indeterminate")
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.progress.set(max(0.0, min(1.0, progress)))

    def set_server_error(self, message: str) -> None:
        self.server_error = message
        self.refresh()

    def set_tunnel(self, state: str, detail: str) -> None:
        self._tunnel_detail = detail
        self.refresh()

    # ------------------------------------------------------------ what guests scan
    def _on_mode(self, label: str) -> None:
        self.settings.qr_mode = next(k for k, v in MODES.items() if v == label)
        self.settings.guest_search = True  # name search is what the shared code opens
        self._save()
        self._show_mode()
        self.on_change()

    def _show_mode(self) -> None:
        mode = self.settings.qr_mode if self.settings.qr_mode in MODES else "shared"
        self.mode.set(MODES[mode])
        self.mode_text.configure(text=MODE_TEXT[mode])
        self.scan_status.grid_remove()
        if mode != "shared":
            self.shared_box.grid_remove()
            return
        self.shared_box.grid()
        self.search_choice.set("On" if self.settings.guest_search else "Off")
        self.search_text.configure(text=(
            "On. Turn it off after the event so nobody can browse names. Personal links keep working."
            if self.settings.guest_search else
            "Off. The shared code no longer finds photos. Personal links keep working."))

    def refresh_mode(self) -> None:
        self._show_mode()

    def _on_search(self, value: str | None = None) -> None:
        self.settings.guest_search = (value or self.search_choice.get()) == "On"
        self._save()
        self._show_mode()
        self.on_change()

    def _save_poster(self) -> None:
        url = self.shared_url()
        if not url:
            self._scan_message("warning", "The online link isn't ready yet. Wait a few seconds and try again.")
            return
        path = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(), title="Save the QR poster", defaultextension=".png",
            initialfile="PhotoBooth QR poster.png", initialdir=os.path.join(os.path.expanduser("~"), "Pictures"),
            filetypes=[("PNG image", "*.png")])
        if not path:
            return
        try:
            make_poster(url, self.settings.event_name).save(path)
        except OSError as exc:
            self._scan_message("error", f"Could not save the poster: {exc}")
            return
        note = (" The online link changes when the app restarts: print it after starting the app on event day."
                if self.settings.online and not self.settings.permanent_link else "")
        self._scan_message("ok", f"Poster saved (A4): {path}.{note}")

    def _scan_message(self, kind: str, text: str) -> None:
        self.scan_status.grid()
        self.scan_status.show(kind, text)

    # ------------------------------------------------------------ how phones connect
    def _on_connection(self, label: str) -> None:
        self.settings.connection = next(k for k, v in CONNECTIONS.items() if v == label)
        self._save()
        self.on_change()  # the app starts or stops the online link

    def _on_address(self, value: str) -> None:
        self.settings.host_override = "" if value == AUTO else value
        self._save()
        self.refresh()
        self.on_change()

    def _toggle_permanent(self) -> None:
        if self.perm_form.winfo_manager():
            self.perm_form.grid_remove()
            return
        self.perm_host.set(self.settings.tunnel_hostname)
        self.perm_token.set(self.settings.tunnel_token)
        self.perm_status.clear()
        if self.settings.permanent_link:
            self.perm_remove.pack(side="left", padx=(10, 0))
        else:
            self.perm_remove.pack_forget()
        self.perm_form.grid()

    def _save_permanent(self) -> None:
        host = tunnel_mod.clean_hostname(self.perm_host.get())
        token = "".join(self.perm_token.get().split())
        if token.lower().startswith("--token"):
            token = token[7:]
        problems = False
        if not tunnel_mod.valid_hostname(host):
            self.perm_host.set_error("Type the full address, e.g. photos.mywedding.com")
            problems = True
        if len(token) < 60:
            self.perm_token.set_error("That looks too short. Copy the whole long text after --token.")
            problems = True
        if problems:
            return
        self.settings.tunnel_hostname, self.settings.tunnel_token = host, token
        self._store_permanent()

    def _remove_permanent(self) -> None:
        self.settings.tunnel_hostname = self.settings.tunnel_token = ""
        self._store_permanent()

    def _store_permanent(self) -> None:
        try:
            config.save(self.settings)
        except OSError as exc:
            self.perm_status.show("error", f"Couldn't save: {exc}")
            return
        self.perm_form.grid_remove()
        self.on_change()  # the app restarts the online link with the new setup

    # ------------------------------------------------------------ helpers
    def _save(self) -> None:
        try:
            config.save(self.settings)
        except OSError:
            pass

    def _open_test_page(self) -> None:
        if not self.shared_url():
            self._banner("busy", "Getting the online link ready…", "Wait a few seconds, then press Test again.",
                         progress="busy")
            return
        if self.settings.qr_mode == "shared":
            webbrowser.open(self.shared_url())
            return
        sessions = self.db.ready_sessions(self.settings.watch_folder) if self.settings.watch_folder else []
        if not sessions:
            self._banner("warning", "No guests are ready yet", "Add photos to the folder first, then press Test.")
            return
        webbrowser.open(self.url_for(sessions[-1]["token"]))
