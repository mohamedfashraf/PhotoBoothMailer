"""Create a fake photo booth folder so you can test without a camera.

Matches how the booth saves photos: ONE folder, each photo named after the guest, and a
"_1", "_2" … ending for extra photos of the same guest:

    test_photos/Hana.jpg
    test_photos/Omnya & Fatma.jpg
    test_photos/Omnya & Fatma_1.jpg

    python dev/make_test_photos.py            -> fills  test_photos/  with sample guests
    python dev/make_test_photos.py --live     -> also adds a new guest every 20 s, photo by photo,
                                                 like a real booth (press Ctrl+C to stop)
    python dev/make_test_photos.py --out "D:\\Booth\\Photos"   -> use another folder
    python dev/make_test_photos.py --clean    -> empty test_photos/ first
"""
from __future__ import annotations

import argparse
import random
import shutil
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "test_photos"
SIZE = (1200, 1800)  # portrait, like a typical booth print

# Guest name (as typed at the booth) -> number of photos.
GUESTS: list[tuple[str, int]] = [
    ("Hana", 1),
    ("Laila Shoura", 1),
    ("mohammed", 1),                 # lowercase, as typed by the guest
    ("Fatma", 1),
    ("Omnya & Fatma", 2),            # -> Omnya & Fatma.jpg + Omnya & Fatma_1.jpg
    ("Habiba & Hana", 1),
    ("Yousef & sadoon", 2),
    ("Anas & Khaled", 3),
    ("محمد علي", 2),                 # Arabic name: checks that non-English file names work
]
LIVE_NAMES = ["Nour Adel", "karim", "Hana & Salma", "Ali Tarek", "Mariam", "Ziad & Omar",
              "salma wael", "Ahmed Nabil", "Farida", "Hassan & Mona"]

PALETTES = [
    ((99, 102, 241), (236, 72, 153)), ((14, 165, 233), (34, 197, 94)), ((249, 115, 22), (234, 179, 8)),
    ((168, 85, 247), (59, 130, 246)), ((244, 63, 94), (251, 146, 60)), ((20, 184, 166), (99, 102, 241)),
]


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for name in (("segoeuib.ttf", "arialbd.ttf") if bold else ("segoeui.ttf", "arial.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_photo(path: Path, guest: str, index: int, total: int, seed: int) -> None:
    rng = random.Random(seed)
    a, b = rng.choice(PALETTES)
    w, h = SIZE
    img = Image.new("RGB", SIZE)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        draw.line([(0, y), (w, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))

    # Soft "bokeh" lights
    bokeh = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    bd = ImageDraw.Draw(bokeh)
    for _ in range(26):
        r = rng.randint(40, 170)
        x, y = rng.randint(-50, w + 50), rng.randint(-50, h + 50)
        bd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, rng.randint(18, 60)))
    img = Image.alpha_composite(img.convert("RGBA"), bokeh.filter(ImageFilter.GaussianBlur(14))).convert("RGB")
    draw = ImageDraw.Draw(img)

    # A simple "person" silhouette so it reads as a photo at a glance
    cx, cy = w // 2, int(h * 0.47)
    draw.ellipse([cx - 170, cy - 420, cx + 170, cy - 80], fill=(255, 255, 255))
    draw.rounded_rectangle([cx - 330, cy - 40, cx + 330, cy + 520], radius=260, fill=(255, 255, 255))

    # Booth-style caption strip
    draw.rectangle([0, h - 300, w, h], fill=(255, 255, 255))
    name = guest if guest.isascii() else "Guest"  # Pillow can't shape Arabic without extra libraries
    draw.text((w // 2, h - 205), name, font=_font(82, bold=True), fill=(21, 22, 28), anchor="mm")
    draw.text((w // 2, h - 105), f"PhotoBooth test  ·  photo {index} of {total}", font=_font(46),
              fill=(104, 108, 126), anchor="mm")
    img.save(path, "JPEG", quality=88, optimize=True)


def file_names(guest: str, count: int) -> list[str]:
    """'Omnya & Fatma', 2 -> ['Omnya & Fatma.jpg', 'Omnya & Fatma_1.jpg']"""
    return [f"{guest}.jpg" if i == 0 else f"{guest}_{i}.jpg" for i in range(count)]


def make_guest(out: Path, guest: str, count: int, delay: float = 0.0) -> list[str]:
    names = file_names(guest, count)
    for i, name in enumerate(names, start=1):
        # Write to a temp name first, then rename: like many booth apps do.
        temp = out / f"~{name}.tmp"
        make_photo(temp, guest, i, count, seed=random.randint(0, 0xFFFF))
        temp.replace(out / name)
        if delay:
            time.sleep(delay)
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="folder to fill (default: test_photos)")
    parser.add_argument("--live", action="store_true", help="keep adding new guests like a real booth")
    parser.add_argument("--every", type=float, default=20, help="seconds between live guests (default 20)")
    parser.add_argument("--clean", action="store_true", help="empty the default test_photos folder first")
    args = parser.parse_args()
    out: Path = args.out

    if args.clean and out.exists():
        if out.resolve() != DEFAULT_OUT.resolve():
            raise SystemExit("--clean only empties the default test_photos folder, to be safe.")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    for guest, count in GUESTS:
        names = make_guest(out, guest, count)
        print(f"  ✓ {guest:18} {', '.join(names)}")
    # Files the app must ignore
    (out / "notes.txt").write_text("not a photo", encoding="utf-8")
    (out / "Thumbs.db").write_bytes(bytes(64))
    print(f"\nTest photos are in: {out}")

    if args.live:
        print(f"\nLive mode: a new guest every {args.every:.0f} s. Press Ctrl+C to stop.")
        n = len(GUESTS) + 1
        try:
            while True:
                time.sleep(args.every)
                name = LIVE_NAMES[(n - 1) % len(LIVE_NAMES)]
                if n > len(GUESTS) + len(LIVE_NAMES):
                    name = f"{name} {n}"  # keep names unique when the list repeats
                count = random.randint(1, 3)
                names = make_guest(out, name, count, delay=2)
                print(f"  + {name:18} {', '.join(names)}")
                n += 1
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
