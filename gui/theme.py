"""Colors and fonts. Every color is a (light, dark) pair so the app follows Windows light/dark mode.

The look: black and white (zinc greys), dark primary buttons, hairline borders and semibold (not bold)
type. Colour only where it carries meaning: green = saved, red = problem, amber = warning.
"""
from __future__ import annotations

import tkinter.font as tkfont

import customtkinter as ctk

FAMILY = "Segoe UI"            # body text
SEMIBOLD = "Segoe UI Semibold"  # labels, buttons, headings (refined; plain "bold" looks heavy)
DISPLAY = "Segoe UI Semibold"   # big titles

# Black and white: the "accent" (selection, progress, highlights) is the same near-black / near-white
# as the text. Colour is kept only where it means something (green = saved, red = problem).
ACCENT = ("#18181B", "#FAFAFA")
ACCENT_HOVER = ("#3F3F46", "#E4E4E7")
ACCENT_SOFT = ("#F4F4F5", "#202024")
ACCENT_TEXT = ("#18181B", "#FAFAFA")

# Primary buttons: near-black in light mode, near-white in dark mode.
PRIMARY = ("#18181B", "#FAFAFA")
PRIMARY_HOVER = ("#3F3F46", "#E4E4E7")
PRIMARY_TEXT = ("#FFFFFF", "#18181B")

BG = ("#FAFAFA", "#0C0C0E")
SIDEBAR = ("#F4F4F5", "#121215")
CARD = ("#FFFFFF", "#17171A")
BORDER = ("#E4E4E7", "#27272A")
FIELD = ("#FFFFFF", "#1C1C20")
SOFT = ("#F4F4F5", "#202024")
SOFT_HOVER = ("#E9E9EC", "#2A2A2F")

TEXT = ("#09090B", "#FAFAFA")
MUTED = ("#71717A", "#A1A1AA")
FAINT = ("#A1A1AA", "#71717A")

SUCCESS = ("#16A34A", "#4ADE80")
SUCCESS_SOFT = ("#F0FDF4", "#0B2A17")
ERROR = ("#DC2626", "#F87171")
WARNING = ("#D97706", "#FBBF24")


def pick_font_family(root) -> None:
    """Prefer Windows 11's Segoe UI Variable (with its real Semibold) when it's installed."""
    global FAMILY, SEMIBOLD, DISPLAY
    try:
        available = set(tkfont.families(root))
    except Exception:
        return
    if "Segoe UI Variable Text" in available and "Segoe UI Variable Text Semibold" in available:
        FAMILY, SEMIBOLD = "Segoe UI Variable Text", "Segoe UI Variable Text Semibold"
        DISPLAY = "Segoe UI Variable Display Semib" if "Segoe UI Variable Display Semib" in available else SEMIBOLD
    elif "Segoe UI Semibold" in available:
        FAMILY, SEMIBOLD, DISPLAY = "Segoe UI", "Segoe UI Semibold", "Segoe UI Semibold"


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    """weight "bold" uses the semibold face; sizes from 18 up use the display face."""
    if weight == "bold":
        return ctk.CTkFont(family=DISPLAY if size >= 18 else SEMIBOLD, size=size)
    return ctk.CTkFont(family=FAMILY, size=size)


def apply_appearance(mode: str) -> None:
    ctk.set_appearance_mode(mode if mode in ("system", "light", "dark") else "system")
