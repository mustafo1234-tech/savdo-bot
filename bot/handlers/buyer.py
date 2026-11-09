from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_config
from bot.constants import PROFILE_ACCEPTED
from bot.database.models import Account, User
from bot.keyboards.inline import (
    buyer_account_keyboard,
    buyer_browse_keyboard,
    buyer_entry_keyboard,
    cancel_keyboard,
    deal_payment_keyboard,
    profile_consent_keyboard,
)
from bot.services.deals import create_transaction
from bot.services.notifications import add_notification, send_user_message
from bot.services.settings import get_commission_percent
from bot.states import BuyerStates
from bot.texts import (
    BUYER_EMPTY_TEXT,
    BUYER_ENTRY_TEXT,
    BUYER_NOT_FOUND_TEXT,
    BUYER_SEARCH_TEXT,
    PROFILE_REQUIRED_TEXT,
    account_detail_text,
    buyer_list_text,
    deal_preview_text,
)
from bot.utils.formatting import h, money, platform_name, user_contact
from bot.utils.pagination import clamp_page, total_pages
from bot.utils.telegram import safe_edit, send_account_photos

logger = logging.getLogger(__name__)
router = Router(name="buyer")

PER_PAGE = 5


@router.callback_query(F.data == "menu:buy")
async def buyer_entry(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await safe_edit(callback, BUYER_ENTRY_TEXT, buyer_entry_keyboard())


@router.callback_query(F.data == "buyer:search")
async def buyer_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BuyerStates.search)
    await callback.answer()
    await safe_edit(callback, BUYER_SEARCH_TEXT, cancel_keyboard())


@router.message(BuyerStates.search, F.text)
async def buyer_search_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    raw = (message.text or "").strip().upper().lstrip("#")
    public_id = raw
    if raw.isdigit():
        try:
            public_id = f"ACC{int(raw)}"
        except ValueError:
            public_id = raw
    account = await session.scalar(select(Account).where(Account.public_id == public_id))
    if account is None or account.status != "ACTIVE":
        await message.answer(BUYER_NOT_FOUND_TEXT, reply_markup=buyer_entry_keyboard())
        await state.clear()
        return

    account.views += 1
    await session.commit()
    await state.clear()
    await message.answer(
        account_detail_text(account),
        reply_markup=buyer_account_keyboard(account.id, 0, account.seller_id != user.id),
    )
    await send_account_photos(message.bot, message.chat.id, [img.file_id for img in account.images])


@router.message(BuyerStates.search)
async def buyer_search_invalid(message: Message) -> None:
    await message.answer(
        "⚠️ E'lon ID sini matn ko'rinishida yuboring. Masalan: <code>ACC1001</code> yoki <code>1001</code>.",
        reply_markup=cancel_keyboard(),
    )


async def _render_browse(callback: CallbackQuery, session: AsyncSession, page: int) -> None:
    total = await session.scalar(select(func.count(Account.id)).where(Account.status == "ACTIVE")) or 0
    if total == 0:
        await safe_edit(callback, BUYER_EMPTY_TEXT, buyer_entry_keyboard())
        return
    pages = total_pages(total, PER_PAGE)
    page = clamp_page(page, pages)
    accounts = (
        await session.scalars(
            select(Account)
            .where(Account.status == "ACTIVE")
            .order_by(Account.created_at.desc())
            .offset((page - 1) * PER_PAGE)
            .limit(PER_PAGE)
        )
    ).all()
    await safe_edit(callback, buyer_list_text(page, pages, total), buyer_browse_keyboard(accounts, page, pages))


@router.callback_query(F.data == "buyer:browse")
async def buyer_browse(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await _render_browse(callback, session, 1)


@router.callback_query(F.data.startswith("buyer:page:"))
async def buyer_page(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        page = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        page = 1
    await callback.answer()
    await _render_browse(callback, session, page)


@router.callback_query(F.data.startswith("buyer:view:"))
async def buyer_view(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    parts = (callback.data or "").split(":")
    try:
        account_id = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 1
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri e'lon.", show_alert=True)
        return
    account = await session.scalar(select(Account).where(Account.id == account_id))
    if account is None or account.status != "ACTIVE":
        await callback.answer("Bu e'lon hozir faol emas.", show_alert=True)
        return

    account.views += 1
    await session.commit()
    await callback.answer()
    await safe_edit(
        callback,
        account_detail_text(account),
        buyer_account_keyboard(account.id, page, account.seller_id != user.id),
    )
    await send_account_photos(
        callback.bot,
        callback.from_user.id,
        [img.file_id for img in account.images],
    )


@router.callback_query(F.data.startswith("buyer:buy:"))
async def buyer_buy(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    if user.profile_consent != PROFILE_ACCEPTED:
        await state.clear()
        await callback.answer("🔐 Profilni ulashish kerak", show_alert=True)
        await safe_edit(callback, PROFILE_REQUIRED_TEXT, profile_consent_keyboard())
        return

    try:
        account_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri e'lon.", show_alert=True)
        return

    commission = await get_commission_percent(session)
    tx, error = await create_transaction(session, user, account_id, commission)
    if tx is None:
        messages = {
            "not_found": "E'lon topilmadi.",
            "not_active": "Bu e'lon hozir faol emas.",
            "own_account": "O'z e'loningizni sotib ololmaysiz.",
            "busy": "Bu akkaunt bo'yicha savdo allaqachon boshlangan.",
            "code_error": "Tranzaksiya yaratishda xatolik. Qayta urinib ko'ring.",
        }
        await callback.answer(messages.get(error or "", "Xatolik yuz berdi."), show_alert=True)
        return

    await state.clear()
    await callback.answer("Savdo boshlandi")
    await safe_edit(
        callback,
        deal_preview_text(tx, tx.account, tx.commission_rate),
        deal_payment_keyboard(tx.id, get_config().click_enabled),
    )

    add_notification(
        session,
        tx.seller_id,
        "Yangi buyurtma",
        f"{tx.account.public_id} akkaunti uchun buyurtma yaratildi. To'lov kutilmoqda.",
    )
    await session.commit()

    await send_user_message(
        callback.bot,
        tx.seller.telegram_id,
        "🛒 <b>YANGI BUYURTMA</b>\n\n"
        f"📜 Tranzaksiya: <code>{h(tx.code)}</code>\n"
        f"📦 #{h(tx.account.public_id)} — {h(tx.account.account_name)}\n"
        f"💵 Narx: <b>{money(tx.amount)}</b>\n"
        f"💰 Sizga o'tadi: <b>{money(tx.seller_amount)}</b>\n\n"
        "⏳ Xaridor hozir to'lov qilmoqda. To'lov tasdiqlanganda sizga darhol xabar beramiz.",
    )
    config = get_config()
    if config.owner_id != user.telegram_id:
        await send_user_message(
            callback.bot,
            config.owner_id,
            "🛒 <b>Yangi buyurtma</b>\n\n"
            f"📜 <code>{h(tx.code)}</code>\n"
            f"📦 #{h(tx.account.public_id)} — {h(platform_name(tx.account.platform))}\n"
            f"💵 {money(tx.amount)}\n"
            f"🛒 Xaridor: {user_contact(user)}\n"
            f"💰 Sotuvchi: {user_contact(tx.seller)}",
        )
