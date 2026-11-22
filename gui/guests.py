"""Guests screen: a live list of everyone the folder watcher has found."""
from __future__ import annotations

import csv
import os
from datetime import datetime
from tkinter import filedialog, ttk

import customtkinter as ctk

from config import Settings
from db import STATUS_READY, Database
from gui import theme
from gui.icons import icon
from gui.widgets import (Card, StatusLine, WrapLabel, icon_tile, rtl_fix, secondary_button, show_page,
                         shorten_path, title_label)

COLUMNS = [  # id, heading, width, anchor
    ("guest", "GUEST", 260, "w"),
    ("photos", "PHOTOS", 90, "center"),
    ("status", "STATUS", 230, "w"),
    ("time", "ADDED", 90, "center"),
    ("code", "LINK CODE", 140, "w"),
]


def _mode_index() -> int:
    return 0 if ctk.get_appearance_mode() == "Light" else 1


class GuestsView(ctk.CTkFrame):
    def __init__(self, master, settings: Settings, db: Database, on_open=None, on_new_event=None,
                 url_for=None):
        super().__init__(master, fg_color=theme.BG, corner_radius=0)
        self.on_open = on_open  # called with a session id to show that guest's QR code
        self.on_new_event = on_new_event  # opens the "New event" window
        self.url_for = url_for  # token -> guest page address (for the exported list)
        self.settings = settings
        self.db = db
        self.rows: dict[int, dict] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header with live counters
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)
        title_label(header, "Guests").grid(row=0, column=0, sticky="w")
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e")
        secondary_button(actions, "Export list", self._export, icon_name="save", width=116).pack(side="left")
        secondary_button(actions, "New event", self.on_new_event, icon_name="party-popper", width=116).pack(
            side="left", padx=(8, 0))

        # One quiet line of numbers instead of big boxes
        stats = ctk.CTkFrame(header, fg_color="transparent")
        stats.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.guest_chip = self._chip(stats, "users")
        self.photo_chip = self._chip(stats, "images")
        self.sent_chip = self._chip(stats, "circle-check", color=theme.SUCCESS)
        self.export_status = StatusLine(stats, wraplength=900, autowrap=False)
        self.export_status.pack(side="right")
        self.export_status.show("info", "Double-click a guest to show their QR code")

        # Body: the table and an empty state, stacked; we raise whichever applies.
        body = Card(self)
        body.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 8))
        body.body.grid_configure(padx=6, pady=6)
        body.body.grid_rowconfigure(0, weight=1)

        self.table_page = ctk.CTkFrame(body.body, fg_color=theme.CARD, corner_radius=0)
        self.table_page.grid(row=0, column=0, sticky="nsew")
        self.table_page.grid_columnconfigure(0, weight=1)
        self.table_page.grid_rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(self.table_page, columns=[c[0] for c in COLUMNS], show="headings",
                                 style="Guests.Treeview", selectmode="browse")
        for cid, heading, width, anchor in COLUMNS:
            self.tree.heading(cid, text=heading, anchor=anchor)
            self.tree.column(cid, width=width, minwidth=60, anchor=anchor, stretch=cid in ("guest", "status"))
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=4)
        scrollbar = ctk.CTkScrollbar(self.table_page, command=self.tree.yview, button_color=theme.SOFT_HOVER)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=4, pady=4)
        def scrolled(first, last, bar=scrollbar):
            bar.set(first, last)
            if float(first) <= 0.0 and float(last) >= 1.0:  # everything fits: no scrollbar
                bar.grid_remove()
            elif not bar.winfo_manager():
                bar.grid()

        self.tree.configure(yscrollcommand=scrolled)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>", self._on_double_click)

        self.empty_page = ctk.CTkFrame(body.body, fg_color=theme.CARD, corner_radius=0)
        self.empty_page.grid(row=0, column=0, sticky="nsew")
        inner = ctk.CTkFrame(self.empty_page, fg_color="transparent")
        inner.place(relx=0.5, rely=0.46, anchor="center")
        icon_tile(inner, "images", size=72, icon_size=34).pack()
        ctk.CTkLabel(inner, text="No guests yet", font=theme.font(19, "bold"), text_color=theme.TEXT).pack(pady=(16, 4))
        self.empty_message = ctk.CTkLabel(inner, text="", font=theme.font(14), text_color=theme.MUTED,
                                          justify="center", wraplength=440)
        self.empty_message.pack()

        self._style_table()
        ctk.AppearanceModeTracker.add(lambda _mode: self.after(10, self._style_table), self)
        self.reload()

    def _chip(self, master, icon_name: str, color=theme.MUTED) -> ctk.CTkLabel:
        chip = ctk.CTkLabel(master, text="", image=icon(icon_name, 14, color), compound="left",
                            font=theme.font(12), text_color=theme.MUTED, fg_color="transparent", height=20)
        chip.pack(side="left", padx=(0, 16))
        return chip

    def _on_double_click(self, _event=None) -> None:
        selection = self.tree.selection()
        if selection and self.on_open:
            session = self.rows.get(int(selection[0]))
            if session and session["status"] == STATUS_READY:
                self.on_open(session["id"])

    # ------------------------------------------------------------ styling (ttk follows light/dark)
    def _style_table(self) -> None:
        i = _mode_index()
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        style = ttk.Style(self)
        if style.theme_use() != "clam":
            style.theme_use("clam")
        bg, fg = theme.CARD[i], theme.TEXT[i]
        style.layout("Guests.Treeview", [("Guests.Treeview.treearea", {"sticky": "nswe"})])
        style.configure("Guests.Treeview", background=bg, fieldbackground=bg, foreground=fg, borderwidth=0,
                        rowheight=int(34 * scale), font=(theme.FAMILY, 10))
        style.map("Guests.Treeview", background=[("selected", theme.SOFT[i])],
                  foreground=[("selected", theme.TEXT[i])])
        style.configure("Guests.Treeview.Heading", background=bg, foreground=theme.FAINT[i], borderwidth=0,
                        relief="flat", font=(theme.SEMIBOLD, 9), padding=(int(4 * scale), int(8 * scale)))
        style.map("Guests.Treeview.Heading", background=[("active", bg)], relief=[("active", "flat")])
        # Calm table: only rows that mean something get colour.
        self.tree.tag_configure("ready", foreground=fg)
        self.tree.tag_configure("sending", foreground=fg)  # opened, not saved yet: the status text says it
        self.tree.tag_configure("sent", foreground=theme.SUCCESS[i])
        self.tree.tag_configure("collecting", foreground=theme.FAINT[i])
        self.tree.tag_configure("alert", foreground=theme.ERROR[i])

    # ------------------------------------------------------------ data
    def reload(self) -> None:
        """Re-read all guests of the current folder from the database."""
        self.tree.delete(*self.tree.get_children())
        self.rows.clear()
        if self.settings.watch_folder:
            for session in reversed(self.db.sessions_for(self.settings.watch_folder)):
                self.upsert(session, refresh=False)
        self._refresh_summary()

    def upsert(self, session: dict, refresh: bool = True) -> None:
        sid = session["id"]
        self.rows[sid] = session
        iid = str(sid)
        if session["photo_count"] == 0:  # all photos deleted
            if self.tree.exists(iid):
                self.tree.delete(iid)
        else:
            status, tag = self._status(session)
            values = self._values(session, status)
            tags = (tag,)
            if self.tree.exists(iid):
                self.tree.item(iid, values=values, tags=tags)
            else:
                self.tree.insert("", 0, iid=iid, values=values, tags=tags)  # newest on top
                if refresh:
                    self.tree.see(iid)  # live arrival: make sure it's visible
        if refresh:
            self._refresh_summary()

    @staticmethod
    def _status(session: dict) -> tuple[str, str]:
        """(text, colour tag) for the STATUS column."""
        if session["status"] != STATUS_READY:
            return "◌  Getting photos…", "collecting"
        if session.get("photos_after_send"):
            return "⚠  New photos since they saved", "alert"
        if session.get("downloaded_at"):
            return "✓  Photos saved", "sent"
        if session.get("opened_at"):
            return "◉  Opened, not saved yet", "sending"
        return "●  Ready", "ready"

    @staticmethod
    def _values(session: dict, status: str) -> tuple:
        added = datetime.fromtimestamp(session["created_at"]).strftime("%H:%M")
        photos = session["photo_count"]
        return (f"  {rtl_fix(session['name'])}", photos, status, added, session["token"])

    def _refresh_summary(self) -> None:
        visible = [s for s in self.rows.values() if s["photo_count"] > 0]
        sent = sum(1 for s in visible if s.get("downloaded_at"))
        photos = sum(s["photo_count"] for s in visible)
        self.guest_chip.configure(text=f" {len(visible)} guest{'s' if len(visible) != 1 else ''}")
        self.photo_chip.configure(text=f" {photos} photo{'s' if photos != 1 else ''}")
        self.sent_chip.configure(text=f" {sent} saved")
        if visible:
            show_page(self.table_page)
        else:
            folder = shorten_path(self.settings.watch_folder, 48) or "your photos folder"
            self.empty_message.configure(text=f"As soon as the booth saves photos into\n{folder}\n"
                                              "each guest will show up here.")
            show_page(self.empty_page)

    # ------------------------------------------------------------ export
    def _export(self) -> None:
        """Save the guest list as a spreadsheet (CSV; opens in Excel, Arabic names included)."""
        sessions = [s for s in self.db.sessions_for(self.settings.watch_folder) if s["photo_count"] > 0] \
            if self.settings.watch_folder else []
        if not sessions:
            self.export_status.show("info", "No guests to export yet.")
            return
        safe_event = "".join(c for c in (self.settings.event_name or "Guests") if c not in '<>:"/\\|?*').strip()
        path = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(), title="Export the guest list", defaultextension=".csv",
            initialfile=f"{safe_event} - guests.csv", initialdir=os.path.join(os.path.expanduser("~"), "Documents"),
            filetypes=[("Spreadsheet (CSV)", "*.csv")])
        if not path:
            return

        def when(ts):
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:  # -sig: Excel shows Arabic correctly
                writer = csv.writer(f)
                writer.writerow(["Guest", "Photos", "Status", "Added", "Opened page", "Saved photos",
                                 "Times saved", "Link code", "Link"])
                for s in reversed(sessions):  # oldest first, like the booth's order
                    status = self._status(s)[0].split("  ", 1)[-1]
                    link = self.url_for(s["token"]) if self.url_for and s["status"] == STATUS_READY else ""
                    writer.writerow([s["name"], s["photo_count"], status, when(s["created_at"]),
                                     when(s.get("opened_at")), when(s.get("downloaded_at")), s.get("downloads") or 0,
                                     s["token"], link])
        except OSError as exc:
            self.export_status.show("error", f"Couldn't save the list: {exc}")
            return
        self.export_status.show("ok", f"Saved {len(sessions)} guests to {shorten_path(path, 40)}")

    def refresh(self) -> None:
        self.reload()
