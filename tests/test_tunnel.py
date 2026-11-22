"""The online link, with a stand-in for cloudflared.exe (no internet needed)."""
import time
from pathlib import Path

import pytest

import tunnel

REAL_SLEEP = time.sleep
QUICK_LINES = ["INF Requesting new quick Tunnel on trycloudflare.com...\n",
               "INF |  https://quiet-river-1234.trycloudflare.com  |\n",
               "INF Registered tunnel connection connIndex=0\n"]


class FakeCloudflared:
    """Prints what the real one prints, then keeps running until stopped (or `stop_after` seconds)."""
    script: dict = {}

    def __init__(self, args, **kwargs):
        self.args = args
        self.token = kwargs.get("env", {}).get("TUNNEL_TOKEN")
        self.alive = True
        self.stdout = self._lines()
        self._handle = 0
        FakeCloudflared.script.setdefault("runs", []).append(self)

    def _lines(self):
        yield from FakeCloudflared.script.get("lines", [])
        end = time.monotonic() + FakeCloudflared.script.get("stop_after", 60)
        while self.alive and time.monotonic() < end:
            REAL_SLEEP(0.05)
        self.alive = False

    def poll(self):
        return None if self.alive else 0

    def terminate(self):
        self.alive = False

    kill = terminate

    def wait(self, timeout=None):
        return 0


class Reply:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def read(self):
        return b"ok"


@pytest.fixture
def fake(monkeypatch):
    FakeCloudflared.script = {"lines": QUICK_LINES, "reachable": True}

    def urlopen(url, timeout=0):
        if not FakeCloudflared.script.get("reachable"):
            raise OSError("not reachable")
        return Reply()

    monkeypatch.setattr(tunnel.subprocess, "Popen", FakeCloudflared)
    monkeypatch.setattr(tunnel, "find_exe", lambda: Path("cloudflared.exe"))
    monkeypatch.setattr(tunnel.urllib.request, "urlopen", urlopen)
    # time inside tunnel.py runs 20x faster, so waits of seconds take a moment
    monkeypatch.setattr(tunnel, "time", type("FastTime", (), {
        "time": staticmethod(lambda: time.time() * 20),
        "sleep": staticmethod(lambda s: REAL_SLEEP(min(s, 0.05)))}))
    return FakeCloudflared.script


def run(tun, states, seconds):
    end = time.time() + seconds
    while time.time() < end and tun.state not in states:
        REAL_SLEEP(0.05)
    return tun.state


def test_quick_link(fake):
    events = []
    tun = tunnel.Tunnel(8000, lambda s, d: events.append(s))
    tun.start()
    assert run(tun, {tunnel.ONLINE}, 5) == tunnel.ONLINE
    assert tun.url == "https://quiet-river-1234.trycloudflare.com"
    assert "--url" in fake["runs"][0].args and fake["runs"][0].token is None
    tun.stop()
    assert tun.state == tunnel.OFF and not fake["runs"][0].alive


def test_reconnects_after_a_drop(fake):
    fake["stop_after"] = 0.5
    tun = tunnel.Tunnel(8000, lambda s, d: None)
    tun.retry_delay = 0.1
    tun.start()
    wait = time.time() + 8
    while time.time() < wait and len(fake["runs"]) < 2:
        REAL_SLEEP(0.05)
    tun.stop()
    assert len(fake["runs"]) >= 2


def test_permanent_address(fake):
    fake["lines"] = ["INF Registered tunnel connection connIndex=0\n"]
    fake["reachable"] = False
    messages = []
    tun = tunnel.Tunnel(8000, lambda s, d: messages.append((s, d)), token="t" * 80,
                        hostname="https://Photos.Example.com/")
    tun.start()
    assert run(tun, {tunnel.ERROR}, 5) == tunnel.ERROR  # connected, but the address isn't routed to the app
    assert "doesn't open this app" in messages[-1][1]
    fake["reachable"] = True
    assert run(tun, {tunnel.ONLINE}, 5) == tunnel.ONLINE
    assert tun.url == "https://photos.example.com"
    run_ = fake["runs"][0]
    assert run_.args[-1] == "run" and run_.token == "t" * 80  # token via environment, not the command line
    assert "t" * 80 not in " ".join(run_.args)
    tun.stop()


def test_bad_token(fake):
    fake["lines"] = ["ERR Provided Tunnel token is not valid.\n"]
    fake["stop_after"] = 0
    messages = []
    tun = tunnel.Tunnel(8000, lambda s, d: messages.append((s, d)), token="x" * 80, hostname="photos.example.com")
    tun.start()
    run(tun, {tunnel.ERROR}, 5)
    tun.stop()
    assert any("didn't accept the tunnel token" in d for s, d in messages if s == tunnel.ERROR)


@pytest.mark.parametrize("text, host, ok", [
    ("https://Photos.MyWedding.com/", "photos.mywedding.com", True),
    ("photos.mywedding.com", "photos.mywedding.com", True),
    ("localhost", "localhost", False),
    ("my wedding.com", "my wedding.com", False),
])
def test_hostname_check(text, host, ok):
    assert tunnel.clean_hostname(text) == host
    assert tunnel.valid_hostname(host) is ok
