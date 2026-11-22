"""'Check for updates': asks GitHub for the newest release of the app."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from config import APP_VERSION, GITHUB_REPO


class UpdateCheckError(Exception):
    """Friendly message for the user."""


def version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", text)[:3]) or (0,)


def latest_release(timeout: float = 10) -> tuple[str, str]:
    """(newest version, its download page). Raises UpdateCheckError."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "PhotoBoothShare"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateCheckError("No published versions were found to compare with.") from exc
        raise UpdateCheckError(f"GitHub didn't answer properly (error {exc.code}). Try again later.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateCheckError("Couldn't reach GitHub. Is this laptop connected to the internet?") from exc
    version = (data.get("tag_name") or "").lstrip("vV")
    if not version:
        raise UpdateCheckError("The newest version on GitHub has no version number.")
    return version, data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest"


def is_newer(version: str, than: str = APP_VERSION) -> bool:
    return version_tuple(version) > version_tuple(than)
