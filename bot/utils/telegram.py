from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InputMediaPhoto

logger = logging.getLogger(__name__)


async def safe_edit(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
    *,
    parse_mode: str | None = "HTML",
) -> None:
    try:
        if callback.message is not None:
            await callback.message.edit_text(
                text,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode=parse_mode,
            )
        else:
            await callback.bot.send_message(
                callback.from_user.id,
                text,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode=parse_mode,
            )
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc):
            return
        try:
            await callback.bot.send_message(
                callback.from_user.id,
                text,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode=parse_mode,
            )
        except Exception:  # noqa: BLE001
            logger.warning("Xabarni tahrirlash/yuborishda xatolik.")
    except Exception:  # noqa: BLE001
        logger.warning("Xabarni tahrirlashda kutilmagan xatolik.")


async def send_account_photos(bot: Bot, chat_id: int, file_ids: list[str]) -> None:
    if not file_ids:
        return
    try:
        if len(file_ids) == 1:
            await bot.send_photo(chat_id, file_ids[0])
        else:
            media = [InputMediaPhoto(media=file_id) for file_id in file_ids[:10]]
            await bot.send_media_group(chat_id, media)
    except Exception:  # noqa: BLE001
        logger.warning("Akkaunt rasmlarini yuborishda xatolik.")
