from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config, get_config
from bot.constants import DEFAULT_SETTINGS
from bot.database.models import Setting


async def ensure_default_settings(session: AsyncSession, config: Config | None = None) -> None:
    config = config or get_config()
    defaults = dict(DEFAULT_SETTINGS)
    defaults["commission_percent"] = str(config.default_commission)
    defaults["min_price"] = str(config.default_min_price)
    defaults["support_contact"] = config.default_support

    existing = set((await session.execute(select(Setting.key))).scalars().all())
    for key, value in defaults.items():
        if key not in existing:
            session.add(Setting(key=key, value=value))
    await session.commit()


async def get_setting(session: AsyncSession, key: str, default: str | None = None) -> str:
    setting = await session.get(Setting, key)
    if setting is None:
        return default if default is not None else DEFAULT_SETTINGS.get(key, "")
    return setting.value


async def get_decimal_setting(session: AsyncSession, key: str, default: Decimal) -> Decimal:
    raw = await get_setting(session, key, str(default))
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return default


async def get_bool_setting(session: AsyncSession, key: str, default: bool = False) -> bool:
    raw = await get_setting(session, key, "true" if default else "false")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    setting = await session.get(Setting, key)
    if setting is None:
        session.add(Setting(key=key, value=str(value)))
    else:
        setting.value = str(value)
    await session.flush()


async def get_commission_percent(session: AsyncSession) -> Decimal:
    percent = await get_decimal_setting(session, "commission_percent", Decimal(10))
    if percent < 0:
        return Decimal(0)
    if percent > 50:
        return Decimal(50)
    return percent


async def get_min_price(session: AsyncSession) -> Decimal:
    value = await get_decimal_setting(session, "min_price", Decimal(5000))
    return value if value > 0 else Decimal(1)


async def is_maintenance(session: AsyncSession) -> bool:
    return await get_bool_setting(session, "maintenance", False)


async def auto_approve(session: AsyncSession) -> bool:
    return await get_bool_setting(session, "auto_approve", True)
