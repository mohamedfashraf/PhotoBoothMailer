"""Colors and fonts. Every color is a (light, dark) pair so the app follows Windows light/dark mode."""
from __future__ import annotations

import tkinter.font as tkfont

import customtkinter as ctk

FAMILY = "Segoe UI"

ACCENT = ("#5B5BF7", "#7B7BFF")
ACCENT_HOVER = ("#4646E6", "#6767F0")
ACCENT_SOFT = ("#EEEEFF", "#24244A")
ACCENT_TEXT = ("#3F3FD6", "#A9A9FF")

BG = ("#F5F6FA", "#0F1014")
SIDEBAR = ("#FFFFFF", "#16171C")
CARD = ("#FFFFFF", "#1A1B21")
BORDER = ("#E4E6EE", "#2A2C35")
FIELD = ("#F7F8FB", "#21222A")
SOFT = ("#EEF0F5", "#24252E")
SOFT_HOVER = ("#E1E4ED", "#2F313B")

TEXT = ("#15161C", "#F1F2F6")
MUTED = ("#686C7E", "#9A9DAE")

SUCCESS = ("#15803D", "#4ADE80")
SUCCESS_SOFT = ("#E7F7EC", "#15301F")
ERROR = ("#DC2626", "#F87171")
WARNING = ("#B45309", "#FBBF24")


def pick_font_family(root) -> None:
    """Prefer Windows 11's Segoe UI Variable when it's installed."""
    global FAMILY
    try:
        available = set(tkfont.families(root))
    except Exception:
        return
    for name in ("Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI"):
        if name in available:
            FAMILY = name
            return


def font(size: int = 14, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FAMILY, size=size, weight=weight)


def apply_appearance(mode: str) -> None:
    ctk.set_appearance_mode(mode if mode in ("system", "light", "dark") else "system")
