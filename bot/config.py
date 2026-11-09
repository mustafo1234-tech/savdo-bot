from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class ConfigError(RuntimeError):
    """Konfiguratsiya xatosi."""


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int | None = None, required: bool = False) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        if required:
            raise ConfigError(f"{name} muhit o'zgaruvchisi majburiy.")
        if default is None:
            raise ConfigError(f"{name} noto'g'ri sozlangan.")
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} butun son bo'lishi kerak.") from exc


def _decimal(name: str, default: Decimal) -> Decimal:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return Decimal(raw)
    except Exception as exc:
        raise ConfigError(f"{name} raqam bo'lishi kerak.") from exc


def to_async_database_url(url: str) -> str:
    """Render/Heroku beradigan URL ni asyncpg formatiga keltiradi."""
    url = url.strip()
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


def to_sync_database_url(url: str) -> str:
    """Alembic uchun sinxron drayver URL manzili."""
    url = url.strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://") :]
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


@dataclass(frozen=True)
class Config:
    bot_token: str
    owner_id: int
    database_url: str
    encryption_key: str
    secret_key: str
    click_service_id: str | None = None
    click_merchant_id: str | None = None
    click_secret_key: str | None = None
    click_merchant_user_id: str | None = None
    public_base_url: str | None = None
    web_host: str = "0.0.0.0"
    web_port: int = 8080
    auto_create_tables: bool = True
    default_commission: Decimal = Decimal(10)
    default_min_price: Decimal = Decimal(5000)
    default_support: str = "@support"
    throttle_limit: int = 8
    throttle_window: float = 3.0
    log_level: str = "INFO"
    debug: bool = False

    @property
    def async_database_url(self) -> str:
        return to_async_database_url(self.database_url)

    @property
    def sync_database_url(self) -> str:
        return to_sync_database_url(self.database_url)

    @property
    def click_enabled(self) -> bool:
        return bool(self.click_service_id and self.click_merchant_id and self.click_secret_key)


_config: Config | None = None


def load_config(force: bool = False) -> Config:
    global _config
    if _config is not None and not force:
        return _config

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token or ":" not in bot_token:
        raise ConfigError("BOT_TOKEN noto'g'ri yoki ko'rsatilmagan.")

    owner_id = _int("OWNER_ID", required=True)

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise ConfigError("DATABASE_URL ko'rsatilmagan.")

    secret_key = os.getenv("SECRET_KEY", "").strip()
    encryption_key_raw = os.getenv("ENCRYPTION_KEY", "").strip()
    if not secret_key and not encryption_key_raw:
        raise ConfigError("SECRET_KEY yoki ENCRYPTION_KEY ko'rsatilishi shart.")

    key_material = (encryption_key_raw or secret_key).encode("utf-8")
    encryption_key = base64.urlsafe_b64encode(hashlib.sha256(key_material).digest()).decode("ascii")

    click_service_id = os.getenv("CLICK_SERVICE_ID", "").strip() or None
    click_merchant_id = os.getenv("CLICK_MERCHANT_ID", "").strip() or None
    click_secret_key = os.getenv("CLICK_SECRET_KEY", "").strip() or None
    if any((click_service_id, click_merchant_id, click_secret_key)) and not all(
        (click_service_id, click_merchant_id, click_secret_key)
    ):
        raise ConfigError(
            "Click uchun CLICK_SERVICE_ID, CLICK_MERCHANT_ID va CLICK_SECRET_KEY birgalikda kerak."
        )

    _config = Config(
        bot_token=bot_token,
        owner_id=owner_id,
        database_url=database_url,
        encryption_key=encryption_key,
        secret_key=secret_key or encryption_key_raw,
        click_service_id=click_service_id,
        click_merchant_id=click_merchant_id,
        click_secret_key=click_secret_key,
        click_merchant_user_id=os.getenv("CLICK_MERCHANT_USER_ID", "").strip() or None,
        public_base_url=(os.getenv("PUBLIC_BASE_URL", "").strip() or None),
        web_host=os.getenv("WEB_HOST", "0.0.0.0").strip() or "0.0.0.0",
        web_port=_int("PORT", 8080),
        auto_create_tables=_bool("AUTO_CREATE_TABLES", True),
        default_commission=_decimal("DEFAULT_COMMISSION", Decimal(10)),
        default_min_price=_decimal("DEFAULT_MIN_PRICE", Decimal(5000)),
        default_support=os.getenv("DEFAULT_SUPPORT", "@support").strip() or "@support",
        throttle_limit=_int("THROTTLE_LIMIT", 8),
        throttle_window=float(os.getenv("THROTTLE_WINDOW", "3") or 3),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        debug=_bool("DEBUG", False),
    )
    return _config


def get_config() -> Config:
    if _config is None:
        return load_config()
    return _config
