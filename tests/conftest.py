"""Shared test setup. Run all tests with:   python -m pytest"""
from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dev"))

import branding  # noqa: E402
import config  # noqa: E402
import make_test_photos  # noqa: E402
from db import Database  # noqa: E402
from watcher import FolderWatcher  # noqa: E402


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    """Every test gets its own empty app-data folder (never touches the real settings or database)."""
    folder = tmp_path / "appdata"
    folder.mkdir()
    monkeypatch.setattr(config, "data_dir", lambda: folder)
    return folder


def make_photos(folder: Path, guests: dict[str, int]) -> Path:
    """Create sample booth photos, e.g. {"Hana": 1, "Omnya & Fatma": 2}."""
    folder.mkdir(parents=True, exist_ok=True)
    for name, count in guests.items():
        make_test_photos.make_guest(folder, name, count)
    return folder


@pytest.fixture
def photos(tmp_path) -> Path:
    return make_photos(tmp_path / "Photos", {"Hana": 1, "Omnya & Fatma": 2, "محمد علي": 1, "Table 5": 1, "Table 6": 1})


@pytest.fixture
def db(tmp_path) -> Database:
    return Database(tmp_path / "test.db")


def wait_until(check, timeout: float = 10.0, step: float = 0.1):
    end = time.time() + timeout
    while time.time() < end:
        result = check()
        if result:
            return result
        time.sleep(step)
    raise AssertionError("timed out waiting")


@pytest.fixture
def watched(photos, db):
    """The photos folder being watched; waits until every guest is ready."""
    watcher = FolderWatcher(str(photos), db, lambda s: None)
    watcher.start()
    wait_until(lambda: len(db.ready_sessions(str(photos))) == 5)
    yield photos, db, watcher
    watcher.stop()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
