from __future__ import annotations

import html
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from bot.constants import (
    ACCOUNT_STATUSES,
    DISPUTE_STATUSES,
    PAYMENT_STATUSES,
    PLATFORMS,
    TRANSACTION_STATUSES,
)


def h(value: object) -> str:
    """HTML uchun xavfsiz matn."""
    return html.escape(str(value), quote=False)


def money(value: Decimal | float | str) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        amount = Decimal(0)
    if amount == amount.to_integral_value():
        formatted = f"{int(amount):,}".replace(",", " ")
    else:
        formatted = f"{amount:,.2f}".replace(",", " ")
    return f"{formatted} so'm"


def num(value: Decimal | float | str) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        amount = Decimal(0)
    if amount == amount.to_integral_value():
        return f"{int(amount):,}".replace(",", " ")
    return f"{amount:,.2f}".replace(",", " ")


def parse_price(raw: str) -> Decimal | None:
    cleaned = (
        raw.strip()
        .lower()
        .replace("so'm", "")
        .replace("сум", "")
        .replace(" ", "")
        .replace(",", "")
        .replace("_", "")
    )
    if not cleaned.isdigit():
        return None
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return value


def user_display(user) -> str:
    name = user.full_name or "Foydalanuvchi"
    if user.username:
        return f"{h(name)} (@{h(user.username)})"
    return h(name)


def user_contact(user) -> str:
    name = h(user.full_name or "Foydalanuvchi")
    if user.username:
        return f"@{h(user.username)}"
    return f'<a href="tg://user?id={user.telegram_id}">{name}</a>'


def rating_text(user) -> str:
    if not user.rating_count:
        return "— (hali baho yo'q)"
    value = user.rating_sum / user.rating_count
    return f"{value:.1f} ⭐ ({user.rating_count} ta baho)"


def platform_name(key: str) -> str:
    return PLATFORMS.get(key, key)


def account_status(key: str) -> str:
    return ACCOUNT_STATUSES.get(key, key)


def tx_status(key: str) -> str:
    return TRANSACTION_STATUSES.get(key, key)


def payment_status(key: str) -> str:
    return PAYMENT_STATUSES.get(key, key)


def dispute_status(key: str) -> str:
    return DISPUTE_STATUSES.get(key, key)


def fmt_dt(value: datetime | None) -> str:
    if not value:
        return "—"
    local_tz = timezone(timedelta(hours=5))
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(local_tz).strftime("%d.%m.%Y %H:%M")


def truncate(text: str, limit: int = 80) -> str:
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
