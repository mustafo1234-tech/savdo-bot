from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Notification

logger = logging.getLogger(__name__)


def add_notification(session: AsyncSession, user_id: int, title: str, body: str) -> None:
    session.add(Notification(user_id=user_id, title=title[:160], body=body))


async def send_user_message(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    *,
    parse_mode: str | None = "HTML",
) -> bool:
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            parse_mode=parse_mode,
        )
        return True
    except Exception:  # noqa: BLE001
        logger.warning("Foydalanuvchiga xabar yuborilmadi (chat_id=%s).", chat_id)
        return False
