from __future__ import annotations

import logging

from cryptography.fernet import Fernet, InvalidToken

from bot.config import get_config

logger = logging.getLogger(__name__)
_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(get_config().encryption_key.encode("ascii"))
    return _fernet


def encrypt(value: str) -> str:
    if not value:
        return ""
    return _get_fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str | None) -> str:
    if not token:
        return ""
    try:
        return _get_fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        logger.warning("Shifrlangan ma'lumotni ochib bo'lmadi (kalit o'zgargan bo'lishi mumkin).")
        return "⚠️ ma'lumot ochilmadi"
