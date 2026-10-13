"""Configuration intentionally separates public preview from business operation."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes"}


@dataclass
class Settings:
    root_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parents[1])
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("AERZEN_DATA_DIR", str(Path.home() / ".local/share/aerzen-reference-landing"))))
    secret_key: str = field(default_factory=lambda: os.getenv("AERZEN_SECRET_KEY", ""))
    preview_mode: bool = field(default_factory=lambda: env_bool("AERZEN_PREVIEW_MODE", True))
    forms_enabled: bool = field(default_factory=lambda: env_bool("AERZEN_FORMS_ENABLED"))
    commerce_enabled: bool = field(default_factory=lambda: env_bool("AERZEN_COMMERCE_ENABLED"))
    secure_cookies: bool = field(default_factory=lambda: env_bool("AERZEN_SECURE_COOKIES", True))
    base_url: str = field(default_factory=lambda: os.getenv("AERZEN_BASE_URL", "http://127.0.0.1:8000").rstrip("/"))
    allowed_hosts: tuple[str, ...] = field(default_factory=lambda: tuple(s.strip() for s in os.getenv("AERZEN_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if s.strip()))
    session_max_age: int = 30 * 24 * 60 * 60
    max_body_bytes: int = 20_000
    rate_limit: int = 8
    rate_window_seconds: int = 3600
    retention_days: int | None = None

    def __post_init__(self) -> None:
        self.root_dir = Path(self.root_dir).resolve()
        self.data_dir = Path(self.data_dir).resolve()
        if self.root_dir / "static" == self.data_dir or (self.root_dir / "static") in self.data_dir.parents:
            raise ValueError("Database directory must be outside static files")
        if not self.secret_key:
            if not self.preview_mode:
                raise ValueError("Set a persistent AERZEN_SECRET_KEY for business operation")
            self.secret_key = secrets.token_urlsafe(48)
        if len(self.secret_key) < 32:
            raise ValueError("AERZEN_SECRET_KEY must have at least 32 characters")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
            raise ValueError("AERZEN_BASE_URL must be an origin without credentials or a path")
        if not self.preview_mode and (parsed.scheme != "https" or not self.secure_cookies):
            raise ValueError("Business operation requires HTTPS and Secure cookies")
        if "*" in self.allowed_hosts:
            raise ValueError("Explicit allowed hosts are required")
