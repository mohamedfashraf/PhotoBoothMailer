"""PhotoBooth Share — entry point.

    python main.py
    python main.py --folder "D:\\Booth\\Photos"     (use this folder for this run)
    python main.py --setup                          (show the setup guide again)
"""
from __future__ import annotations

import argparse
import os
import sys

import config
from gui import theme


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="PhotoBoothShare", description="Share photo booth pictures with guests by QR code.")
    parser.add_argument("--folder", help="Photos folder to watch (overrides the saved setting for this run)")
    parser.add_argument("--setup", action="store_true", help="Open the setup guide")
    return parser.parse_args(argv)


def already_running() -> bool:
    """True if the app is already open (double-clicked twice). The mutex lives until this process exits."""
    if os.name != "nt":
        return False
    import ctypes
    global _instance_mutex
    _instance_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, f"Local\\{config.APP_ID}")
    return ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def main(argv: list[str] | None = None) -> None:
    # The packaged app has no console: give stray prints somewhere harmless to go.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if already_running():
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showinfo(config.APP_NAME, f"{config.APP_NAME} is already open. Look for it on the taskbar.")
        root.destroy()
        return

    if os.name == "nt":
        try:  # own taskbar entry/icon instead of grouping under python.exe
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(config.APP_ID)
        except Exception:
            pass

    settings = config.load()
    if args.folder:
        settings.watch_folder = os.path.normpath(os.path.abspath(args.folder))

    theme.apply_appearance(settings.appearance)

    from gui.app import App  # imported after appearance is set so widgets start in the right mode
    App(settings, force_setup=args.setup).mainloop()


if __name__ == "__main__":
    main()
