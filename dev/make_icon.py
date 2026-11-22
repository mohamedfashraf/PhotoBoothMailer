"""Generate the app icon: a white Lucide camera on a black rounded square.

Writes assets/app.ico (window/taskbar/exe), assets/app.png and static/icon.png (guest page icon).

    python dev/make_icon.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "assets" / "fonts" / "lucide.ttf"
OUT = ROOT / "assets" / "app.ico"
CAMERA = chr(0xE064)


def render(size: int = 1024) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    # Near-black vertical gradient (zinc 700 -> zinc 950) inside a rounded square.
    top, bottom = (63, 63, 70), (9, 9, 11)
    gradient = Image.new("RGBA", (size, size))
    draw = ImageDraw.Draw(gradient)
    for y in range(size):
        t = y / (size - 1)
        draw.line([(0, y), (size, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.23), fill=255)
    img.paste(gradient, (0, 0), mask)

    font = ImageFont.truetype(str(FONT), int(size * 0.66))
    left, t, right, b = font.getbbox(CAMERA)
    x = (size - (right - left)) / 2 - left
    y = (size - (b - t)) / 2 - t
    ImageDraw.Draw(img).text((x, y), CAMERA, font=font, fill=(255, 255, 255, 255))
    return img


if __name__ == "__main__":
    image = render()
    image.save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    image.resize((256, 256), Image.LANCZOS).save(OUT.with_suffix(".png"))
    image.resize((180, 180), Image.LANCZOS).save(ROOT / "static" / "icon.png")  # phones: tab + home screen
    print(f"Wrote {OUT}")
