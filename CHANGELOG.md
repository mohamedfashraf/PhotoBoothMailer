# Changelog

Every version of PhotoBooth Share. The newest is at the top. Each version is also a GitHub Release
with its `.exe` attached.

## 1.2.0 (2026-11-22)

New look: black and white, calmer and more compact.

- Black and white everywhere (app, QR screen, guest's phone page). Colour is only used where it
  means something: green = saved, red = problem, amber = warning. You can still give the guest page
  your own colour in Settings → Guest page look.
- Refined type: Windows 11's semibold font instead of heavy bold, smaller consistent sizes.
- Dark primary buttons, outlined secondary buttons, pill-style choices (like iOS / macOS) instead of
  blocky blue bars.
- Light sidebar with quiet navigation; cards with hairline borders and small icons instead of tiles.
- Guests: one quiet line of numbers instead of big boxes; only meaningful rows are coloured.
- New black and white app icon; the guest's phone page now shows it as its tab and home-screen icon.

## 1.1.2 (2026-11-22)

- More compact everywhere: smaller margins, buttons, boxes and table rows, a narrower sidebar and
  shorter texts, so more fits on a laptop screen.
- Scrollbars only appear when there is something to scroll.
- Fixed: "Light" and "Dark" in Settings → Look were almost invisible; the example text in empty
  boxes didn't show; "Look" wasn't lined up with the port box; the port hint always said 8000.
- Setup guide: removed a repeated sentence on the event step and a stray dot on the progress bar.

## 1.1.1 (2026-11-22)

- Cleaner QR screen tab: a status banner at the top shows at a glance whether guests can connect
  (with Test and refresh buttons), **Open QR screen** is always in the top corner, and the settings
  are grouped into two tidy cards: "What guests scan" and "How phones connect".
- Name search is now a clear On / Off choice (the switch was hard to see in light mode).

## 1.1.0 (2026-11-22)

- **New event** button (Guests screen): closes the current guest list and starts the next event.
  Fixes a real risk: with the same photos folder, a returning name like "Hana" used to keep last
  event's link, so last event's guest could open the new guest's photos.
- **Export list**: save the guest list as a spreadsheet (works in Excel, Arabic included).
- **Name search switch** (QR screen tab): turn it off after the event so nobody can browse names;
  personal QR codes keep working.
- **Guest page look** (Settings): your colour, logo and a short message on guests' phones; the logo
  also shows on the QR screen.
- The laptop no longer sleeps or turns its screen off while the app is open.
- Fixed: a guest with an Arabic name and one photo got a nameless download on old browsers.
- Automated tests (57) in `tests/`; `dev/release.py` runs them before every release.

## 1.0.1 (2026-11-22)

- A progress bar shows the online link being set up: it fills during the first-time download, then
  moves while connecting or reconnecting. The QR window shows one too while it waits for the link.

## 1.0.0 (2026-11-22)

First release.

- Guests scan a QR code and save their photos to their phone: share menu on iPhone, downloads on
  Android, one ZIP file on a computer. No email needed.
- One QR code for everyone (guests type their name) or one QR code per guest.
- Phones can use any network through an online link, or the same Wi-Fi as the laptop.
- Optional permanent online address with your own domain, so printed posters keep working.
- The Guests screen shows live who opened and who saved their photos.
- Photos are grouped by guest name: `Hana.jpg`, `Hana_1.jpg`, `Hana (2).jpg` are one guest, while
  "Table 5" and "Table 6" stay separate. Search ignores capitals and small spelling differences,
  and works with Arabic names and Arabic digits.
- Pages stay fast with hundreds of guests and many phones at once.
- Packaged as one `.exe` with `build.bat`.
