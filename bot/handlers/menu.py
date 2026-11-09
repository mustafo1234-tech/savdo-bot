from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Account, Payment, Transaction, User
from bot.keyboards.inline import (
    main_menu_keyboard,
    mylist_account_keyboard,
    pagination_keyboard,
    profile_keyboard,
    support_keyboard,
)
from bot.services.settings import get_setting
from bot.texts import (
    history_item_line,
    history_text,
    main_menu_text,
    my_listing_detail_text,
    my_listings_text,
    payment_line,
    payments_text,
    profile_text,
    support_text,
)
from bot.utils.formatting import account_status, money, num
from bot.utils.pagination import clamp_page, total_pages
from bot.utils.telegram import safe_edit

logger = logging.getLogger(__name__)
router = Router(name="menu")

LISTINGS_PER_PAGE = 5
HISTORY_PER_PAGE = 5
PAYMENTS_PER_PAGE = 6


async def _show_main_menu(callback: CallbackQuery, user: User, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(callback, main_menu_text(user), main_menu_keyboard())


@router.callback_query(F.data == "menu:home")
async def menu_home(callback: CallbackQuery, user: User, state: FSMContext) -> None:
    await callback.answer()
    await _show_main_menu(callback, user, state)


@router.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery, user: User, state: FSMContext) -> None:
    await callback.answer("Bekor qilindi")
    await _show_main_menu(callback, user, state)


@router.message(Command("cancel"))
async def cancel_command(message: Message, user: User, state: FSMContext) -> None:
    await state.clear()
    await message.answer(main_menu_text(user), reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "menu:profile")
async def menu_profile(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await state.clear()
    sold = (
        await session.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.seller_id == user.id,
                Transaction.status == "SUCCESS",
            )
        )
        or 0
    )
    bought = (
        await session.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.buyer_id == user.id,
                Transaction.status == "SUCCESS",
            )
        )
        or 0
    )
    await callback.answer()
    await safe_edit(
        callback,
        profile_text(user, sold, bought),
        profile_keyboard(user.profile_consent),
    )


def _my_listings_keyboard(accounts, page: int, pages: int):
    builder = InlineKeyboardBuilder()
    for account in accounts:
        label = f"#{account.public_id} | {account_status(account.status)} | {num(account.price)}"
        builder.button(text=label, callback_data=f"mylist:view:{account.id}")
    builder.adjust(1)
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"mylist:page:{page - 1}"))
    if page < pages:
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"mylist:page:{page + 1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="💰 Yangi e'lon", callback_data="menu:sell"))
    builder.row(InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu:home"))
    return builder.as_markup()


async def _render_my_listings(callback: CallbackQuery, user: User, session: AsyncSession, page: int) -> None:
    total = (
        await session.scalar(select(func.count(Account.id)).where(Account.seller_id == user.id)) or 0
    )
    pages = total_pages(total, LISTINGS_PER_PAGE)
    page = clamp_page(page, pages)
    accounts = (
        await session.scalars(
            select(Account)
            .where(Account.seller_id == user.id)
            .order_by(Account.created_at.desc())
            .offset((page - 1) * LISTINGS_PER_PAGE)
            .limit(LISTINGS_PER_PAGE)
        )
    ).all()
    if not accounts:
        builder = InlineKeyboardBuilder()
        builder.button(text="💰 Akkaunt sotish", callback_data="menu:sell")
        builder.button(text="🏠 Asosiy menyu", callback_data="menu:home")
        builder.adjust(1)
        await safe_edit(
            callback,
            "📦 <b>MENING E'LONLARIM</b>\n\nSizda hali e'lon yo'q. Birinchi e'loningizni joylang!",
            builder.as_markup(),
        )
        return
    await safe_edit(
        callback,
        my_listings_text(page, pages, total),
        _my_listings_keyboard(accounts, page, pages),
    )


@router.callback_query(F.data == "menu:listings")
async def menu_listings(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await _render_my_listings(callback, user, session, 1)


@router.callback_query(F.data.startswith("mylist:page:"))
async def mylist_page(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    try:
        page = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        page = 1
    await callback.answer()
    await _render_my_listings(callback, user, session, page)


async def _get_my_account(session: AsyncSession, user: User, account_id: int) -> Account | None:
    return await session.scalar(
        select(Account).where(Account.id == account_id, Account.seller_id == user.id)
    )


@router.callback_query(F.data.startswith("mylist:view:"))
async def mylist_view(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    try:
        account_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri e'lon.", show_alert=True)
        return
    account = await _get_my_account(session, user, account_id)
    if account is None:
        await callback.answer("E'lon topilmadi.", show_alert=True)
        return
    await callback.answer()
    await safe_edit(callback, my_listing_detail_text(account), mylist_account_keyboard(account.id, account.status))


@router.callback_query(F.data.startswith("mylist:deactivate:"))
async def mylist_deactivate(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    try:
        account_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri e'lon.", show_alert=True)
        return
    account = await _get_my_account(session, user, account_id)
    if account is None:
        await callback.answer("E'lon topilmadi.", show_alert=True)
        return
    if account.status in {"RESERVED", "SOLD"}:
        await callback.answer("Faol savdodagi yoki sotilgan e'lonni o'chirib bo'lmaydi.", show_alert=True)
        return
    account.status = "INACTIVE"
    await session.commit()
    await callback.answer("⏸ E'lon faoliyatsiz holatga o'tkazildi.")
    await safe_edit(callback, my_listing_detail_text(account), mylist_account_keyboard(account.id, account.status))


@router.callback_query(F.data.startswith("mylist:activate:"))
async def mylist_activate(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    try:
        account_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri e'lon.", show_alert=True)
        return
    account = await _get_my_account(session, user, account_id)
    if account is None:
        await callback.answer("E'lon topilmadi.", show_alert=True)
        return
    if account.status in {"RESERVED", "SOLD", "BLOCKED"}:
        await callback.answer("Bu e'lonni qayta faollashtirib bo'lmaydi.", show_alert=True)
        return
    account.status = "ACTIVE"
    await session.commit()
    await callback.answer("▶️ E'lon qayta faollashtirildi.")
    await safe_edit(callback, my_listing_detail_text(account), mylist_account_keyboard(account.id, account.status))


def _history_keyboard(transactions, page: int, pages: int):
    builder = InlineKeyboardBuilder()
    for tx in transactions:
        builder.button(
            text=f"📜 {tx.code} · {money(tx.amount)}",
            callback_data=f"txn:view:{tx.id}",
        )
    builder.adjust(1)
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"history:page:{page - 1}"))
    if page < pages:
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"history:page:{page + 1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu:home"))
    return builder.as_markup()


async def _render_history(callback: CallbackQuery, user: User, session: AsyncSession, page: int) -> None:
    condition = (Transaction.buyer_id == user.id) | (Transaction.seller_id == user.id)
    total = await session.scalar(select(func.count(Transaction.id)).where(condition)) or 0
    pages = total_pages(total, HISTORY_PER_PAGE)
    page = clamp_page(page, pages)
    transactions = (
        await session.scalars(
            select(Transaction)
            .where(condition)
            .order_by(Transaction.created_at.desc())
            .offset((page - 1) * HISTORY_PER_PAGE)
            .limit(HISTORY_PER_PAGE)
        )
    ).all()
    if not transactions:
        builder = InlineKeyboardBuilder()
        builder.button(text="🛍 Akkaunt sotib olish", callback_data="menu:buy")
        builder.button(text="🏠 Asosiy menyu", callback_data="menu:home")
        builder.adjust(1)
        await safe_edit(
            callback,
            "📜 <b>SAVDO TARIXI</b>\n\nSizda hali savdolar yo'q.",
            builder.as_markup(),
        )
        return
    lines = [history_text(page, pages), ""]
    for tx in transactions:
        lines.append(history_item_line(tx, user.id))
        lines.append("")
    await safe_edit(callback, "\n".join(lines), _history_keyboard(transactions, page, pages))


@router.callback_query(F.data == "menu:history")
async def menu_history(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await _render_history(callback, user, session, 1)


@router.callback_query(F.data.startswith("history:page:"))
async def history_page(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    try:
        page = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        page = 1
    await callback.answer()
    await _render_history(callback, user, session, page)


def _payments_keyboard(page: int, pages: int):
    return pagination_keyboard("payments:page", page, pages)


async def _render_payments(callback: CallbackQuery, user: User, session: AsyncSession, page: int) -> None:
    total = (
        await session.scalar(select(func.count(Payment.id)).where(Payment.user_id == user.id)) or 0
    )
    pages = total_pages(total, PAYMENTS_PER_PAGE)
    page = clamp_page(page, pages)
    payments = (
        await session.scalars(
            select(Payment)
            .where(Payment.user_id == user.id)
            .order_by(Payment.created_at.desc())
            .offset((page - 1) * PAYMENTS_PER_PAGE)
            .limit(PAYMENTS_PER_PAGE)
        )
    ).all()
    if not payments:
        builder = InlineKeyboardBuilder()
        builder.button(text="🛍 Akkaunt sotib olish", callback_data="menu:buy")
        builder.button(text="🏠 Asosiy menyu", callback_data="menu:home")
        builder.adjust(1)
        await safe_edit(
            callback,
            "💳 <b>TO'LOVLARIM</b>\n\nSizda hali to'lovlar yo'q.",
            builder.as_markup(),
        )
        return
    lines = [payments_text(page, pages), ""]
    for payment in payments:
        lines.append(payment_line(payment))
        lines.append("")
    await safe_edit(callback, "\n".join(lines), _payments_keyboard(page, pages))


@router.callback_query(F.data == "menu:payments")
async def menu_payments(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await _render_payments(callback, user, session, 1)


@router.callback_query(F.data.startswith("payments:page:"))
async def payments_page(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    try:
        page = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        page = 1
    await callback.answer()
    await _render_payments(callback, user, session, page)


@router.callback_query(F.data == "menu:support")
async def menu_support(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    support_contact = await get_setting(session, "support_contact", "@support")
    await callback.answer()
    await safe_edit(callback, support_text(support_contact), support_keyboard())
