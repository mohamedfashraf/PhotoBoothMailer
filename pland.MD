
# Project: PhotoBoothMailer (Windows desktop app, single .exe)

## Goal

A Windows desktop app for a photo booth. The booth software saves each guest's photos
into a subfolder named after them inside one watched folder, e.g.:

  D:\Booth\Photos\ahmed_ali_042\1.jpg
  D:\Booth\Photos\ahmed_ali_042\2.jpg

For every new subfolder, the app shows a QR code. The guest scans it with their phone,
a small web form opens, they enter their email, and the app emails them their photos.
No n8n, no Docker: everything runs inside one .exe.

## Tech stack

- Python 3.11+
- GUI: customtkinter (settings screen, QR display window, dashboard)
- Web form server: FastAPI + uvicorn, running in a background thread
- Folder watching: watchdog
- QR codes: qrcode + Pillow
- Email: smtplib (SMTP with TLS), configurable host/port/user/app password
- Storage: SQLite (sessions, tokens, send status) + settings.json next to the exe
- Packaging: PyInstaller --onefile --windowed

## Features

1. Settings screen (first launch, editable later)

   - Browse button to pick the watched folder (saved to settings.json)
   - Event name (shown on the form and in the email)
   - SMTP settings + "Send test email" button
   - Delivery mode: attach photos OR send a link (link mode can come later, attach first)
   - Server port (default 8000)
   - CLI override: PhotoBoothMailer.exe --folder "D:\Booth\Photos"
2. Folder watcher

   - Only watch direct subfolders of the selected folder
   - Only count .jpg / .jpeg / .png files; ignore temp/other files
   - Debounce: wait ~5 seconds after the last file is written before marking the
     session "ready", so half-written sets are never sent
   - Photos added later to an existing subfolder are included in the email
3. Sessions and security

   - Each new subfolder gets a random unguessable token (secrets.token_urlsafe(8))
   - Store folder_name <-> token in SQLite
   - The QR URL is http://<laptop-LAN-IP></laptop>:<port></port>/s/<token></token>, NEVER the folder name
   - Unknown or invalid token -> friendly "Ask the booth staff" page
4. QR display window

   - Large QR for the latest ready session, plus the guest's display name
     (derived from the folder: ahmed_ali_042 -> "Ahmed Ali")
   - Fullscreen toggle so it can sit on a second monitor/tablet facing guests
   - Buttons: previous/next session to re-show an older QR
5. Guest web form (mobile-first, works on Android + iPhone)

   - Shows event name, guest display name, a thumbnail preview of their photos
   - Email field with validation -> submit -> "Check your inbox" page
   - Can be submitted again (e.g. add a second email) without duplicating sends by accident
6. Email sending

   - Background queue so the form responds instantly
   - Resize images if total attachments > 20 MB (keep quality reasonable)
   - Retry failed sends 3 times with backoff; record status in SQLite
   - Simple HTML email template with event name
7. Dashboard (main window tab)

   - Table: guest, folder, photo count, email(s), status (waiting / sent / failed), time
   - Resend button per row
   - Shows the server URL and whether phones can reach it
8. Networking

   - Auto-detect the laptop's LAN IP (works with Windows Mobile Hotspot)
   - Show a warning if the firewall may block the port, with the netsh command to allow it

## Non-goals (for now)

- WhatsApp delivery
- Cloud hosting
- Public tunnel (design so ngrok/cloudflared can be added later)

## How to work

1. First, give me a short plan + folder structure. Wait for my OK.
2. Then build in phases, and stop after each phase so I can test:
   - Phase 1: project skeleton, settings.json, settings screen
   - Phase 2: folder watcher + debounce + SQLite sessions/tokens
   - Phase 3: QR display window
   - Phase 4: FastAPI guest form (served on LAN)
   - Phase 5: email queue + sending + retries
   - Phase 6: dashboard + resend
   - Phase 7: PyInstaller build script (build.bat) producing dist/PhotoBoothMailer.exe
3. Include a dev script that generates a fake Photos folder with sample guest
   subfolders and images, so I can test without the camera.
4. Add a README with: setup, how to run in dev, how to build the exe,
   how to set up a Gmail app password, and an event-day checklist.
5. Keep the code modular: config.py, watcher.py, db.py, server.py, mailer.py,
   gui/ (settings, qr_window, dashboard), main.py.
