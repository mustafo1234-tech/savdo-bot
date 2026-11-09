from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import get_config
from bot.database.models import User
from bot.services.settings import is_maintenance

logger = logging.getLogger(__name__)

ALLOWED_WITHOUT_RULES = {"rules:accept", "rules:reject", "rules:show"}


class UserMiddleware(BaseMiddleware):
    """Foydalanuvchini bazaga yozadi, ban/texnik xizmat/qoidalarni tekshiradi."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user") or getattr(event, "from_user", None)
        if tg_user is None or getattr(tg_user, "is_bot", False):
            return await handler(event, data)

        session: AsyncSession | None = data.get("session")
        if session is None:
            async with self.session_factory() as new_session:
                data["session"] = new_session
                return await self._process(handler, event, data, tg_user)

        return await self._process(handler, event, data, tg_user)

    async def _process(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
        tg_user,
    ) -> Any:
        session: AsyncSession = data["session"]
        config = get_config()

        user = await session.scalar(select(User).where(User.telegram_id == tg_user.id))
        full_name = (tg_user.first_name or "Foydalanuvchi").strip()
        if getattr(tg_user, "last_name", None):
            full_name = f"{full_name} {tg_user.last_name}".strip()

        if user is None:
            user = User(
                telegram_id=tg_user.id,
                username=tg_user.username,
                full_name=full_name[:255],
                rules_accepted=tg_user.id == config.owner_id,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            changed = False
            if user.username != tg_user.username:
                user.username = tg_user.username
                changed = True
            if full_name and user.full_name != full_name[:255]:
                user.full_name = full_name[:255]
                changed = True
            if tg_user.id == config.owner_id and not user.rules_accepted:
                user.rules_accepted = True
                changed = True
            if changed:
                await session.commit()

        data["user"] = user
        is_owner = user.telegram_id == config.owner_id
        data["is_owner"] = is_owner

        if user.is_banned and not is_owner:
            if isinstance(event, CallbackQuery):
                await event.answer("🚫 Siz botdan banlangansiz.", show_alert=True)
            else:
                await event.answer("🚫 <b>Siz botdan banlangansiz.</b>\n\nMurojaat uchun admin bilan bog'laning.")
            return None

        if not is_owner:
            try:
                maintenance = await is_maintenance(session)
            except Exception:  # noqa: BLE001
                maintenance = False
            if maintenance:
                if isinstance(event, CallbackQuery):
                    await event.answer("🛠 Bot texnik xizmatda. Keyinroq urinib ko'ring.", show_alert=True)
                else:
                    await event.answer(
                        "🛠 <b>Bot texnik xizmatda</b>\n\nIltimos, birozdan so'ng qayta urinib ko'ring."
                    )
                return None

        if not user.rules_accepted and not is_owner:
            is_start = (
                isinstance(event, Message)
                and event.text
                and event.text.strip().lower().startswith("/start")
            )
            allowed_callback = isinstance(event, CallbackQuery) and event.data in ALLOWED_WITHOUT_RULES
            if not is_start and not allowed_callback:
                from bot.keyboards.inline import rules_keyboard
                from bot.texts import RULES_GATE_TEXT, RULES_TEXT

                if isinstance(event, CallbackQuery):
                    await event.answer("Avval qoidalarni qabul qiling.", show_alert=True)
                else:
                    await event.answer(RULES_GATE_TEXT + "\n\n" + RULES_TEXT, reply_markup=rules_keyboard())
                return None

        return await handler(event, data)
