"""Guests, link codes and what guests did, in the database."""
from db import STATUS_READY


def test_new_guest_gets_secret_code(db):
    session, created = db.upsert_guest("C:/Photos", "hana", "Hana", 1)
    assert created and len(session["token"]) >= 10
    again, changed = db.upsert_guest("C:/Photos", "hana", "Hana", 1)
    assert again["token"] == session["token"] and not changed


def test_opened_and_downloaded(db):
    session, _ = db.upsert_guest("C:/Photos", "hana", "Hana", 1)
    db.mark_ready(session["id"])
    opened = db.mark_opened(session["id"])
    assert opened["opened_at"] and not opened["downloaded_at"]
    saved = db.mark_downloaded(session["id"])
    assert saved["downloaded_at"] and saved["downloads"] == 1


def test_new_photos_after_saving_are_flagged(db):
    session, _ = db.upsert_guest("C:/Photos", "hana", "Hana", 1)
    db.mark_downloaded(session["id"])
    grown, _ = db.upsert_guest("C:/Photos", "hana", "Hana", 2)
    assert grown["photos_after_send"] == 1
    assert db.mark_downloaded(session["id"])["photos_after_send"] == 0


def test_new_event_gives_returning_names_new_codes(db):
    """Same folder, next event: last event's "Hana" link must not open the new Hana's photos."""
    old, _ = db.upsert_guest("C:/Photos", "hana", "Hana", 1)
    db.mark_ready(old["id"])
    assert db.close_event("C:/Photos") == 1
    assert db.sessions_for("C:/Photos") == []
    new, created = db.upsert_guest("C:/Photos", "hana", "Hana", 1)
    assert created and new["token"] != old["token"]
    # the old code still exists in the database but points at the ended event
    ended = db.session_by_token(old["token"])
    assert ended["folder"] != new["folder"] and ended["status"] == STATUS_READY
