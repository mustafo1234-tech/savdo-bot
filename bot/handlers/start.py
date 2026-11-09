from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constants import PROFILE_ACCEPTED, PROFILE_DECLINED
from bot.database.models import User
from bot.keyboards.inline import (
    main_menu_keyboard,
    profile_consent_keyboard,
    rules_keyboard,
)
from bot.texts import (
    PROFILE_ACCEPTED_TEXT,
    PROFILE_CONSENT_TEXT,
    PROFILE_DECLINED_TEXT,
    RULES_GATE_TEXT,
    RULES_REJECTED_TEXT,
    RULES_TEXT,
    main_menu_text,
)
from bot.utils.telegram import safe_edit

logger = logging.getLogger(__name__)
router = Router(name="start")


def _needs_profile_consent(user: User) -> bool:
    return user.profile_consent is None


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    user: User,
    is_owner: bool = False,
) -> None:
    await state.clear()
    if not (user.rules_accepted or is_owner):
        await message.answer(RULES_TEXT, reply_markup=rules_keyboard())
        return
    if not is_owner and _needs_profile_consent(user):
        await message.answer(PROFILE_CONSENT_TEXT, reply_markup=profile_consent_keyboard())
        return
    await message.answer(main_menu_text(user), reply_markup=main_menu_keyboard())


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, user: User, is_owner: bool = False) -> None:
    await state.clear()
    if not (user.rules_accepted or is_owner):
        await message.answer(RULES_GATE_TEXT + "\n\n" + RULES_TEXT, reply_markup=rules_keyboard())
        return
    if not is_owner and _needs_profile_consent(user):
        await message.answer(PROFILE_CONSENT_TEXT, reply_markup=profile_consent_keyboard())
        return
    await message.answer(main_menu_text(user), reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "rules:accept")
async def accept_rules(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    is_owner: bool = False,
) -> None:
    if not user.rules_accepted:
        user.rules_accepted = True
        await session.commit()
    await state.clear()
    await callback.answer("✅ Qoidalar qabul qilindi")
    if not is_owner and _needs_profile_consent(user):
        await safe_edit(callback, PROFILE_CONSENT_TEXT, profile_consent_keyboard())
        return
    await safe_edit(callback, main_menu_text(user), main_menu_keyboard())


@router.callback_query(F.data == "profile:share")
async def profile_share(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    user.profile_consent = PROFILE_ACCEPTED
    await session.commit()
    await state.clear()
    await callback.answer("✅ Profil ulashildi")
    await safe_edit(
        callback,
        PROFILE_ACCEPTED_TEXT + "\n\n" + main_menu_text(user),
        main_menu_keyboard(),
    )


@router.callback_query(F.data == "profile:decline")
async def profile_decline(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    user.profile_consent = PROFILE_DECLINED
    await session.commit()
    await state.clear()
    await callback.answer("🔐 Yashirin rejim")
    await safe_edit(callback, PROFILE_DECLINED_TEXT, main_menu_keyboard())


@router.callback_query(F.data == "rules:reject")
async def reject_rules(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("❌ Rad etildi")
    await safe_edit(callback, RULES_REJECTED_TEXT, rules_keyboard())


@router.callback_query(F.data == "rules:show")
async def show_rules(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await safe_edit(callback, RULES_TEXT, rules_keyboard())


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer("ℹ️ Bu tugma hozir faol emas.")
