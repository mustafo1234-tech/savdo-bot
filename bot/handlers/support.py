from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_config
from bot.database.models import User
from bot.keyboards.inline import cancel_keyboard, support_keyboard
from bot.services.notifications import add_notification, send_user_message
from bot.services.settings import get_setting
from bot.states import SupportStates
from bot.texts import SUPPORT_PROMPT, SUPPORT_SENT_TEXT, support_text
from bot.utils.formatting import h, user_display
from bot.utils.telegram import safe_edit

logger = logging.getLogger(__name__)
router = Router(name="support")


@router.message(Command("help"))
async def help_command(message: Message, session: AsyncSession) -> None:
    support_contact = await get_setting(session, "support_contact", "@support")
    await message.answer(support_text(support_contact), reply_markup=support_keyboard())


@router.callback_query(F.data == "support:message")
async def support_message_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SupportStates.message)
    await callback.answer()
    await safe_edit(callback, SUPPORT_PROMPT, cancel_keyboard())


@router.message(SupportStates.message, F.text)
async def support_message_send(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    text = (message.text or "").strip()
    if not 2 <= len(text) <= 3000:
        await message.answer("⚠️ Xabar 2 tadan 3000 tagacha belgidan iborat bo'lishi kerak.")
        return

    config = get_config()
    owner = await session.scalar(select(User).where(User.telegram_id == config.owner_id))
    if owner is not None:
        add_notification(session, owner.id, "Yangi murojaat", text[:500])
        await session.commit()

    sent = await send_user_message(
        message.bot,
        config.owner_id,
        "📩 <b>YANGI MUROJAAT</b>\n\n"
        f"👤 Foydalanuvchi: {user_display(user)}\n"
        f"🆔 ID: <code>{user.telegram_id}</code>\n"
        f"📎 Username: {('@' + h(user.username)) if user.username else '—'}\n\n"
        f"💬 <b>Xabar:</b>\n{h(text)}",
    )
    await state.clear()
    if sent:
        await message.answer(SUPPORT_SENT_TEXT, reply_markup=support_keyboard())
    else:
        await message.answer(
            "⚠️ Murojaatni yetkazishda xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring."
        )
