"""App settings: stored in settings.json next to the app (or %APPDATA% if that folder is read-only)."""
from __future__ import annotations

import functools
import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

APP_NAME = "PhotoBooth Share"
APP_ID = "PhotoBoothMailer"  # internal id (kept so existing installs keep their data)
APP_VERSION = "1.1.2"  # bump for every release (see CHANGELOG.md and dev/release.py)

# ---------------------------------------------------------------- paths
def app_dir() -> Path:
    """Folder containing the .exe (when packaged) or this source file (in dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_path(relative: str) -> Path:
    """Path to a bundled read-only resource (templates, static files)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


@functools.lru_cache(maxsize=1)
def data_dir() -> Path:
    """Writable folder for settings.json and the database."""
    preferred = app_dir()
    if _is_writable(preferred):
        return preferred
    fallback = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_ID
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def settings_path() -> Path:
    return data_dir() / "settings.json"


def _is_writable(folder: Path) -> bool:
    try:
        probe = folder / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- settings model
CONNECTION_ONLINE = "online"  # phones use a public https link (any network; laptop needs internet)
CONNECTION_WIFI = "wifi"      # phones must be on the same Wi-Fi / hotspot as the laptop


@dataclass
class Settings:
    watch_folder: str = ""
    event_name: str = ""
    connection: str = CONNECTION_ONLINE
    server_port: int = 8000
    host_override: str = ""   # Wi-Fi address put in QR codes; "" = pick automatically
    # Optional permanent online address (needs your own domain on Cloudflare). Empty = free changing link.
    tunnel_hostname: str = ""  # e.g. "photos.mywedding.com"
    tunnel_token: str = ""     # the token Cloudflare shows when you create a tunnel
    qr_mode: str = "shared"   # shared = one QR for everyone (guests search their name) | guest = QR per guest
    guest_search: bool = True  # allow finding photos by typing a name on the shared page
    appearance: str = "system"  # system | light | dark
    brand_color: str = ""      # guest page colour, e.g. "#E11D48" ("" = the app's own colour)
    brand_message: str = ""    # optional line on the guest's photos page, e.g. "Thank you for coming!"
    setup_complete: bool = False

    @property
    def folder_ok(self) -> bool:
        return bool(self.watch_folder) and os.path.isdir(self.watch_folder)

    @property
    def is_ready(self) -> bool:
        return self.folder_ok and bool(self.event_name.strip())

    @property
    def online(self) -> bool:
        return self.connection == CONNECTION_ONLINE

    @property
    def permanent_link(self) -> bool:
        return bool(self.tunnel_hostname and self.tunnel_token)

    # -- serialisation
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "Settings":
        known = {f.name for f in fields(cls)}
        settings = cls(**{k: v for k, v in raw.items() if k in known})  # old keys (e.g. email) are ignored
        settings.server_port = _to_int(settings.server_port, 8000)
        if settings.connection not in (CONNECTION_ONLINE, CONNECTION_WIFI):
            settings.connection = CONNECTION_ONLINE
        return settings


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load() -> Settings:
    path = settings_path()
    if not path.exists():
        return Settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Settings.from_dict(raw)
    except (OSError, ValueError, TypeError):
        # Keep the broken file for inspection and start fresh instead of crashing.
        try:
            path.replace(path.with_name("settings.broken.json"))
        except OSError:
            pass
        return Settings()


def save(settings: Settings) -> None:
    path = settings_path()
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(settings.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)  # atomic: never leaves a half-written settings file
