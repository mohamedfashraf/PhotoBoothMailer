"""Online link: lets phones open the guest page from ANY network (mobile data, other Wi-Fi).

It uses a free Cloudflare "quick tunnel": the small `cloudflared.exe` program connects out from this
laptop to Cloudflare, and Cloudflare gives us a public https address like
https://quiet-river-1234.trycloudflare.com that forwards to the guest page on this laptop.
No account, no router settings. The laptop just needs internet.

- cloudflared.exe is looked for next to the app (or bundled inside it); otherwise it is downloaded
  once from Cloudflare's official GitHub releases into the app's data folder (about 60 MB).
- The address is new every time the app starts, UNLESS a permanent address is set up: with your own
  domain on Cloudflare you create a named tunnel, and the app runs it with its token. The address
  then never changes (good for printed posters).
- If it stops, it is restarted automatically.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Callable

from config import app_dir, data_dir, resource_path

DOWNLOAD_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
EXE_NAME = "cloudflared.exe"
URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

OFF, DOWNLOADING, STARTING, ONLINE, ERROR = "off", "downloading", "starting", "online", "error"


def clean_hostname(text: str) -> str:
    """'https://Photos.MyWedding.com/' -> 'photos.mywedding.com'."""
    text = text.strip().lower()
    for prefix in ("https://", "http://"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text.split("/")[0].strip()


def valid_hostname(text: str) -> bool:
    return bool(re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}", text))


def find_exe() -> Path | None:
    for candidate in (resource_path(EXE_NAME), app_dir() / EXE_NAME, data_dir() / "tools" / EXE_NAME):
        if candidate.is_file() and candidate.stat().st_size > 1_000_000:
            return candidate
    return None


class _KillWithApp:
    """A Windows job object: cloudflared is closed automatically when this app exits (even on a crash)."""

    def __init__(self):
        self.handle = None
        if os.name != "nt":
            return
        try:
            import ctypes
            from ctypes import wintypes

            class LIMIT(ctypes.Structure):
                _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                            ("SchedulingClass", wintypes.DWORD)]

            class IO(ctypes.Structure):
                _fields_ = [(n, ctypes.c_uint64) for n in ("r", "w", "o", "rt", "wt", "ot")]

            class EXTENDED(ctypes.Structure):
                _fields_ = [("Basic", LIMIT), ("Io", IO), ("ProcessMemoryLimit", ctypes.c_size_t),
                            ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                            ("PeakJobMemoryUsed", ctypes.c_size_t)]

            kernel32 = ctypes.windll.kernel32
            kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            handle = kernel32.CreateJobObjectW(None, None)
            info = EXTENDED()
            info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if handle and kernel32.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
                self.handle = handle
        except Exception:
            self.handle = None

    def add(self, process: subprocess.Popen) -> None:
        if not self.handle:
            return
        try:
            import ctypes
            ctypes.windll.kernel32.AssignProcessToJobObject(self.handle, int(process._handle))
        except Exception:
            pass


class Tunnel:
    retry_delay = 5.0  # seconds before reconnecting; doubles while it keeps failing (max 60)

    def __init__(self, port: int, on_change: Callable[[str, str], None], token: str = "", hostname: str = ""):
        """on_change(state, detail) is called from a background thread.

        detail: the public URL when ONLINE, a percentage when DOWNLOADING, a friendly message on ERROR.
        """
        self.port = port
        self.on_change = on_change
        self.token = token.strip()
        self.hostname = clean_hostname(hostname)
        self.permanent = bool(self.token and self.hostname)
        self.state = OFF
        self.url = ""
        self._process: subprocess.Popen | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._job = _KillWithApp()

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="Tunnel", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._kill()
        self._set(OFF, "")

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ------------------------------------------------------------ internals
    def _set(self, state: str, detail: str) -> None:
        self.state = state
        self.url = detail if state == ONLINE else ""
        try:
            self.on_change(state, detail)
        except Exception:
            pass

    def _kill(self) -> None:
        process, self._process = self._process, None
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

    def _run(self) -> None:
        delay = self.retry_delay
        while not self._stop.is_set():
            exe = find_exe() or self._download()
            if exe is None:
                if self._stop.wait(30):  # no internet yet: try again in a while
                    return
                continue
            started = time.time()
            self._run_once(exe)
            if self._stop.is_set():
                return
            # It stopped (internet dropped, laptop slept...). Try again, waiting a bit longer each time.
            delay = self.retry_delay if time.time() - started > 120 else min(delay * 2, 60)
            if self._stop.wait(delay):
                return

    def _download(self) -> Path | None:
        target = data_dir() / "tools" / EXE_NAME
        part = target.with_suffix(".part")
        self._set(DOWNLOADING, "0")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": "PhotoBooth"})
            with urllib.request.urlopen(request, timeout=30) as response, open(part, "wb") as out:
                total = int(response.headers.get("Content-Length") or 0)
                done, last = 0, -1
                while chunk := response.read(256 * 1024):
                    if self._stop.is_set():
                        raise InterruptedError
                    out.write(chunk)
                    done += len(chunk)
                    percent = int(done * 100 / total) if total else 0
                    if percent != last:
                        last = percent
                        self._set(DOWNLOADING, str(percent))
            if done < 1_000_000:
                raise OSError("download incomplete")
            os.replace(part, target)
            return target
        except InterruptedError:
            return None
        except Exception:
            try:
                part.unlink(missing_ok=True)
            except OSError:
                pass
            self._set(ERROR, "Couldn't download the online-link tool. Is this laptop connected to the "
                             "internet? Trying again in 30 seconds.")
            return None

    def _run_once(self, exe: Path) -> None:
        self._set(STARTING, "")
        flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW: no black console window
        env = dict(os.environ)
        if self.permanent:
            # The token goes in an environment variable, so it doesn't show in the process list.
            args = [str(exe), "tunnel", "--no-autoupdate", "run"]
            env["TUNNEL_TOKEN"] = self.token
        else:
            args = [str(exe), "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{self.port}"]
        try:
            self._process = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
                creationflags=flags, text=True, encoding="utf-8", errors="replace")
        except OSError as exc:
            self._set(ERROR, f"Couldn't start the online link: {exc}")
            return
        self._job.add(self._process)

        url = f"https://{self.hostname}" if self.permanent else ""
        connected = False
        announced = False
        bad_token = False
        process = self._process
        for line in process.stdout:  # ends when cloudflared exits
            if self._stop.is_set():
                break
            lowered = line.lower()
            if "token" in lowered and ("invalid" in lowered or "not valid" in lowered or "unauthorized" in lowered):
                bad_token = True
            if not url:
                match = URL_PATTERN.search(line)
                if match:
                    url = match.group(0)
            if "Registered tunnel connection" in line:
                connected = True
            if url and connected and not announced:
                announced = True
                threading.Thread(target=self._announce_when_reachable, args=(url, process),
                                 daemon=True).start()
        if self._stop.is_set():
            return
        if bad_token:
            self._set(ERROR, "Cloudflare didn't accept the tunnel token. Check it under QR screen → "
                             "Permanent address. Trying again…")
        else:
            self._set(ERROR, "The online link stopped (is the internet still on?). Reconnecting…")

    def _announce_when_reachable(self, url: str, process: subprocess.Popen) -> None:
        """Report ONLINE once the new address really answers (Cloudflare needs a few seconds)."""
        time.sleep(3)  # asking too early can make Windows remember "address not found" for a while
        deadline = time.time() + 45
        warned = False
        while not self._stop.is_set() and process.poll() is None:
            try:
                with urllib.request.urlopen(url + "/healthz", timeout=8) as response:
                    if response.status == 200 and response.read() == b"ok":
                        break
            except Exception:
                pass
            if time.time() > deadline:
                if not self.permanent:
                    break  # quick links: assume it works (some networks can't reach their own link)
                if not warned:  # permanent address: connected, but it doesn't lead to this app (yet)
                    warned = True
                    self._set(ERROR, f"Connected to Cloudflare, but {self.hostname} doesn't open this app yet. "
                                     f"In Cloudflare, the tunnel's public hostname must point to "
                                     f"http://localhost:{self.port}. Checking again…")
                time.sleep(8)
            else:
                time.sleep(2)
        if not self._stop.is_set() and process.poll() is None and process is self._process:
            self._set(ONLINE, url)


if __name__ == "__main__":  # quick manual check:  python tunnel.py 8000
    t = Tunnel(int(sys.argv[1]) if len(sys.argv) > 1 else 8000, lambda s, d: print(s, d))
    t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        t.stop()
