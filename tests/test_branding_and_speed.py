"""Event colours, Instagram links, update checks, and the folder memory that keeps pages fast."""
import time

import pytest

import branding
import updater
from config import Settings
from conftest import make_photos
from server import GuestServer


def test_colour_css():
    assert branding.css("") == "" and branding.css(branding.DEFAULT_COLOR) == ""
    css = branding.css("#E11D48")
    assert "--accent: #E11D48" in css and "prefers-color-scheme: dark" in css
    assert branding.css("red; } body { x") == ""  # only real #RRGGBB colours are used



@pytest.mark.parametrize("text, url", [
    ("@my.studio", "https://www.instagram.com/my.studio/"),
    ("my_studio", "https://www.instagram.com/my_studio/"),
    ("instagram.com/studio", "https://www.instagram.com/studio/"),
    ("https://www.instagram.com/studio/?hl=en", "https://www.instagram.com/studio/"),
    ("https://instagram.com/p/abc123", ""),  # a post, not an account
    ("bad name", ""),
    ("", ""),
])
def test_instagram_links(text, url):
    assert branding.instagram_url(text) == url


@pytest.mark.parametrize("newest, current, newer", [
    ("1.2.2", "1.2.1", True), ("v1.10.0", "1.9.9", True), ("1.2.1", "1.2.1", False), ("1.0.0", "1.2.1", False),
])
def test_update_version_compare(newest, current, newer):
    assert updater.is_newer(newest, current) is newer


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
