"""Event colours/logo, and the folder memory that keeps pages fast with many phones."""
import time

from PIL import Image

import branding
from config import Settings
from conftest import make_photos
from server import GuestServer


def test_colour_css():
    assert branding.css("") == "" and branding.css(branding.DEFAULT_COLOR) == ""
    css = branding.css("#E11D48")
    assert "--accent: #E11D48" in css and "prefers-color-scheme: dark" in css
    assert branding.css("red; } body { x") == ""  # only real #RRGGBB colours are used


def test_logo_is_copied_and_shrunk(tmp_path):
    source = tmp_path / "big.png"
    Image.new("RGBA", (2000, 1000), (200, 0, 0, 128)).save(source)
    branding.save_logo(str(source))
    source.unlink()  # the original can move or disappear: the app keeps its own copy
    with Image.open(branding.logo_path()) as logo:
        assert max(logo.size) == branding.LOGO_MAX
    branding.remove_logo()
    assert not branding.has_logo()


def test_folder_is_not_reread_for_every_request(tmp_path, db, monkeypatch):
    folder = make_photos(tmp_path / "P", {"Hana": 1})
    server = GuestServer(Settings(watch_folder=str(folder)), db, lambda s: None)
    calls = []
    import naming
    real = naming.scan_folder
    monkeypatch.setattr(naming, "scan_folder", lambda f: calls.append(1) or real(f))
    for _ in range(50):
        server._scan(str(folder))
    assert len(calls) == 1
    time.sleep(0.05)
    (folder / "Hana_1.jpg").write_bytes((folder / "Hana.jpg").read_bytes())  # folder changes...
    assert len(server._scan(str(folder))["hana"].photos) == 2  # ...and is read again at once
    assert len(calls) == 2
