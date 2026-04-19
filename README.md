# SimpleMediaBrowser

A tiny, self-hosted file and media browser meant for **simple media sharing and browsing for private use** — for example, sharing photos and videos inside a family or with a handful of friends on your home network. No admin UI, no database, just a single `.env` file and one `python app.py`.

- **Zero admin UI** — users, media folders, host/port all live in `.env`
- **3 permission tiers** — `admin` (read/upload/download/delete/mkdir), `user` (read/upload/download), `guest` (read-only)
- **Mobile-first responsive UI** with a dark/light toggle
- **Inline media playback** — HTML5 `<video>` / `<audio>` with byte-range seeking, image thumbnails, lightbox
- **One-click Windows installer** (`install.bat`) — auto-installs Python via `winget`, creates a `.venv`, installs deps, seeds `.env`
- **MIT licensed**

---

## Quick start — Windows (one-click)

1. Clone or download this repo.
2. Double-click **`install.bat`**. It will:
   - Check for Python; install Python 3.12 via `winget` if missing
   - Create a virtual environment in `.venv`
   - Install the Python dependencies
   - Copy `.env.example` to `.env` and generate a random `SECRET_KEY`
3. Open **`.env`** and edit `MEDIA_ROOTS` and `USERS` (see [Configuration](#configuration)).
4. Double-click **`start_mediabrowser.bat`** to launch. By default it listens on <http://localhost:8080>.

> If Python was freshly installed, close the command window and open a new one before running `install.bat` again, so the PATH picks up Python.

## Quick start — macOS / Linux

```bash
git clone <this-repo>
cd mediabrowser
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env
python app.py
```

---

## Configuration

All configuration lives in `.env`. Copy from `.env.example` and edit in place.

| Key | Example | Description |
|-----|---------|-------------|
| `HOST` | `0.0.0.0` | Interface to bind. Use `127.0.0.1` for localhost-only. |
| `PORT` | `8080` | TCP port. |
| `SECRET_KEY` | `b6e9...` | Random hex string used to sign session cookies. The installer generates one for you. Regenerate with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `MEDIA_ROOTS` | `Movies=C:\Media\Movies;Photos=C:\Media\Photos` | Semicolon-separated `Label=AbsolutePath` pairs. Each label becomes a library tile on the home page. Paths must be absolute. |
| `USERS` | `alice:wonderland:admin;bob:builder:user;guest:guest:guest` | Semicolon-separated `username:password:group` triples. |
| `MAX_UPLOAD_MB` | `2048` | Maximum upload size per request, in megabytes. |

### Permission groups

| Group | Read | View / stream | Download | Upload | Create folder | Delete |
|-------|:----:|:-------------:|:--------:|:------:|:-------------:|:------:|
| `guest` | x | x |   |   |   |   |
| `user`  | x | x | x | x |   |   |
| `admin` | x | x | x | x | x | x |

### Example `.env`

```ini
HOST=0.0.0.0
PORT=8080
SECRET_KEY=<installer generates this>
MEDIA_ROOTS=Movies=D:\Media\Movies;Music=D:\Media\Music
USERS=alice:wonderland:admin;bob:builder:user;family:letmein:guest
MAX_UPLOAD_MB=2048
```

---

## Security notes

- **Passwords in `.env` are stored as plain text.** This is a deliberate trade-off for simplicity — on startup they are hashed in memory and never written back. Keep `.env` private: add it to `.gitignore` (it already is), and on Linux/macOS run `chmod 600 .env`.
- **Run behind a reverse proxy if exposing to the internet.** The built-in Flask server is fine for a LAN but should sit behind nginx/Caddy/Traefik with TLS for public exposure.
- Sessions are cookie-based, HTTPOnly, and SameSite=Lax, with a 7-day lifetime.
- All mutating requests (upload, mkdir, delete, logout) require a CSRF token.
- Path traversal is blocked: every request resolves the target and verifies it lies inside its configured media root.

---

## How it works

- **`app.py`** — the Flask app. All routes, auth, file ops, and thumbnail generation in one file.
- **`config.py`** — parses and validates `.env` on startup, hashing passwords into memory.
- **`templates/`** — three Jinja2 templates (base layout, login, browser).
- **`static/`** — one CSS file with CSS-variable theming and one small vanilla-JS file.
- **`.thumbs/`** — auto-created cache of WebP thumbnails for images.

Media files are streamed with HTTP `Range` support, so videos can seek without re-downloading.

---

## FAQ

**Can I add users without restarting?** No — `.env` is read at startup. Restart after edits.

**Why plain-text passwords?** To keep the installer one-click and the config human-readable. If you need hashed passwords at rest, open an issue.

**Can I use SQLite / a database?** No — that's explicitly out of scope. Use [filebrowser.org](https://filebrowser.org/) if you need admin UI, sharing links, or multi-tenant features.

**HTTPS?** Put it behind nginx/Caddy and terminate TLS there.

---

## License

MIT. See `LICENSE`.
