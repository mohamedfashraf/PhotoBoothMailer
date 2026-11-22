# PhotoBooth Share

Guests scan a QR code with their phone and save their photo booth pictures straight to their phone.
Everything runs inside one Windows app: no accounts, no email, nothing to install on the phones.

## First launch

The app opens a short setup guide (about a minute):

1. **Photos folder**: the one folder where the booth saves all photos, each named after the guest:

   ```
   D:\Booth\Photos\Hana.jpg
   D:\Booth\Photos\Omnya & Fatma.jpg
   D:\Booth\Photos\Omnya & Fatma_1.jpg    <- same guest(s), second photo
   ```

   Photos whose names differ only by an ending like `_1`, `_2`, `-3` or ` (4)` go to the same guest.
   Upper/lower case doesn't matter (`mohammed.jpg` shows as "Mohammed"). Spaces, `&` and Arabic
   names are fine. Only `.jpg`, `.jpeg` and `.png` count; other files are ignored.
   Per-guest subfolders (`Photos\Hana\1.jpg`) also work.

   ⚠️ Two different guests with exactly the same name (two "Mohammed"s) would be treated as one
   guest. Ask the booth operator to add a surname or a number when names repeat.
2. **Event name**: shown at the top of the guest's photos page.

You can change everything later under **Settings**, or press **Run setup guide again**.

## How guests appear

The app watches the photos folder while it's open. On the **Guests** screen:

- A new guest shows up within a second as **Getting photos…**
- When no new photo has arrived for that guest for **5 seconds**, they become **Ready**. This makes
  sure a guest never sees a half-finished set of photos.
- Photos added later to the same guest are counted too.
- Every guest gets a secret, random **link code** (e.g. `q9R4sYrkw-o`). Their QR code links to that
  code, never to the guest's name, so nobody can guess someone else's photos.
- Guests and link codes are kept in `photobooth.db` next to the app, so they survive a restart.
- Double-click a guest to show their QR code.

The status column then shows what each guest did: *Ready*, *Opened, not saved yet*,
*Photos saved*, or *New photos since they saved* (more photos arrived after they downloaded: show
them their QR code again). The counter at the top shows how many guests saved their photos.

- **Export list** saves the guest list as a spreadsheet (opens in Excel, Arabic names included): each
  guest's photos, status, when they opened and saved their photos, and their link.
- **New event** starts the next event: give it a name and a photos folder. The current guest list is
  closed and its QR codes and links stop working (no photos are deleted). Always do this between
  events, especially if the booth reuses the same folder: otherwise a returning name like "Hana"
  would keep last event's link.

## QR codes: two ways

Choose in the **QR screen** tab:

**One QR for everyone** (default). Every guest scans the same code, types their name, taps their
photos and saves them. Show it on the QR screen, or press **Save poster to print** and put the
printed A4 sign next to the booth. Name search ignores capitals and small spelling differences
(`mohamed` finds "Mohammed", `أحمد` finds "احمد"). At least 2 letters must be typed and at most 8
matches are shown.

> Anyone with the link can search any name. Turn off **Guests can find their photos by typing their
> name** (QR screen tab) after the event, or use per-guest QR codes instead. Personal QR codes and
> links keep working when search is off.

**A QR per guest.** The QR screen shows a code for the newest guest as soon as their photos are
ready, so nobody has to type their name. Double-clicking a guest in the Guests list also switches to
this mode and shows that guest's code.

## The QR screen

Open it from the **QR screen** tab (or double-click a guest). It opens as a small window.

- **← / →** (or the arrow buttons, per-guest mode): show an earlier guest again. While you look
  back, new guests don't interrupt; press **Newest guest** to continue.
- **Full screen** (or **F11**): drag the window to a second screen or tablet facing guests first.
  In full screen the buttons hide; move the mouse to show them. **Esc** leaves full screen.

## Your event's look

Settings has three sections: **Event** (photos folder, event name), **Guest page** (look, Instagram)
and **App** (appearance, port, version and updates).

**Settings → Guest page → Look**: the guest page is black and white by default; pick a colour
(7 choices) if you like, and add a short message such as "Thank you for celebrating with us!".

**Settings → Guest page → Instagram**: turn on the follow popup and type your account (`@yourstudio`
or your profile link). The first time a guest opens the page they see "Can you follow us on
Instagram" (or your own text) with a **Follow on Instagram** button. They can close it with **×** or
"Not now" and still get their photos; it's shown once per phone.

## Updates

**Settings → App → Check for updates** asks GitHub for the newest version. If there is one, press
**Download** and replace the old `.exe` with the new one (settings and guests are kept, because they're
saved next to the `.exe`). This only works if the GitHub repository with the releases is public.

## How guests save their photos

The QR code opens a page on the guest's phone with their name and all their photos:

- **Save all photos**: on iPhone this opens the share menu, where **Save Images** puts them in the
  Photos app. On Android each photo is downloaded and shows up in the gallery (under Downloads).
  If the phone asks "allow multiple downloads?", tap **Allow**.
- Every photo also has its own **download** button, and tapping a photo opens it full size
  (press and hold to save).
- On a computer, **Download all as one ZIP file** gets everything at once.
- Photos are sent in full quality, named after the guest (`Omnya & Fatma - 1.jpg`).

## How phones connect

Choose in the **QR screen** tab under **How phones connect**:

**Any network (online link)**, the default. Phones can be on any Wi-Fi or on mobile data. The laptop
needs internet (venue Wi-Fi, a phone hotspot or a USB dongle). The app uses a free Cloudflare quick
tunnel: it gets a public `https://….trycloudflare.com` address that leads to the guest page on this
laptop. No account or router settings needed.

- The first time, the app downloads Cloudflare's small `cloudflared.exe` program (about 60 MB). The
  packaged `.exe` already includes it if it could be downloaded when the app was built.
- The address is **new every time the app starts** (unless you set up a permanent address, below).
  The QR screen always shows the current one. If you print the poster, print it after starting the
  app on event day.
- If the internet drops, the link reconnects by itself. Until it works again, the QR screen shows
  "Getting the online link ready…" instead of a code that wouldn't work.
- Photos travel through Cloudflare encrypted (https). The address is random and only shown in the
  QR code.

**Permanent address (optional).** The free link above is meant for testing by Cloudflare and changes
on every restart. For real events you can give the app an address that never changes, like
`https://photos.mywedding.com`, so posters can be printed days before. You need your own domain
(about $10 a year; Cloudflare sells them at cost) added to a free Cloudflare account. Then:

1. In Cloudflare, open **Zero Trust → Networks → Tunnels → Create a tunnel → Cloudflared**, and
   name it `photobooth`.
2. Copy the **token**: the long text after `--token` in the install command shown. Don't run the
   command; the app runs the tunnel itself.
3. Add a **public hostname**: a subdomain such as `photos` plus your domain. Service: **HTTP**, URL:
   **`localhost:8000`** (or your port from Settings).
4. In the app: **QR screen → How phones connect → Permanent address → Set up**, paste the address
   and the token, and press **Save**.

The status turns green once the address opens the app. If it says the address "doesn't open this
app yet", check the URL in step 3. **Remove** goes back to the free link. The token is saved in
`settings.json` next to the app; keep that file private, since anyone with the token could take over
the address.

**Same Wi-Fi only**. No internet needed, but every phone must join the same Wi-Fi or hotspot as the
laptop. Tip: turn on **Mobile Hotspot** on the laptop and let guests join it. The QR screen tab shows
the address in use (e.g. `http://192.168.1.2:8000`); leave it on **Automatic** unless phones can't
open the page.

The first time, Windows may ask whether to allow network access for the app: click **Allow**.

## Running in development

With conda (one-time setup):

```powershell
conda create -n PhotoBoothMailer python=3.12
conda activate PhotoBoothMailer
pip install -r requirements.txt
```

Run:

```powershell
conda activate PhotoBoothMailer
python main.py
python main.py --folder "D:\Booth\Photos"   # use a different photos folder for this run
python main.py --setup                      # show the setup guide again
python tunnel.py 8000                       # test the online link alone (prints its address)
```

### Test photos (no camera needed)

```powershell
python dev/make_test_photos.py           # creates test_photos\ with 9 sample guests (14 photos)
python dev/make_test_photos.py --live    # ...then adds a new guest every 20 s, like a real booth
python dev/make_test_photos.py --clean   # start test_photos\ from scratch
```

Then choose the `test_photos` folder in the app.

### Tests

```powershell
pip install -r requirements-dev.txt   # once
python -m pytest                      # about 30 seconds, no internet needed
```

They cover photo grouping, name search, the guest page (downloads, ZIP, search on/off, branding),
new events, the online link (with a stand-in for cloudflared) and the folder speed-up.
`dev/release.py` runs them before every release.

Settings are saved in `settings.json` next to the app, guests and link codes in `photobooth.db`.

## Building the .exe

```powershell
conda activate PhotoBoothMailer
.\build.bat
```

This installs PyInstaller, downloads `cloudflared.exe` into `vendor\` (so the online link works
without a download at the event) and creates **`dist\PhotoBoothShare.exe`**: one file, no console
window. Copy it to the event laptop, for example into `D:\PhotoBooth\`, and double-click it. Its
settings and database are created next to it. Opening it a second time just says it's already open.

## Versions and releases

The version number is `APP_VERSION` in `config.py`; the app shows it in the sidebar. Every version is
listed in [CHANGELOG.md](CHANGELOG.md) and published as a GitHub Release with its `.exe` attached,
so any older version can be downloaded again. `build.bat` also keeps a copy of each build in
`releases\` (e.g. `releases\PhotoBoothShare-1.0.0.exe`).

To publish a new version:

1. Change `APP_VERSION` in `config.py` (bug fix: `1.0.1`; new feature: `1.1.0`).
2. Add a `## 1.1.0 (date)` section at the top of `CHANGELOG.md` saying what changed.
3. Run `.\build.bat`.
4. Commit: `git commit -am "Version 1.1.0"`.
5. Run `python dev/release.py`. It tags the version, pushes it and creates the GitHub Release with
   the `.exe`.

## Event-day checklist

**The day before**

- [ ] Copy `PhotoBoothShare.exe` to the event laptop and open it once (setup guide: photos folder +
      event name).
- [ ] Check the booth software saves into that folder, one file per guest name (`Hana.jpg`,
      `Hana_1.jpg`).
- [ ] Take a test photo, scan the QR code with your own phone **on mobile data**, and save the photo.

**At the venue**

- [ ] Laptop plugged in. (While the app is open, Windows won't sleep or turn the screen off.)
- [ ] Laptop has internet (for the online link). No internet? Switch to **Same Wi-Fi only** and turn
      on the laptop's Mobile Hotspot.
- [ ] Open the app. **QR screen** tab → green "Online" status.
- [ ] Open the QR screen, drag it to the guest-facing screen or tablet, press **Full screen**.
- [ ] Printing the poster? Print it now (the online address changes when the app restarts).
- [ ] Take one test photo and save it from a phone, to check everything works end to end.

**During the event**

- [ ] Keep the app open: guests can only open their photos while it runs.
- [ ] Glance at **Guests** now and then: *Opened, not saved yet* may mean a guest needs help saving.
- [ ] Two guests with the same name? Ask the booth operator to add a surname or a number.

**After**

- [ ] Turn off name search (QR screen tab) once guests have left.
- [ ] **Export list** if you want a record of who got their photos.
- [ ] Next event: press **New event** first.
