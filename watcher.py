"""Watches the photos folder and turns photos into guests (sessions).

- A guest appears as "collecting" as soon as their first photo lands.
- Once no new photo for that guest has arrived for DEBOUNCE seconds, the guest becomes "ready"
  (their QR code can be shown). This way a half-finished set is never sent.
- Photos added later to a guest are picked up too (the guest page always shows the current files).
- A full re-scan runs every RESCAN seconds as a safety net, because file events can be missed
  on OneDrive, network or USB folders.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

import naming
from db import STATUS_COLLECTING, Database

DEBOUNCE = 5.0
RESCAN = 30.0
TICK = 0.5


class FolderWatcher:
    def __init__(self, folder: str, db: Database, on_guest: Callable[[dict], None],
                 on_status: Callable[[bool], None] | None = None,
                 debounce: float = DEBOUNCE, rescan: float = RESCAN):
        self.folder = os.path.abspath(folder)
        self.db = db
        self.on_guest = on_guest          # called from a background thread with the session dict
        self.on_status = on_status        # called with True/False when the folder is reachable/missing
        self.debounce = debounce
        self.rescan = rescan
        self._pending: dict[str, float] = {}  # guest key -> time of last file event
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._observer: Observer | None = None
        self._thread: threading.Thread | None = None
        self._folder_ok: bool | None = None

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="FolderWatcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception:
                pass

    def _run(self) -> None:
        self._sync(None, settle_all=True)  # photos already there at start are complete sets
        last_rescan = time.monotonic()
        while not self._stop.is_set():
            if self._observer is None and os.path.isdir(self.folder):
                self._start_observer()
            now = time.monotonic()
            with self._lock:
                pending = dict(self._pending)
            if pending:
                due = {k for k, t in pending.items() if now - t >= self.debounce}
                self._sync(set(pending), ready_keys=due)
                with self._lock:
                    for key in due:
                        if self._pending.get(key) == pending[key]:  # no newer event meanwhile
                            self._pending.pop(key, None)
            if now - last_rescan >= self.rescan:
                last_rescan = now
                self._sync(None, settle_all=False)
            self._stop.wait(TICK)

    def _start_observer(self) -> None:
        try:
            observer = Observer()
            observer.schedule(_Handler(self), self.folder, recursive=True)
            observer.start()
            self._observer = observer
        except OSError:
            self._observer = None

    # ------------------------------------------------------------ events
    def note_change(self, path: str) -> None:
        key = self._key_for(path)
        if key:
            with self._lock:
                self._pending[key] = time.monotonic()

    def _key_for(self, path: str) -> str | None:
        try:
            rel = os.path.relpath(path, self.folder)
        except ValueError:
            return None
        parts = Path(rel).parts
        if not parts or parts[0] in (".", ".."):
            return None
        if len(parts) == 1:
            name = parts[0]
            if naming.is_photo(name):
                return naming.guest_key(os.path.splitext(name)[0])
            if os.path.isdir(path):  # a guest subfolder was created/renamed
                return "folder:" + name.casefold()
            return None
        if len(parts) == 2 and naming.is_photo(parts[1]):
            return "folder:" + parts[0].casefold()
        return None

    # ------------------------------------------------------------ syncing files -> database
    def _sync(self, keys: set[str] | None, ready_keys: set[str] = frozenset(), settle_all: bool = False) -> None:
        """Re-read the folder and update the given guests (or all guests when keys is None)."""
        folder_ok = os.path.isdir(self.folder)
        if folder_ok != self._folder_ok:
            self._folder_ok = folder_ok
            if self.on_status:
                self.on_status(folder_ok)
            if not folder_ok and self._observer is not None:  # e.g. USB drive unplugged
                self.stop_observer()
        if not folder_ok:
            return

        guests = naming.scan_folder(self.folder)
        known = {s["guest_key"]: s for s in self.db.sessions_for(self.folder)}
        targets = set(guests) | {k for k, s in known.items() if s["photo_count"]} if keys is None else keys
        with self._lock:
            still_pending = set(self._pending)
        safety_rescan = keys is None and not settle_all

        for key in targets:
            guest = guests.get(key)
            count = len(guest.photos) if guest else 0
            if guest is None and key not in known:
                continue  # e.g. a temp file that was renamed away
            name = guest.name if guest else known[key]["name"]
            session, changed = self.db.upsert_guest(self.folder, key, name, count)
            if safety_rescan and changed:
                # The re-scan found photos no file event told us about: still wait the full debounce.
                with self._lock:
                    self._pending.setdefault(key, time.monotonic())
                should_be_ready = False
            elif keys is None:
                should_be_ready = count > 0 and key not in still_pending
            else:
                should_be_ready = count > 0 and key in ready_keys
            if should_be_ready and session["status"] == STATUS_COLLECTING:
                session = self.db.mark_ready(session["id"])
                changed = True
            if changed:
                self.on_guest(session)

    def stop_observer(self) -> None:
        try:
            self._observer.stop()
        except Exception:
            pass
        self._observer = None


class _Handler(FileSystemEventHandler):
    def __init__(self, watcher: FolderWatcher):
        self.watcher = watcher

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.event_type in ("opened", "closed_no_write"):
            return
        self.watcher.note_change(event.src_path)
        dest = getattr(event, "dest_path", "")
        if dest:
            self.watcher.note_change(dest)
