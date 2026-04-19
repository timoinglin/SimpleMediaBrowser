"""SimpleMediaBrowser — a simple self-hosted file/media browser."""
from __future__ import annotations

import hashlib
import io
import mimetypes
import secrets
import shutil
from datetime import timedelta
from functools import wraps
from pathlib import Path
from typing import Callable

from flask import (
    Flask,
    abort,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from config import Config, group_allows, load_config

BASE_DIR = Path(__file__).parent.resolve()
THUMB_DIR = BASE_DIR / ".thumbs"
THUMB_DIR.mkdir(exist_ok=True)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".webm", ".ogv", ".mov", ".mkv", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".oga", ".flac", ".m4a", ".aac"}


def classify(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    return "file"


def human_size(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024.0:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"


def create_app(config: Config) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.update(
        SECRET_KEY=config.secret_key,
        MAX_CONTENT_LENGTH=config.max_upload_mb * 1024 * 1024,
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    app.jinja_env.globals["human_size"] = human_size
    app.jinja_env.globals["classify"] = classify

    # --- Helpers ---

    def current_user():
        uname = session.get("user")
        if uname and uname in config.users:
            return config.users[uname]
        return None

    def resolve_path(root_label: str, subpath: str) -> Path:
        if root_label not in config.media_roots:
            abort(404, "Unknown media root")
        root = config.media_roots[root_label]
        sub = (subpath or "").replace("\\", "/").strip("/")
        candidate = (root / sub).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            abort(400, "Invalid path")
        return candidate

    def csrf_token() -> str:
        tok = session.get("_csrf")
        if not tok:
            tok = secrets.token_urlsafe(32)
            session["_csrf"] = tok
        return tok

    def require_login(view: Callable) -> Callable:
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return redirect(url_for("login", next=request.path))
            g.user = user
            return view(*args, **kwargs)
        return wrapper

    def require_group(group: str) -> Callable:
        def deco(view: Callable) -> Callable:
            @wraps(view)
            def wrapper(*args, **kwargs):
                user = current_user()
                if not user:
                    return redirect(url_for("login", next=request.path))
                if not group_allows(user.group, group):
                    abort(403)
                g.user = user
                return view(*args, **kwargs)
            return wrapper
        return deco

    def check_csrf():
        token = request.form.get("_csrf") or request.headers.get("X-CSRF-Token", "")
        expected = session.get("_csrf", "")
        if not expected or not secrets.compare_digest(token, expected):
            abort(400, "Invalid CSRF token")

    @app.context_processor
    def inject_common():
        return {
            "current_user": current_user(),
            "csrf_token": csrf_token,
            "media_root_labels": list(config.media_roots.keys()),
        }

    # --- Auth ---

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            uname = (request.form.get("username") or "").strip()
            pw = request.form.get("password") or ""
            user = config.users.get(uname)
            if user and check_password_hash(user.password_hash, pw):
                session.permanent = True
                session["user"] = user.username
                session["_csrf"] = secrets.token_urlsafe(32)
                nxt = request.args.get("next") or url_for("index")
                if not nxt.startswith("/"):
                    nxt = url_for("index")
                return redirect(nxt)
            flash("Invalid username or password.", "error")
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        check_csrf()
        session.clear()
        return redirect(url_for("login"))

    # --- Browsing ---

    @app.route("/")
    @require_login
    def index():
        roots = []
        for label, path in config.media_roots.items():
            roots.append({"label": label, "path": str(path), "exists": path.exists()})
        return render_template("browser.html", mode="roots", roots=roots)

    @app.route("/browse/<root>/", defaults={"subpath": ""})
    @app.route("/browse/<root>/<path:subpath>")
    @require_login
    def browse(root: str, subpath: str):
        target = resolve_path(root, subpath)
        if not target.exists():
            abort(404)
        if not target.is_dir():
            return redirect(url_for("view", root=root, subpath=subpath))

        entries = []
        try:
            for child in sorted(
                target.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            ):
                try:
                    stat = child.stat()
                except OSError:
                    continue
                entries.append({
                    "name": child.name,
                    "is_dir": child.is_dir(),
                    "size": stat.st_size if child.is_file() else 0,
                    "mtime": stat.st_mtime,
                    "kind": "folder" if child.is_dir() else classify(child.name),
                })
        except PermissionError:
            abort(403, "Permission denied reading folder")

        crumbs = []
        accum = ""
        crumbs.append({"label": root, "url": url_for("browse", root=root, subpath="")})
        if subpath:
            for part in subpath.replace("\\", "/").strip("/").split("/"):
                accum = f"{accum}/{part}" if accum else part
                crumbs.append({
                    "label": part,
                    "url": url_for("browse", root=root, subpath=accum),
                })

        return render_template(
            "browser.html",
            mode="folder",
            root=root,
            subpath=subpath,
            entries=entries,
            crumbs=crumbs,
        )

    # --- File access ---

    @app.route("/view/<root>/<path:subpath>")
    @require_login
    def view(root: str, subpath: str):
        target = resolve_path(root, subpath)
        if not target.is_file():
            abort(404)
        mime, _ = mimetypes.guess_type(str(target))
        return send_file(
            str(target),
            mimetype=mime,
            conditional=True,
            download_name=target.name,
        )

    @app.route("/download/<root>/<path:subpath>")
    @require_group("user")
    def download(root: str, subpath: str):
        target = resolve_path(root, subpath)
        if not target.is_file():
            abort(404)
        return send_file(
            str(target),
            as_attachment=True,
            download_name=target.name,
            conditional=True,
        )

    @app.route("/api/thumb/<root>/<path:subpath>")
    @require_login
    def thumb(root: str, subpath: str):
        target = resolve_path(root, subpath)
        if not target.is_file() or classify(target.name) != "image":
            abort(404)
        try:
            stat = target.stat()
        except OSError:
            abort(404)
        key = hashlib.sha1(
            f"{target}|{stat.st_mtime_ns}|{stat.st_size}".encode()
        ).hexdigest()
        cache_path = THUMB_DIR / f"{key}.webp"
        if not cache_path.exists():
            try:
                from PIL import Image, ImageOps
            except ImportError:
                abort(500, "Pillow not installed")
            try:
                with Image.open(target) as im:
                    im = ImageOps.exif_transpose(im)
                    im.thumbnail((256, 256))
                    if im.mode not in ("RGB", "RGBA"):
                        im = im.convert("RGB")
                    im.save(cache_path, "WEBP", quality=80, method=4)
            except Exception:
                abort(500, "Could not generate thumbnail")
        return send_file(str(cache_path), mimetype="image/webp", conditional=True)

    # --- Mutations ---

    @app.route("/upload/<root>/", defaults={"subpath": ""}, methods=["POST"])
    @app.route("/upload/<root>/<path:subpath>", methods=["POST"])
    @require_group("user")
    def upload(root: str, subpath: str):
        check_csrf()
        target_dir = resolve_path(root, subpath)
        if not target_dir.is_dir():
            abort(400, "Upload target is not a folder")
        files = request.files.getlist("files")
        if not files:
            abort(400, "No files in upload")
        saved = 0
        for f in files:
            if not f or not f.filename:
                continue
            safe = secure_filename(f.filename)
            if not safe:
                continue
            dest = (target_dir / safe).resolve()
            try:
                dest.relative_to(target_dir)
            except ValueError:
                continue
            f.save(str(dest))
            saved += 1
        flash(f"Uploaded {saved} file(s).", "success")
        return redirect(url_for("browse", root=root, subpath=subpath))

    @app.route("/mkdir/<root>/", defaults={"subpath": ""}, methods=["POST"])
    @app.route("/mkdir/<root>/<path:subpath>", methods=["POST"])
    @require_group("admin")
    def mkdir(root: str, subpath: str):
        check_csrf()
        parent = resolve_path(root, subpath)
        if not parent.is_dir():
            abort(400, "Parent is not a folder")
        name = (request.form.get("name") or "").strip()
        safe = secure_filename(name)
        if not safe:
            flash("Invalid folder name.", "error")
            return redirect(url_for("browse", root=root, subpath=subpath))
        new_dir = (parent / safe).resolve()
        try:
            new_dir.relative_to(parent)
        except ValueError:
            abort(400, "Invalid path")
        try:
            new_dir.mkdir(exist_ok=False)
            flash(f"Created folder '{safe}'.", "success")
        except FileExistsError:
            flash(f"Folder '{safe}' already exists.", "error")
        except OSError as exc:
            flash(f"Could not create folder: {exc}", "error")
        return redirect(url_for("browse", root=root, subpath=subpath))

    @app.route("/delete/<root>/<path:subpath>", methods=["POST"])
    @require_group("admin")
    def delete(root: str, subpath: str):
        check_csrf()
        target = resolve_path(root, subpath)
        root_path = config.media_roots[root]
        if target == root_path:
            abort(400, "Cannot delete a media root")
        if not target.exists():
            abort(404)
        parent_sub = "/".join(
            (subpath or "").replace("\\", "/").strip("/").split("/")[:-1]
        )
        try:
            if target.is_dir():
                shutil.rmtree(target)
                flash(f"Deleted folder '{target.name}'.", "success")
            else:
                target.unlink()
                flash(f"Deleted '{target.name}'.", "success")
        except OSError as exc:
            flash(f"Could not delete: {exc}", "error")
        return redirect(url_for("browse", root=root, subpath=parent_sub))

    # --- Favicon / logo ---

    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(
            app.static_folder, "logo.png", mimetype="image/png"
        )

    # --- Error pages ---

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error_page(err):
        code = getattr(err, "code", 500)
        msg = getattr(err, "description", str(err))
        return render_template("error.html", code=code, message=msg), code

    return app


def main():
    try:
        cfg = load_config()
    except Exception as exc:
        print(f"[SimpleMediaBrowser] Configuration error: {exc}")
        raise SystemExit(1)
    app = create_app(cfg)
    print(f"[SimpleMediaBrowser] Listening on http://{cfg.host}:{cfg.port}")
    print(f"[SimpleMediaBrowser] Media roots: {list(cfg.media_roots.keys())}")
    print(f"[SimpleMediaBrowser] Users: {list(cfg.users.keys())}")
    app.run(host=cfg.host, port=cfg.port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
