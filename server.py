"""The guest web page: guests open it from the QR code and save their photos to their phone.

    GET  /                     find your photos by name (the shared QR code lands here)
    GET  /s/<token>            the guest's photos, with "Save all" and one download button per photo
    GET  /t/<token>/<n>.jpg    small preview of photo n
    GET  /p/<token>/<n>        photo n in full quality (?dl=1 downloads it with a nice file name)
    GET  /z/<token>.zip        all photos in one ZIP (handy on computers)
    POST /s/<token>/saved      the phone reports "saved" (after the iPhone share sheet)
    GET  /healthz              "ok" (used to check the online link works)

File names and folders on the laptop are never shown; photos are only reachable with the guest's
secret token. Unknown or wrong links get a friendly "ask the booth staff" page.
"""
from __future__ import annotations

import io
import os
import tempfile
import threading
import time
import zipfile
from collections import OrderedDict
from typing import Callable
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageOps

import naming
from config import Settings, resource_path
from db import STATUS_READY, Database

THUMB_WIDTH = 520
MAX_PHOTOS = 60
MAX_SEARCH_RESULTS = 8
MIN_SEARCH_LETTERS = 2
SCAN_CACHE_SECONDS = 3.0  # how long a read of the photos folder is reused
MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def download_name(guest_name: str, index: int, count: int, ext: str) -> str:
    """'Omnya & Fatma - 2.jpg' (no characters phones or Windows dislike)."""
    safe = "".join(c for c in guest_name if c not in '<>:"/\\|?*').strip() or "Photo"
    return f"{safe}{f' - {index + 1}' if count > 1 else ''}{ext.lower()}"


def attachment_header(filename: str) -> str:
    ascii_name = filename.encode("ascii", "ignore").decode().strip()
    stem, ext = os.path.splitext(ascii_name)
    if not any(ch.isalpha() for ch in stem):  # e.g. an Arabic name: old browsers get "photo - 1.jpg"
        ascii_name = "photo " + stem.strip() + ext if stem.strip() else "photo" + ext
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'


class GuestServer:
    def __init__(self, settings: Settings, db: Database, on_activity: Callable[[dict], None]):
        self.settings = settings
        self.db = db
        self.on_activity = on_activity  # (session) -> None, called from a server thread
        self._thumbs: OrderedDict[tuple, bytes] = OrderedDict()
        self._thumb_lock = threading.Lock()
        self._scans: dict[str, tuple] = {}  # folder -> (read at, folder modified time, guests)
        self._scan_lock = threading.Lock()
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self.app = self._build_app()

    # ------------------------------------------------------------ lifecycle
    def start(self, port: int) -> None:
        config = uvicorn.Config(self.app, host="0.0.0.0", port=port, log_level="warning",
                                access_log=False, log_config=None)
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, name="GuestServer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=3)

    @property
    def running(self) -> bool:
        return bool(self._server and self._server.started)

    # ------------------------------------------------------------ helpers
    def _scan(self, folder: str) -> dict:
        """The folder's guests, re-read at most every couple of seconds.

        One phone opening a page asks for the page plus every preview; many phones at once would
        otherwise re-read a folder of thousands of photos dozens of times a second. Reading again
        right away when the folder itself changed means a new photo shows up immediately.
        """
        try:
            changed = os.stat(folder).st_mtime_ns
        except OSError:
            changed = None
        now = time.monotonic()
        with self._scan_lock:
            cached = self._scans.get(folder)
            if cached and cached[1] == changed and now - cached[0] < SCAN_CACHE_SECONDS:
                return cached[2]
            guests = naming.scan_folder(folder)
            self._scans[folder] = (now, changed, guests)
            return guests

    def _photos(self, session: dict) -> list[str]:
        guest = self._scan(session["folder"]).get(session["guest_key"])
        return [str(p) for p in guest.photos][:MAX_PHOTOS] if guest else []

    def _thumbnail(self, path: str) -> bytes:
        key = (path, os.path.getmtime(path))
        with self._thumb_lock:
            if key in self._thumbs:
                self._thumbs.move_to_end(key)
                return self._thumbs[key]
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
            img.thumbnail((THUMB_WIDTH, THUMB_WIDTH * 2))
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=80, optimize=True)
        data = buf.getvalue()
        with self._thumb_lock:
            self._thumbs[key] = data
            while len(self._thumbs) > 300:
                self._thumbs.popitem(last=False)
        return data

    def _search(self, query: str) -> list[dict]:
        folder = self.settings.watch_folder
        if not folder:
            return []
        scored = []
        for session in self.db.ready_sessions(folder):
            score = naming.match_score(query, session["name"])
            if score:
                scored.append((score, session["ready_at"] or 0, session))
        if any(score >= 2 for score, _, _ in scored):  # good matches exist: drop loose "appears inside" ones
            scored = [item for item in scored if item[0] >= 2]
        scored.sort(key=lambda item: (-item[0], -item[1]))  # best match first, then most recent
        return [{"token": s["token"], "name": s["name"], "photo_count": s["photo_count"]}
                for _, _, s in scored[:MAX_SEARCH_RESULTS]]

    def _opened(self, session: dict) -> None:
        if session.get("opened_at") is None:
            self.on_activity(self.db.mark_opened(session["id"]))

    def _downloaded(self, session: dict) -> None:
        self.on_activity(self.db.mark_downloaded(session["id"]))

    # ------------------------------------------------------------ web app
    def _build_app(self) -> FastAPI:
        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        app.mount("/static", StaticFiles(directory=str(resource_path("static"))), name="static")
        templates = Jinja2Templates(directory=str(resource_path("templates")))
        no_store = {"Cache-Control": "no-store"}

        def page(request: Request, template: str, status: int = 200, **ctx) -> HTMLResponse:
            ctx.setdefault("event_name", self.settings.event_name or "Photo booth")
            return templates.TemplateResponse(request, template, ctx, status_code=status, headers=no_store)

        def find(token: str) -> dict | None:
            session = self.db.session_by_token(token)
            if session and session["status"] == STATUS_READY and session["photo_count"] > 0:
                return session
            return None

        def photo_at(token: str, index: int) -> tuple[dict, str, list[str]] | None:
            session = find(token)
            photos = self._photos(session) if session else []
            if not 0 <= index < len(photos) or not os.path.isfile(photos[index]):
                return None
            return session, photos[index], photos

        @app.get("/healthz", response_class=PlainTextResponse)
        def healthz():
            return PlainTextResponse("ok", headers=no_store)

        @app.get("/", response_class=HTMLResponse)
        def home(request: Request, q: str = ""):
            """The shared QR code lands here: guests type their name to find their photos."""
            if not self.settings.guest_search:
                return page(request, "invalid.html", reason="home")
            q = q.strip()[:60]
            results, too_short = [], False
            if q:
                if len(naming.search_key(q).replace(" ", "")) < MIN_SEARCH_LETTERS:
                    too_short = True
                else:
                    results = self._search(q)
            return page(request, "search.html", q=q, results=results, searched=bool(q) and not too_short,
                        too_short=too_short)

        @app.get("/s/{token}", response_class=HTMLResponse)
        def gallery(request: Request, token: str):
            session = find(token)
            if not session:
                return page(request, "invalid.html", status=404)
            photos = self._photos(session)
            if not photos:
                return page(request, "invalid.html", status=404)
            self._opened(session)
            count = len(photos)
            items = [{"index": i, "name": download_name(session["name"], i, count, os.path.splitext(p)[1])}
                     for i, p in enumerate(photos)]
            return page(request, "gallery.html", token=token, name=session["name"], photos=items, count=count,
                        stamp=int(session["updated_at"]))

        @app.post("/s/{token}/saved")
        def saved(token: str):
            session = find(token)
            if session:
                self._downloaded(session)
            return Response(status_code=204)

        @app.get("/t/{token}/{index}.jpg")
        def thumb(token: str, index: int):
            found = photo_at(token, index)
            if not found:
                return Response(status_code=404)
            try:
                data = self._thumbnail(found[1])
            except OSError:
                return Response(status_code=404)
            return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})

        @app.get("/p/{token}/{index}")
        def photo(token: str, index: int, dl: int = 0):
            found = photo_at(token, index)
            if not found:
                return Response(status_code=404)
            session, path, photos = found
            ext = os.path.splitext(path)[1].lower()
            headers = {"Cache-Control": "private, max-age=300"}
            if dl:
                headers["Content-Disposition"] = attachment_header(
                    download_name(session["name"], index, len(photos), ext))
                self._downloaded(session)
            return FileResponse(path, media_type=MEDIA_TYPES.get(ext, "application/octet-stream"), headers=headers)

        @app.get("/z/{token}.zip")
        def zip_all(token: str):
            session = find(token)
            photos = self._photos(session) if session else []
            if not photos:
                return Response(status_code=404)
            buf = tempfile.SpooledTemporaryFile(max_size=32 * 1024 * 1024)
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as archive:  # photos are already compressed
                for i, path in enumerate(photos):
                    try:
                        archive.write(path, download_name(session["name"], i, len(photos), os.path.splitext(path)[1]))
                    except OSError:
                        continue
            size = buf.tell()
            buf.seek(0)
            self._downloaded(session)

            def chunks():
                try:
                    while data := buf.read(256 * 1024):
                        yield data
                finally:
                    buf.close()

            name = download_name(session["name"], 0, 1, "") + " photos.zip"
            return StreamingResponse(chunks(), media_type="application/zip",
                                     headers={"Content-Disposition": attachment_header(name),
                                              "Content-Length": str(size)})

        @app.exception_handler(404)
        async def not_found(request: Request, _exc):
            return page(request, "invalid.html", status=404)

        return app
