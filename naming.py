"""How photos are grouped into guests, and how guest names are shown.

The booth saves every photo into ONE folder, named after the guest:

    Hana.jpg
    Omnya & Fatma.jpg
    Omnya & Fatma_1.jpg      <- second photo of the same guest(s)
    Laila Shoura.jpg

Photos whose names only differ by a trailing number (_1, -2, " 3", " (4)") belong to the same
guest. Grouping ignores upper/lower case and extra spaces.

Per-guest subfolders (Photos/Hana/1.jpg …) are also supported: each subfolder is one guest.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

# "_1", "-12", " 3", " (4)" at the end of a file name
# Only "_1", "-2" and " (3)" mean "another photo of the same guest". A plain space + number is part of
# the name ("Table 5", "Ahmed 2"), so "Table 5" and "Table 6" stay two different guests.
_TRAILING_NUMBER = re.compile(r"(?:\s*[_\-]\s*\d{1,4}|\s*\(\d{1,4}\))$")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")  # Arabic/Persian digits -> 0-9
# Unrenamed camera files (IMG_0042.jpg) are NOT guest names: never merge them into one "IMG" guest.
_CAMERA_PREFIXES = {"img", "dsc", "dscn", "dscf", "pxl", "photo", "image", "picture", "pic", "mvimg", "_mg"}


def is_photo(name: str) -> bool:
    """True for real photo files; skips hidden/temporary files the booth may write first."""
    if name.startswith((".", "~", "$")):
        return False
    return os.path.splitext(name)[1].lower() in IMAGE_EXTS


def base_name(stem: str) -> str:
    """'Omnya & Fatma_1' -> 'Omnya & Fatma'. Never returns an empty string."""
    original = name = " ".join(stem.split())
    shorter = _TRAILING_NUMBER.sub("", name).strip()  # one ending only: "Room 101_1" -> "Room 101"
    if shorter:
        name = shorter
    if name.casefold() in _CAMERA_PREFIXES:
        return original
    return name


def guest_key(stem: str) -> str:
    """Grouping key: same key = same guest."""
    return " ".join(base_name(stem).replace("_", " ").split()).casefold()


def display_name(name: str) -> str:
    """'mohammed' -> 'Mohammed', 'Yousef & sadoon' -> 'Yousef & Sadoon', 'mohamed_ashraf_001' -> 'Mohamed Ashraf'.

    Words someone already capitalised on purpose (e.g. 'McDonald') are left alone; Arabic is unchanged.
    """
    words = base_name(name).replace("_", " ").split()
    return " ".join(w[:1].upper() + w[1:] if w.islower() else w for w in words)


@dataclass
class Guest:
    key: str
    name: str                      # display name, e.g. "Omnya & Fatma"
    photos: list[Path] = field(default_factory=list)
    from_subfolder: bool = False


def scan_folder(folder: str | Path) -> dict[str, Guest]:
    """Group every photo in `folder` (and its direct subfolders) into guests."""
    guests: dict[str, Guest] = {}
    try:
        entries = sorted(os.scandir(folder), key=lambda e: e.name.casefold())
    except OSError:
        return guests

    for entry in entries:
        if entry.is_file() and is_photo(entry.name):
            stem = os.path.splitext(entry.name)[0]
            key = guest_key(stem)
            guest = guests.setdefault(key, Guest(key=key, name=display_name(stem)))
            guest.photos.append(Path(entry.path))
        elif entry.is_dir() and not entry.name.startswith((".", "~", "$")):
            try:
                photos = sorted((Path(e.path) for e in os.scandir(entry.path) if e.is_file() and is_photo(e.name)),
                                key=lambda p: p.name.casefold())
            except OSError:
                continue
            if photos:
                key = "folder:" + entry.name.casefold()
                guests[key] = Guest(key=key, name=display_name(entry.name), photos=photos, from_subfolder=True)
    return guests


# ---------------------------------------------------------------- name search (shared QR code)
_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640]")  # harakat + tatweel
_ARABIC_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})


def search_key(text: str) -> str:
    """Lower-case, spelling-tolerant form used to compare names ('Ahmed', 'AHMED', 'أحمد' vs 'احمد')."""
    text = _ARABIC_DIACRITICS.sub("", text).translate(_ARABIC_LETTERS).translate(_DIGITS).casefold()
    text = re.sub(r"[_\-&.,+]", " ", text)
    return " ".join(text.split())


def match_score(query: str, name: str) -> int:
    """0 = no match. Higher = better: exact name > every word starts a name word > appears anywhere."""
    q, n = search_key(query), search_key(name)
    if not q:
        return 0
    if q == n:
        return 3
    words = n.split()
    if all(any(w.startswith(part) for w in words) for part in q.split()):
        return 2
    if q in n:
        return 1
    # Small spelling differences / typos: "mohamed" ~ "mohammed", "yousef" ~ "youssef".
    # (Never for numbers: table 56 must not find table 57.)
    if not any(ch.isdigit() for ch in q) and all(any(_similar(part, w) for w in words) for part in q.split()):
        return 1
    return 0


def _similar(a: str, b: str) -> bool:
    if len(a) < 4 or len(b) < 4:
        return False
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio() >= 0.8
