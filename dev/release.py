"""Publish a new version: git tag + GitHub Release with the .exe attached.

Before running it:
  1. Change APP_VERSION in config.py (e.g. 1.0.0 -> 1.1.0).
  2. Add a "## 1.1.0 (date)" section at the top of CHANGELOG.md.
  3. Run build.bat (it saves releases\\PhotoBoothShare-1.1.0.exe).
  4. Commit everything.

Then:   python dev/release.py

It uses the GitHub login Git already has saved on this PC (nothing is printed or stored).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402


def git(*args: str, input_text: str | None = None) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, input=input_text, capture_output=True, text=True,
                          check=True).stdout.strip()


def fail(message: str) -> None:
    print(f"\nStopped: {message}")
    sys.exit(1)


def changelog_notes(version: str) -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(rf"^## {re.escape(version)}\b.*?$(.*?)(?=^## |\Z)", text, re.S | re.M)
    return match.group(1).strip() if match else ""


def api(token: str, method: str, url: str, data: bytes | None = None, content_type: str = "application/json"):
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "Content-Type": content_type, "User-Agent": "PhotoBoothShare-release"})
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read() or b"{}")


def main() -> None:
    version = config.APP_VERSION
    tag = f"v{version}"
    exe = ROOT / "releases" / f"PhotoBoothShare-{version}.exe"
    print(f"Releasing PhotoBooth Share {version}")

    if git("status", "--porcelain"):
        fail("there are uncommitted changes. Commit them first.")
    if tag in git("tag", "--list", tag).split():
        fail(f"version {version} was already released. Change APP_VERSION in config.py first.")
    notes = changelog_notes(version)
    if not notes:
        fail(f'CHANGELOG.md has no "## {version}" section. Add one first.')
    if not exe.is_file():
        fail(f"{exe.relative_to(ROOT)} doesn't exist. Run build.bat first.")

    remote = git("remote", "get-url", "origin")
    match = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", remote)
    if not match:
        fail(f"the 'origin' remote isn't a GitHub repository ({remote}).")
    owner, repo = match.groups()

    credential = git("credential", "fill", input_text="protocol=https\nhost=github.com\n\n")
    token = next((line[9:] for line in credential.splitlines() if line.startswith("password=")), "")
    if not token:
        fail("no saved GitHub login found. Push once with Git so it's saved, then try again.")

    print(f"  tagging {tag} and pushing...")
    git("tag", "-a", tag, "-m", f"PhotoBooth Share {version}")
    git("push", "origin", "HEAD", tag)

    print("  creating the GitHub Release...")
    release = api(token, "POST", f"https://api.github.com/repos/{owner}/{repo}/releases", json.dumps({
        "tag_name": tag, "name": f"PhotoBooth Share {version}", "body": notes}).encode())

    print(f"  uploading {exe.name} ({exe.stat().st_size / 1e6:.0f} MB)...")
    upload = release["upload_url"].split("{")[0] + "?name=" + quote(exe.name)
    api(token, "POST", upload, exe.read_bytes(), content_type="application/octet-stream")

    print(f"\nDone: {release['html_url']}")


if __name__ == "__main__":
    main()
