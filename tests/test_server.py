"""The guest web page, tested over real HTTP like a phone would use it."""
import io
import time
import urllib.error
import urllib.request
import zipfile

import pytest

import branding
import make_test_photos
from config import Settings
from conftest import free_port, wait_until
from server import GuestServer


class Phone:
    def __init__(self, port):
        self.base = f"http://127.0.0.1:{port}"

    def get(self, path, method="GET"):
        request = urllib.request.Request(self.base + path, method=method, data=b"" if method == "POST" else None)
        try:
            with urllib.request.urlopen(request, timeout=10) as r:
                return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
        except urllib.error.HTTPError as e:
            return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


@pytest.fixture
def site(watched):
    photos, db, _watcher = watched
    activity = []
    settings = Settings(watch_folder=str(photos), event_name="Sara & Omar's Wedding")
    server = GuestServer(settings, db, activity.append)
    port = free_port()
    server.start(port)
    wait_until(lambda: server.running)
    tokens = {s["name"]: s["token"] for s in db.sessions_for(str(photos))}
    yield Phone(port), tokens, settings, server, db, activity, photos
    server.stop()


def test_gallery_and_activity(site):
    phone, tokens, _, _, db, activity, _ = site
    status, _, body = phone.get(f"/s/{tokens['Omnya & Fatma']}")
    assert status == 200 and b"Save all 2 photos" in body and b"Sara &amp; Omar" in body
    assert activity and activity[0]["opened_at"]
    phone.get(f"/s/{tokens['Omnya & Fatma']}")
    assert len(activity) == 1  # opening again doesn't report again


def test_previews_and_full_photos(site):
    phone, tokens, *_ = site
    t = tokens["Omnya & Fatma"]
    assert phone.get(f"/t/{t}/1.jpg")[0] == 200
    assert phone.get(f"/t/{t}/2.jpg")[0] == 404
    status, headers, body = phone.get(f"/p/{t}/0")
    assert status == 200 and headers["content-type"] == "image/jpeg" and len(body) > 1000
    assert "content-disposition" not in headers


def test_download_names_and_saved_flag(site):
    phone, tokens, _, _, db, _, _ = site
    status, headers, _ = phone.get(f"/p/{tokens['Omnya & Fatma']}/1?dl=1")
    assert status == 200 and 'filename="Omnya & Fatma - 2.jpg"' in headers["content-disposition"]
    session = db.session_by_token(tokens["Omnya & Fatma"])
    assert session["downloaded_at"] and session["downloads"] == 1
    # Arabic names: proper name for phones, a plain fallback for very old browsers
    headers = phone.get(f"/p/{tokens['محمد علي']}/0?dl=1")[1]
    assert 'filename="photo.jpg"' in headers["content-disposition"]
    assert "filename*=UTF-8''%D9%85" in headers["content-disposition"]


def test_zip(site):
    phone, tokens, *_ = site
    status, headers, body = phone.get(f"/z/{tokens['Omnya & Fatma']}.zip")
    assert status == 200 and headers["content-type"] == "application/zip"
    assert zipfile.ZipFile(io.BytesIO(body)).namelist() == ["Omnya & Fatma - 1.jpg", "Omnya & Fatma - 2.jpg"]


def test_saved_beacon(site):
    phone, tokens, _, _, db, _, _ = site
    assert phone.get(f"/s/{tokens['Hana']}/saved", method="POST")[0] == 204
    assert db.session_by_token(tokens["Hana"])["downloaded_at"]


def test_unknown_links(site):
    phone, *_ = site
    for path in ["/s/nope", "/p/nope/0", "/t/nope/0.jpg", "/z/nope.zip", "/nothing-here"]:
        assert phone.get(path)[0] == 404


def test_search(site):
    phone, *_ = site
    body = phone.get("/?q=omnya")[2]
    assert b"Omnya &amp; Fatma" in body and b"Hana" not in body
    assert b"at least 2 letters" in phone.get("/?q=x")[2]
    assert b"No photos found" in phone.get("/?q=zzz")[2]


def test_search_can_be_turned_off(site):
    phone, tokens, settings, *_ = site
    settings.guest_search = False
    body = phone.get("/?q=hana")[2]
    assert b"closed" in body and tokens["Hana"].encode() not in body
    assert phone.get(f"/s/{tokens['Hana']}")[0] == 200  # personal links keep working


def test_new_photo_shows_up_straight_away(site):
    phone, tokens, _, _, _, _, photos = site
    phone.get(f"/s/{tokens['Hana']}")  # fills the folder memory
    (photos / "Hana_1.jpg").write_bytes((photos / "Hana.jpg").read_bytes())
    assert b"Save all 2 photos" in phone.get(f"/s/{tokens['Hana']}")[2]


def test_ended_event_links_stop_working(site):
    phone, tokens, _, _, db, _, photos = site
    db.close_event(str(photos))
    assert phone.get(f"/s/{tokens['Hana']}")[0] == 404


def test_branding(site):
    phone, tokens, settings, *_ = site
    body = phone.get(f"/s/{tokens['Hana']}")[2]
    assert b"--accent:" not in body and b"logo-img" not in body
    settings.brand_color = "#E11D48"
    settings.brand_message = "Thank you for coming!"
    branding.save_logo(str(next(iter(make_test_photos_dir(site)))))
    body = phone.get(f"/s/{tokens['Hana']}")[2]
    assert b"--accent: #E11D48" in body and b"Thank you for coming!" in body and b"logo-img" in body
    assert phone.get("/brand/logo.png")[0] == 200
    settings.brand_color = "red; } body { display:none"  # anything that isn't a colour is ignored
    assert b"display:none" not in phone.get(f"/s/{tokens['Hana']}")[2]


def make_test_photos_dir(site):
    photos = site[6]
    return sorted(photos.glob("*.jpg"))


def test_healthz(site):
    assert site[0].get("/healthz")[2] == b"ok"
