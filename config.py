"""Load and validate SimpleMediaBrowser configuration from .env."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

GROUPS = ("admin", "user", "guest")
GROUP_RANK = {"guest": 0, "user": 1, "admin": 2}


@dataclass
class User:
    username: str
    password_hash: str
    group: str


@dataclass
class Config:
    host: str = "0.0.0.0"
    port: int = 8080
    secret_key: str = ""
    media_roots: dict[str, Path] = field(default_factory=dict)
    users: dict[str, User] = field(default_factory=dict)
    max_upload_mb: int = 2048


def _parse_media_roots(raw: str) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for entry in (e.strip() for e in raw.split(";") if e.strip()):
        if "=" not in entry:
            raise ValueError(f"MEDIA_ROOTS entry missing '=': {entry!r}")
        label, path = entry.split("=", 1)
        label = label.strip()
        path_obj = Path(path.strip()).expanduser()
        if not label:
            raise ValueError(f"MEDIA_ROOTS entry has empty label: {entry!r}")
        if not path_obj.is_absolute():
            raise ValueError(
                f"MEDIA_ROOTS path for {label!r} must be absolute: {path_obj}"
            )
        if not path_obj.exists() or not path_obj.is_dir():
            print(
                f"[SimpleMediaBrowser] WARNING: media root {label!r} -> {path_obj} "
                "does not exist or is not a directory.",
                file=sys.stderr,
            )
        roots[label] = path_obj.resolve()
    if not roots:
        raise ValueError("MEDIA_ROOTS is empty. Add at least one Label=Path entry.")
    return roots


def _parse_users(raw: str) -> dict[str, User]:
    users: dict[str, User] = {}
    for entry in (e.strip() for e in raw.split(";") if e.strip()):
        parts = entry.split(":")
        if len(parts) != 3:
            raise ValueError(
                f"USERS entry must be 'username:password:group', got: {entry!r}"
            )
        username, password, group = (p.strip() for p in parts)
        if not username or not password:
            raise ValueError(f"USERS entry has empty username/password: {entry!r}")
        if group not in GROUPS:
            raise ValueError(
                f"USERS entry {username!r} has unknown group {group!r}. "
                f"Must be one of {GROUPS}."
            )
        if username in users:
            raise ValueError(f"USERS has duplicate username: {username!r}")
        users[username] = User(
            username=username,
            password_hash=generate_password_hash(password),
            group=group,
        )
    if not users:
        raise ValueError("USERS is empty. Add at least one user.")
    return users


def load_config(env_path: Path | None = None) -> Config:
    if env_path is None:
        env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        raise FileNotFoundError(
            f".env not found at {env_path}. "
            "Copy .env.example to .env and edit the values."
        )
    load_dotenv(env_path, override=True)

    secret = os.environ.get("SECRET_KEY", "").strip()
    if not secret or secret.startswith("change-me"):
        raise ValueError(
            "SECRET_KEY is unset or still the default. "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    cfg = Config(
        host=os.environ.get("HOST", "0.0.0.0").strip() or "0.0.0.0",
        port=int(os.environ.get("PORT", "8080").strip() or "8080"),
        secret_key=secret,
        media_roots=_parse_media_roots(os.environ.get("MEDIA_ROOTS", "")),
        users=_parse_users(os.environ.get("USERS", "")),
        max_upload_mb=int(os.environ.get("MAX_UPLOAD_MB", "2048").strip() or "2048"),
    )
    return cfg


def group_allows(user_group: str, required: str) -> bool:
    return GROUP_RANK.get(user_group, -1) >= GROUP_RANK.get(required, 999)
