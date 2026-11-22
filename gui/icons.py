"""Lucide icons (https://lucide.dev, ISC license), drawn from the bundled icon font.

Each icon becomes a CTkImage with a light and a dark version, so it follows the app theme
and stays sharp at any Windows display scaling.
"""
from __future__ import annotations

from functools import lru_cache

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

from config import resource_path

# Codepoints from lucide-static 1.70.0 (font/lucide.css).
CODES: dict[str, int] = {
    "camera": 0xE064,
    "folder": 0xE0D7,
    "folder-open": 0xE247,
    "folder-check": 0xE32E,
    "party-popper": 0xE343,
    "mail": 0xE10F,
    "mail-check": 0xE361,
    "users": 0xE1A4,
    "qr-code": 0xE1DF,
    "scan-qr-code": 0xE5F6,
    "settings": 0xE154,
    "circle-check": 0xE226,
    "circle-alert": 0xE077,
    "triangle-alert": 0xE193,
    "external-link": 0xE0B9,
    "eye": 0xE0BA,
    "eye-off": 0xE0BB,
    "arrow-left": 0xE048,
    "arrow-right": 0xE049,
    "send": 0xE152,
    "image": 0xE0F6,
    "images": 0xE5C4,
    "info": 0xE0F9,
    "hourglass": 0xE296,
    "hand": 0xE1D7,
    "sparkles": 0xE412,
    "save": 0xE14D,
    "rotate-ccw": 0xE148,
    "check": 0xE06C,
    "inbox": 0xE0F7,
    "paperclip": 0xE12D,
    "maximize": 0xE112,
    "minimize": 0xE11A,
    "chevron-left": 0xE06E,
    "chevron-right": 0xE06F,
    "globe": 0xE0E8,
    "wifi": 0xE1AE,
}

FONT_PATH = resource_path("assets/fonts/lucide.ttf")
RENDER_SCALE = 4  # draw big, let CTkImage scale down → crisp on 100–200% displays

Color = tuple[str, str]  # (light mode, dark mode)
WHITE: Color = ("#FFFFFF", "#FFFFFF")


@lru_cache(maxsize=None)
def _font(px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), px)


@lru_cache(maxsize=None)
def _glyph(name: str, px: int, color: str) -> Image.Image:
    char = chr(CODES[name])
    # Glyphs sit in a 24-unit box with ~2 units of padding: draw slightly larger to fill the canvas.
    font = _font(int(px * 1.12))
    left, top, right, bottom = font.getbbox(char)
    image = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    x = (px - (right - left)) / 2 - left
    y = (px - (bottom - top)) / 2 - top
    ImageDraw.Draw(image).text((x, y), char, font=font, fill=color)
    return image


@lru_cache(maxsize=None)
def icon(name: str, size: int = 18, color: Color = ("#15161C", "#F1F2F6")) -> ctk.CTkImage:
    px = size * RENDER_SCALE
    return ctk.CTkImage(light_image=_glyph(name, px, color[0]), dark_image=_glyph(name, px, color[1]),
                        size=(size, size))


def reset_cache() -> None:
    """Images belong to a Tk root; call when a new root window is created."""
    icon.cache_clear()
