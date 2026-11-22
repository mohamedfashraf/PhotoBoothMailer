"""Event branding on the guest page: a colour, an optional message and an optional Instagram popup."""
from __future__ import annotations

import colorsys
import re

# name -> main colour. The first one (black) is the default.
PRESETS: dict[str, str] = {
    "Black": "#18181B",
    "Rose": "#E11D48",
    "Gold": "#B7791F",
    "Emerald": "#059669",
    "Ocean": "#0284C7",
    "Indigo": "#4F46E5",
    "Plum": "#9333EA",
}
DEFAULT_COLOR = PRESETS["Black"]


def _rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02x}" for c in rgb)


def _mix(a: str, b: str, amount: float) -> str:
    """amount=0 -> a, amount=1 -> b."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex(tuple(x + (y - x) * amount for x, y in zip(ra, rb)))


def _lightness(hex_color: str, factor: float) -> str:
    h, l, s = colorsys.rgb_to_hls(*_rgb(hex_color))
    return _hex(colorsys.hls_to_rgb(h, max(0.0, min(1.0, l * factor)), s))


def valid_color(text: str) -> bool:
    text = text.strip()
    return len(text) == 7 and text.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in text[1:])


def palette(color: str) -> dict[str, dict[str, str]]:
    """CSS colours for the guest page, for light and dark mode, from one main colour."""
    color = color if valid_color(color) else DEFAULT_COLOR
    light_accent = color
    dark_accent = _mix(color, "#ffffff", 0.18)  # a little brighter on a dark background
    return {
        "light": {"accent": light_accent, "accent-hover": _lightness(light_accent, 0.85),
                  "accent-soft": _mix(light_accent, "#ffffff", 0.9), "accent-text": _lightness(light_accent, 0.8),
                  "on-accent": "#ffffff"},
        "dark": {"accent": dark_accent, "accent-hover": _lightness(dark_accent, 0.88),
                 "accent-soft": _mix(dark_accent, "#0f1014", 0.78), "accent-text": _mix(dark_accent, "#ffffff", 0.35),
                 "on-accent": "#ffffff"},
    }


def css(color: str) -> str:
    """A <style> body that overrides the guest page's accent colours ("" for the default colour)."""
    if not valid_color(color) or color.upper() == DEFAULT_COLOR.upper():
        return ""
    p = palette(color)

    def block(values: dict[str, str]) -> str:
        return " ".join(f"--{k}: {v};" for k, v in values.items())

    return (f":root {{ {block(p['light'])} }}\n"
            f"@media (prefers-color-scheme: dark) {{ :root {{ {block(p['dark'])} }} }}")


# ---------------------------------------------------------------- Instagram popup
INSTAGRAM_DEFAULT_MESSAGE = "Can you follow us on Instagram"
_HANDLE = re.compile(r"^[A-Za-z0-9._]{1,30}$")


def instagram_handle(text: str) -> str:
    """'@studio', 'studio', 'instagram.com/studio', 'https://www.instagram.com/studio/?hl=en' -> 'studio'.

    Returns "" if it doesn't look like an Instagram account.
    """
    text = (text or "").strip()
    match = re.match(r"^(?:https?://)?(?:www\.|m\.)?(?:instagram\.com|instagr\.am)/([^/?#\s]+)", text, re.I)
    handle = match.group(1) if match else text.lstrip("@")
    return handle if _HANDLE.match(handle) and handle.lower() not in {"p", "reel", "explore", "accounts"} else ""


def instagram_url(text: str) -> str:
    handle = instagram_handle(text)
    return f"https://www.instagram.com/{handle}/" if handle else ""
