from __future__ import annotations

import asyncio
import logging
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_config
from bot.constants import PAYOUT_METHODS, PROFILE_ACCEPTED
from bot.database.models import Account, Dispute, Payment, Transaction, User
from bot.filters.is_owner import IsOwner
from bot.keyboards.inline import (
    admin_account_keyboard,
    admin_back_keyboard,
    admin_dispute_keyboard,
    admin_panel_keyboard,
    admin_payment_keyboard,
    admin_settings_keyboard,
    admin_user_keyboard,
)
from bot.services.crypto import decrypt
from bot.services.deals import (
    cancel_pending_transaction,
    complete_transaction,
    load_transaction,
    quantize_money,
    utcnow,
)
from bot.services.notifications import add_notification, send_user_message
from bot.services.settings import get_bool_setting, get_setting, set_setting
from bot.states import AdminStates
from bot.texts import dispute_resolved_text
from bot.utils.formatting import (
    account_status,
    dispute_status,
    fmt_dt,
    h,
    money,
    num,
    payment_status,
    platform_name,
    rating_text,
    truncate,
    tx_status,
    user_contact,
    user_display,
)
from bot.utils.pagination import clamp_page, total_pages
from bot.utils.telegram import safe_edit

logger = logging.getLogger(__name__)
router = Router(name="admin")

PER_PAGE = 8


def _parse_page(data: str | None, index: int = 2) -> int:
    try:
        return int((data or "").split(":")[index])
    except (IndexError, ValueError):
        return 1


def _add_nav(builder: InlineKeyboardBuilder, prefix: str, page: int, pages: int) -> None:
    row: list[InlineKeyboardButton] = []
    if page > 1:
        row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"{prefix}:{page - 1}"))
    if page < pages:
        row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"{prefix}:{page + 1}"))
    if row:
        builder.row(*row)
    builder.row(InlineKeyboardButton(text="🔙 Admin panel", callback_data="adm:home"))


async def _panel_text(session: AsyncSession) -> str:
    users_count = await session.scalar(select(func.count(User.id))) or 0
    banned_count = await session.scalar(select(func.count(User.id)).where(User.is_banned.is_(True))) or 0
    active_accounts = (
        await session.scalar(select(func.count(Account.id)).where(Account.status == "ACTIVE")) or 0
    )
    all_accounts = await session.scalar(select(func.count(Account.id))) or 0
    tx_count = await session.scalar(select(func.count(Transaction.id))) or 0
    success_count = (
        await session.scalar(
            select(func.count(Transaction.id)).where(Transaction.status == "SUCCESS")
        )
        or 0
    )
    open_disputes = (
        await session.scalar(select(func.count(Dispute.id)).where(Dispute.status == "OPEN")) or 0
    )
    revenue = await session.scalar(
        select(func.coalesce(func.sum(Transaction.commission_amount), 0)).where(
            Transaction.status == "SUCCESS"
        )
    )
    return (
        "👑 <b>ADMIN PANEL</b>\n"
        "\n"
        f"👥 Foydalanuvchilar: <b>{users_count}</b> (🚫 {banned_count})\n"
        f"📦 E'lonlar: <b>{all_accounts}</b> (✅ faol: {active_accounts})\n"
        f"📜 Tranzaksiyalar: <b>{tx_count}</b> (✅ {success_count})\n"
        f"⚠️ Ochiq nizolar: <b>{open_disputes}</b>\n"
        f"💸 Platforma daromadi: <b>{money(revenue or 0)}</b>\n"
        "\n"
        "Kerakli bo'limni tanlang 👇"
    )


async def _settings_text(session: AsyncSession) -> str:
    commission = await get_setting(session, "commission_percent", "10")
    min_price = await get_setting(session, "min_price", "5000")
    maintenance = await get_bool_setting(session, "maintenance", False)
    support = await get_setting(session, "support_contact", "@support")
    auto = await get_bool_setting(session, "auto_approve", True)
    click_enabled = get_config().click_enabled
    return (
        "⚙️ <b>BOT SOZLAMALARI</b>\n"
        "\n"
        f"💸 Komissiya: <b>{h(commission)}%</b>\n"
        f"💰 Minimal narx: <b>{money(min_price)}</b>\n"
        f"📞 Yordam kontakti: <b>{h(support)}</b>\n"
        f"🛠 Texnik xizmat: <b>{'🔴 Yoqilgan' if maintenance else '🟢 O‘chirilgan'}</b>\n"
        f"🕓 E'lon moderatsiyasi: <b>{'🟢 Avtomatik tasdiqlash' if auto else '🟡 Admin tasdiqlaydi'}</b>\n"
        f"💳 Click: <b>{'✅ Sozlangan' if click_enabled else '❌ Sozlanmagan'}</b>\n"
    )


@router.message(Command("admin"), IsOwner())
async def admin_command(message: Message, session: AsyncSession) -> None:
    await message.answer(await _panel_text(session), reply_markup=admin_panel_keyboard())


@router.message(Command("admin"))
async def admin_command_denied(message: Message) -> None:
    await message.answer("⛔ Bu buyruq faqat bot egasi uchun.")


@router.callback_query(IsOwner(), F.data == "adm:home")
async def admin_home(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await safe_edit(callback, await _panel_text(session), admin_panel_keyboard())


@router.callback_query(IsOwner(), F.data == "adm:stats")
async def admin_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    users_count = await session.scalar(select(func.count(User.id))) or 0
    banned = await session.scalar(select(func.count(User.id)).where(User.is_banned.is_(True))) or 0
    accounts_total = await session.scalar(select(func.count(Account.id))) or 0
    accounts_active = (
        await session.scalar(select(func.count(Account.id)).where(Account.status == "ACTIVE")) or 0
    )
    accounts_sold = (
        await session.scalar(select(func.count(Account.id)).where(Account.status == "SOLD")) or 0
    )
    tx_total = await session.scalar(select(func.count(Transaction.id))) or 0
    tx_success = (
        await session.scalar(
            select(func.count(Transaction.id)).where(Transaction.status == "SUCCESS")
        )
        or 0
    )
    tx_pending = (
        await session.scalar(
            select(func.count(Transaction.id)).where(Transaction.status == "PENDING")
        )
        or 0
    )
    tx_disputes = (
        await session.scalar(
            select(func.count(Transaction.id)).where(Transaction.status == "DISPUTE")
        )
        or 0
    )
    payments_paid = (
        await session.scalar(
            select(func.count(Payment.id)).where(Payment.status == "PAID")
        )
        or 0
    )
    revenue = await session.scalar(
        select(func.coalesce(func.sum(Transaction.commission_amount), 0)).where(
            Transaction.status == "SUCCESS"
        )
    )
    turnover = await session.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.status == "SUCCESS"
        )
    )
    text = (
        "📊 <b>STATISTIKA</b>\n"
        "\n"
        f"👥 Foydalanuvchilar: <b>{users_count}</b> (🚫 {banned})\n"
        f"📦 E'lonlar: <b>{accounts_total}</b>\n"
        f"  ✅ Faol: {accounts_active}\n"
        f"  🤝 Sotilgan: {accounts_sold}\n"
        "\n"
        f"📜 Tranzaksiyalar: <b>{tx_total}</b>\n"
        f"  ⏳ Kutilmoqda: {tx_pending}\n"
        f"  ✅ Muvaffaqiyatli: {tx_success}\n"
        f"  ⚠️ Nizoda: {tx_disputes}\n"
        f"💳 To'langan paymentlar: {payments_paid}\n"
        "\n"
        f"💰 Savdo aylanmasi: <b>{money(turnover or 0)}</b>\n"
        f"💸 Platforma daromadi: <b>{money(revenue or 0)}</b>"
    )
    await callback.answer()
    await safe_edit(callback, text, admin_back_keyboard())


async def _render_users(callback: CallbackQuery, session: AsyncSession, page: int) -> None:
    total = await session.scalar(select(func.count(User.id))) or 0
    pages = total_pages(total, PER_PAGE)
    page = clamp_page(page, pages)
    users = (
        await session.scalars(
            select(User)
            .order_by(User.created_at.desc())
            .offset((page - 1) * PER_PAGE)
            .limit(PER_PAGE)
        )
    ).all()
    builder = InlineKeyboardBuilder()
    for user in users:
        icon = "🚫" if user.is_banned else "👤"
        builder.button(
            text=f"{icon} {truncate(user.full_name or 'Foydalanuvchi', 20)} | {user.telegram_id}",
            callback_data=f"adm:user:{user.id}",
        )
    builder.adjust(1)
    _add_nav(builder, "adm:users", page, pages)
    text = (
        "👥 <b>FOYDALANUVCHILAR</b>\n"
        "\n"
        f"Jami: <b>{total}</b> | Sahifa: <b>{page}/{pages}</b>\n\n"
        "Foydalanuvchini tanlang 👇"
    )
    await safe_edit(callback, text, builder.as_markup())


@router.callback_query(IsOwner(), F.data.startswith("adm:users:"))
async def admin_users(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await _render_users(callback, session, _parse_page(callback.data))


async def _render_user(callback: CallbackQuery, session: AsyncSession, user_id: int) -> None:
    user = await session.get(User, user_id)
    if user is None:
        await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return
    listings = await session.scalar(select(func.count(Account.id)).where(Account.seller_id == user.id)) or 0
    sold = (
        await session.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.seller_id == user.id, Transaction.status == "SUCCESS"
            )
        )
        or 0
    )
    bought = (
        await session.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.buyer_id == user.id, Transaction.status == "SUCCESS"
            )
        )
        or 0
    )
    if user.profile_consent == PROFILE_ACCEPTED:
        consent_label = "Ulashilgan"
    elif user.profile_consent:
        consent_label = "Yashirin"
    else:
        consent_label = "So'ralmagan"
    text = (
        "👤 <b>FOYDALANUVCHI</b>\n"
        "\n"
        f"🧑 Ism: <b>{h(user.full_name or '—')}</b>\n"
        f"📎 Username: {('@' + h(user.username)) if user.username else '—'}\n"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
        f"🗄 DB ID: <code>{user.id}</code>\n"
        f"💰 Balans: <b>{money(user.balance)}</b>\n"
        f"⭐ Reyting: {rating_text(user)}\n"
        f"📦 E'lonlari: {listings} | 🤝 Sotgan: {sold} | 🛒 Sotib olgan: {bought}\n"
        f"🚫 Ban: {'Ha' if user.is_banned else 'Yo‘q'}\n"
        f"📜 Qoidalar: {'Qabul qilgan' if user.rules_accepted else 'Qabul qilmagan'}\n"
        f"🔐 Profil roziligi: {consent_label}\n"
        f"📅 Ro'yxatdan o'tgan: {fmt_dt(user.created_at)}"
    )
    await safe_edit(callback, text, admin_user_keyboard(user.id, user.is_banned))


@router.callback_query(IsOwner(), F.data.startswith("adm:user:"))
async def admin_user(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await _render_user(callback, session, _parse_page(callback.data))


@router.callback_query(IsOwner(), F.data.startswith("adm:ban:"))
async def admin_ban(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    target = await session.get(User, _parse_page(callback.data))
    if target is None:
        await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return
    if target.id == user.id:
        await callback.answer("O'zingizni ban qila olmaysiz.", show_alert=True)
        return
    target.is_banned = True
    add_notification(session, target.id, "Ban", "Siz botdan banlandingiz.")
    await session.commit()
    await callback.answer("🚫 Ban qilindi")
    await send_user_message(
        callback.bot,
        target.telegram_id,
        "🚫 <b>Siz botdan banlandingiz.</b>\n\nMurojaat uchun admin bilan bog'laning.",
    )
    await _render_user(callback, session, target.id)


@router.callback_query(IsOwner(), F.data.startswith("adm:unban:"))
async def admin_unban(callback: CallbackQuery, session: AsyncSession) -> None:
    target = await session.get(User, _parse_page(callback.data))
    if target is None:
        await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return
    target.is_banned = False
    add_notification(session, target.id, "Ban olib tashlandi", "Sizning banningiz olib tashlandi.")
    await session.commit()
    await callback.answer("✅ Bandan chiqarildi")
    await send_user_message(
        callback.bot,
        target.telegram_id,
        "✅ <b>Ban olib tashlandi.</b>\n\nBotdan yana foydalanishingiz mumkin.",
    )
    await _render_user(callback, session, target.id)


async def _render_accounts(callback: CallbackQuery, session: AsyncSession, page: int) -> None:
    total = await session.scalar(select(func.count(Account.id))) or 0
    pages = total_pages(total, PER_PAGE)
    page = clamp_page(page, pages)
    accounts = (
        await session.scalars(
            select(Account)
            .order_by(Account.created_at.desc())
            .offset((page - 1) * PER_PAGE)
            .limit(PER_PAGE)
        )
    ).all()
    builder = InlineKeyboardBuilder()
    for account in accounts:
        builder.button(
            text=f"#{account.public_id} | {num(account.price)} | {account_status(account.status)}",
            callback_data=f"adm:acc:{account.id}",
        )
    builder.adjust(1)
    _add_nav(builder, "adm:accounts", page, pages)
    text = (
        "📦 <b>BARCHA E'LONLAR</b>\n"
        "\n"
        f"Jami: <b>{total}</b> | Sahifa: <b>{page}/{pages}</b>\n\n"
        "E'lonni tanlang 👇"
    )
    await safe_edit(callback, text, builder.as_markup())


@router.callback_query(IsOwner(), F.data.startswith("adm:accounts:"))
async def admin_accounts(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await _render_accounts(callback, session, _parse_page(callback.data))


async def _render_account(callback: CallbackQuery, session: AsyncSession, account_id: int) -> None:
    account = await session.get(Account, account_id)
    if account is None:
        await callback.answer("E'lon topilmadi.", show_alert=True)
        return
    seller = await session.get(User, account.seller_id)
    text = (
        f"📦 <b>E'LON #{h(account.public_id)}</b>\n"
        "\n"
        f"Platforma: {h(platform_name(account.platform))}\n"
        f"🏷 Nom: <b>{h(account.account_name)}</b>\n"
        f"🆔 Akkaunt ID: <code>{h(decrypt(account.account_identifier_encrypted))}</code>\n"
        f"🏆 Daraja: {h(account.level)}\n"
        f"💰 Narx: <b>{money(account.price)}</b>\n"
        f"📌 Holat: <b>{account_status(account.status)}</b>\n"
        f"🔐 Egalik tasdiqlangan: {'Ha' if account.ownership_confirmed else 'Yo‘q'}\n"
        f"🏦 To'lov usuli: {h(PAYOUT_METHODS.get(account.payout_method, account.payout_method))}\n"
        f"📞 Aloqa: {h(decrypt(account.contact_encrypted))}\n"
        f"👁 Ko'rishlar: {account.views}\n"
        f"🖼 Rasmlar: {len(account.images)}\n"
        f"📅 Yaratilgan: {fmt_dt(account.created_at)}\n"
        "\n"
        f"👤 Sotuvchi: {user_contact(seller) if seller else '—'}\n"
        "\n"
        f"🎁 <b>Narsalar:</b>\n{h(account.items)}\n\n"
        f"📝 <b>Tavsif:</b>\n{h(account.description)}"
    )
    await safe_edit(callback, text, admin_account_keyboard(account.id, account.status))


@router.callback_query(IsOwner(), F.data.startswith("adm:acc:"))
async def admin_account(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await _render_account(callback, session, _parse_page(callback.data))


@router.callback_query(IsOwner(), F.data.startswith("adm:acc_approve:"))
async def admin_account_approve(callback: CallbackQuery, session: AsyncSession) -> None:
    account = await session.get(Account, _parse_page(callback.data))
    if account is None:
        await callback.answer("E'lon topilmadi.", show_alert=True)
        return
    if account.status != "PENDING":
        await callback.answer("Bu e'lon tasdiqlashni talab qilmaydi.", show_alert=True)
        return
    account.status = "ACTIVE"
    seller = await session.get(User, account.seller_id)
    add_notification(session, account.seller_id, "E'lon tasdiqlandi", f"{account.public_id} e'loni faollashtirildi.")
    await session.commit()
    await callback.answer("✅ E'lon tasdiqlandi")
    if seller:
        await send_user_message(
            callback.bot,
            seller.telegram_id,
            f"✅ <b>E'loningiz tasdiqlandi!</b>\n\n📦 #{h(account.public_id)} — {h(account.account_name)}\n"
            "Endi xaridorlar uni ko'rishi mumkin.",
        )
    await _render_account(callback, session, account.id)


@router.callback_query(IsOwner(), F.data.startswith("adm:acc_block:"))
async def admin_account_block(callback: CallbackQuery, session: AsyncSession) -> None:
    account = await session.get(Account, _parse_page(callback.data))
    if account is None:
        await callback.answer("E'lon topilmadi.", show_alert=True)
        return
    if account.status in {"RESERVED", "SOLD"}:
        await callback.answer("Faol savdodagi yoki sotilgan e'lonni bloklab bo'lmaydi.", show_alert=True)
        return
    account.status = "BLOCKED"
    seller = await session.get(User, account.seller_id)
    add_notification(session, account.seller_id, "E'lon bloklandi", f"{account.public_id} e'loni bloklandi.")
    await session.commit()
    await callback.answer("🚫 E'lon bloklandi")
    if seller:
        await send_user_message(
            callback.bot,
            seller.telegram_id,
            f"🚫 <b>E'loningiz bloklandi.</b>\n\n📦 #{h(account.public_id)}\n"
            "Batafsil ma'lumot uchun admin bilan bog'laning.",
        )
    await _render_account(callback, session, account.id)


@router.callback_query(IsOwner(), F.data.startswith("adm:acc_unblock:"))
async def admin_account_unblock(callback: CallbackQuery, session: AsyncSession) -> None:
    account = await session.get(Account, _parse_page(callback.data))
    if account is None:
        await callback.answer("E'lon topilmadi.", show_alert=True)
        return
    if account.status != "BLOCKED":
        await callback.answer("Bu e'lon bloklanmagan.", show_alert=True)
        return
    account.status = "ACTIVE" if account.ownership_confirmed else "PENDING"
    seller = await session.get(User, account.seller_id)
    await session.commit()
    await callback.answer("✅ Blokdan chiqarildi")
    if seller:
        await send_user_message(
            callback.bot,
            seller.telegram_id,
            f"✅ <b>E'loningiz blokdan chiqarildi.</b>\n\n📦 #{h(account.public_id)}",
        )
    await _render_account(callback, session, account.id)


async def _render_payments(callback: CallbackQuery, session: AsyncSession, page: int) -> None:
    total = await session.scalar(select(func.count(Payment.id))) or 0
    pages = total_pages(total, PER_PAGE)
    page = clamp_page(page, pages)
    payments = (
        await session.scalars(
            select(Payment)
            .order_by(Payment.created_at.desc())
            .offset((page - 1) * PER_PAGE)
            .limit(PER_PAGE)
        )
    ).all()
    builder = InlineKeyboardBuilder()
    for payment in payments:
        builder.button(
            text=f"#{payment.id} | {payment.provider.upper()} | {num(payment.amount)} | {payment_status(payment.status)}",
            callback_data=f"adm:payment:{payment.id}",
        )
    builder.adjust(1)
    _add_nav(builder, "adm:payments", page, pages)
    text = (
        "💳 <b>TO'LOVLAR</b>\n"
        "\n"
        f"Jami: <b>{total}</b> | Sahifa: <b>{page}/{pages}</b>"
    )
    await safe_edit(callback, text, builder.as_markup())


@router.callback_query(IsOwner(), F.data.startswith("adm:payments:"))
async def admin_payments(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await _render_payments(callback, session, _parse_page(callback.data))


async def _render_payment(callback: CallbackQuery, session: AsyncSession, payment_id: int) -> None:
    payment = await session.get(Payment, payment_id)
    if payment is None:
        await callback.answer("To'lov topilmadi.", show_alert=True)
        return
    buyer = await session.get(User, payment.user_id)
    tx = await load_transaction(session, payment.transaction_id)
    text = (
        "💳 <b>TO'LOV TAFSILOTLARI</b>\n"
        "\n"
        f"🆔 UID: <code>{h(payment.payment_uid)}</code>\n"
        f"🏦 Provider: <b>{h(payment.provider.upper())}</b>\n"
        f"📌 Holat: <b>{payment_status(payment.status)}</b>\n"
        f"💵 Summa: <b>{money(payment.amount)}</b>\n"
        f"🔗 Provider tranzaksiya ID: <code>{h(payment.provider_trans_id or '—')}</code>\n"
        f"📅 Yaratilgan: {fmt_dt(payment.created_at)}\n"
        f"✅ To'langan: {fmt_dt(payment.paid_at)}\n"
        f"👤 Xaridor: {user_display(buyer) if buyer else '—'}\n"
        f"📜 Tranzaksiya: <code>{h(tx.code) if tx else '—'}</code>"
    )
    await safe_edit(callback, text, admin_payment_keyboard(payment.id, payment.status))


@router.callback_query(IsOwner(), F.data.startswith("adm:payment:"))
async def admin_payment(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await _render_payment(callback, session, _parse_page(callback.data))


@router.callback_query(IsOwner(), F.data.startswith("adm:refund_done:"))
async def admin_refund_done(callback: CallbackQuery, session: AsyncSession) -> None:
    payment = await session.get(Payment, _parse_page(callback.data))
    if payment is None:
        await callback.answer("To'lov topilmadi.", show_alert=True)
        return
    if payment.status != "REFUND_PENDING":
        await callback.answer("Bu to'lov qaytarish kutilayotgan holatda emas.", show_alert=True)
        return
    payment.status = "REFUNDED"
    add_notification(session, payment.user_id, "To'lov qaytarildi", f"{payment.payment_uid} qaytarildi.")
    await session.commit()
    await callback.answer("✅ Qaytarildi deb belgilandi")
    buyer = await session.get(User, payment.user_id)
    if buyer:
        await send_user_message(
            callback.bot,
            buyer.telegram_id,
            f"↩️ <b>To'lov qaytarildi</b>\n\n🆔 <code>{h(payment.payment_uid)}</code>\n"
            f"💵 {money(payment.amount)}",
        )
    await _render_payment(callback, session, payment.id)


async def _render_transactions(callback: CallbackQuery, session: AsyncSession, page: int) -> None:
    total = await session.scalar(select(func.count(Transaction.id))) or 0
    pages = total_pages(total, PER_PAGE)
    page = clamp_page(page, pages)
    transactions = (
        await session.scalars(
            select(Transaction)
            .order_by(Transaction.created_at.desc())
            .offset((page - 1) * PER_PAGE)
            .limit(PER_PAGE)
        )
    ).all()
    builder = InlineKeyboardBuilder()
    for tx in transactions:
        builder.button(
            text=f"{tx.code} | {money(tx.amount)} | {tx_status(tx.status)}",
            callback_data=f"adm:txn:{tx.id}",
        )
    builder.adjust(1)
    _add_nav(builder, "adm:transactions", page, pages)
    text = (
        "📜 <b>TRANZAKSIYALAR</b>\n"
        "\n"
        f"Jami: <b>{total}</b> | Sahifa: <b>{page}/{pages}</b>"
    )
    await safe_edit(callback, text, builder.as_markup())


@router.callback_query(IsOwner(), F.data.startswith("adm:transactions:"))
async def admin_transactions(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await _render_transactions(callback, session, _parse_page(callback.data))


def _tx_admin_keyboard(tx: Transaction):
    builder = InlineKeyboardBuilder()
    if tx.status == "PENDING":
        builder.button(text="❌ Savdoni bekor qilish", callback_data=f"adm:txn_cancel:{tx.id}")
    if tx.dispute:
        builder.button(text="⚠️ Nizoni ko'rish", callback_data=f"adm:dispute:{tx.dispute.id}")
    builder.button(text="🔙 Tranzaksiyalar", callback_data="adm:transactions:1")
    builder.adjust(1)
    return builder.as_markup()


async def _render_transaction(callback: CallbackQuery, session: AsyncSession, tx_id: int) -> None:
    tx = await session.get(Transaction, tx_id)
    if tx is None:
        await callback.answer("Tranzaksiya topilmadi.", show_alert=True)
        return
    text = (
        "📜 <b>TRANZAKSIYA</b>\n"
        "\n"
        f"🆔 Kod: <code>{h(tx.code)}</code>\n"
        f"📦 E'lon: #{h(tx.account.public_id)} — {h(tx.account.account_name)}\n"
        f"{h(platform_name(tx.account.platform))}\n"
        f"📌 Holat: <b>{tx_status(tx.status)}</b>\n"
        "\n"
        f"🛒 Xaridor: {user_contact(tx.buyer)}\n"
        f"💰 Sotuvchi: {user_contact(tx.seller)}\n"
        "\n"
        f"💵 Summa: <b>{money(tx.amount)}</b>\n"
        f"💸 Komissiya: {money(tx.commission_amount)} ({num(tx.commission_rate)}%)\n"
        f"💰 Sotuvchi oladi: {money(tx.seller_amount)}\n"
        f"📅 Yaratilgan: {fmt_dt(tx.created_at)}\n"
        f"✅ Yakunlangan: {fmt_dt(tx.completed_at)}"
    )
    await safe_edit(callback, text, _tx_admin_keyboard(tx))


@router.callback_query(IsOwner(), F.data.startswith("adm:txn:"))
async def admin_transaction(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await _render_transaction(callback, session, _parse_page(callback.data))


@router.callback_query(IsOwner(), F.data.startswith("adm:txn_cancel:"))
async def admin_txn_cancel(callback: CallbackQuery, session: AsyncSession) -> None:
    tx = await session.scalar(
        select(Transaction).where(Transaction.id == _parse_page(callback.data)).with_for_update()
    )
    if tx is None:
        await callback.answer("Tranzaksiya topilmadi.", show_alert=True)
        return
    if tx.status != "PENDING":
        await callback.answer("Faqat kutilayotgan tranzaksiyani bekor qilish mumkin.", show_alert=True)
        return
    await cancel_pending_transaction(session, tx)
    add_notification(session, tx.buyer_id, "Savdo bekor qilindi", f"{tx.code} admin tomonidan bekor qilindi.")
    add_notification(session, tx.seller_id, "Savdo bekor qilindi", f"{tx.code} admin tomonidan bekor qilindi.")
    await session.commit()
    await callback.answer("❌ Bekor qilindi")
    await send_user_message(
        callback.bot,
        tx.buyer.telegram_id,
        f"❌ <b>Savdo bekor qilindi</b>\n\n📜 <code>{h(tx.code)}</code>\nAdmin tomonidan bekor qilindi.",
    )
    await send_user_message(
        callback.bot,
        tx.seller.telegram_id,
        f"❌ <b>Savdo bekor qilindi</b>\n\n📜 <code>{h(tx.code)}</code>\nAdmin tomonidan bekor qilindi.",
    )
    await _render_transaction(callback, session, tx.id)


async def _render_disputes(callback: CallbackQuery, session: AsyncSession, page: int) -> None:
    total = await session.scalar(select(func.count(Dispute.id))) or 0
    pages = total_pages(total, PER_PAGE)
    page = clamp_page(page, pages)
    rows = (
        await session.execute(
            select(Dispute, Transaction.code)
            .join(Transaction, Transaction.id == Dispute.transaction_id)
            .order_by(Dispute.created_at.desc())
            .offset((page - 1) * PER_PAGE)
            .limit(PER_PAGE)
        )
    ).all()
    builder = InlineKeyboardBuilder()
    for dispute, _tx_code in rows:
        builder.button(
            text=f"{dispute.code} | {dispute_status(dispute.status)}",
            callback_data=f"adm:dispute:{dispute.id}",
        )
    builder.adjust(1)
    _add_nav(builder, "adm:disputes", page, pages)
    text = (
        "⚠️ <b>SHIKOYATLAR / NIZOLAR</b>\n"
        "\n"
        f"Jami: <b>{total}</b> | Sahifa: <b>{page}/{pages}</b>\n\n"
        "Nizoni tanlang 👇"
    )
    await safe_edit(callback, text, builder.as_markup())


@router.callback_query(IsOwner(), F.data.startswith("adm:disputes:"))
async def admin_disputes(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await _render_disputes(callback, session, _parse_page(callback.data))


def _dispute_text(dispute: Dispute, tx: Transaction) -> str:
    evidence = dispute.evidence or []
    text_items = [item for item in evidence if item.get("type") == "text"]
    photos = [item for item in evidence if item.get("type") in {"photo", "document"}]
    text = (
        "⚠️ <b>NIZO TAFSILOTLARI</b>\n"
        "\n"
        f"🆔 Nizo: <code>{h(dispute.code)}</code>\n"
        f"📌 Holat: <b>{dispute_status(dispute.status)}</b>\n"
        f"📜 Tranzaksiya: <code>{h(tx.code)}</code>\n"
        f"📦 E'lon: #{h(tx.account.public_id)} — {h(tx.account.account_name)}\n"
        "\n"
        f"🛒 Xaridor: {user_contact(tx.buyer)}\n"
        f"💰 Sotuvchi: {user_contact(tx.seller)}\n"
        "\n"
        f"💵 Summa: {money(tx.amount)}\n"
        f"📅 Ochilgan: {fmt_dt(dispute.created_at)}\n"
        f"📝 Sabab:\n{h(dispute.reason)}\n"
        "\n"
        f"📎 Dalillar: matn {len(text_items)} ta, fayl {len(photos)} ta"
    )
    if dispute.resolution_note:
        text += f"\n\n⚖️ Qaror izohi:\n{h(dispute.resolution_note)}"
    if text_items:
        text += "\n\n📝 <b>Matnli dalillar:</b>\n"
        for item in text_items[:10]:
            text += f"• {h(item.get('text', ''))}\n"
    return text


async def _render_dispute(
    callback: CallbackQuery,
    session: AsyncSession,
    dispute_id: int,
    *,
    send_evidence: bool = True,
) -> None:
    dispute = await session.get(Dispute, dispute_id)
    if dispute is None:
        await callback.answer("Nizo topilmadi.", show_alert=True)
        return
    tx = await load_transaction(session, dispute.transaction_id)
    if tx is None:
        await callback.answer("Tranzaksiya topilmadi.", show_alert=True)
        return
    keyboard = admin_dispute_keyboard(dispute.id) if dispute.status == "OPEN" else admin_back_keyboard(
        "adm:disputes:1", "🔙 Shikoyatlar"
    )
    await safe_edit(callback, _dispute_text(dispute, tx), keyboard)
    if not send_evidence:
        return
    for item in (dispute.evidence or []):
        if item.get("type") == "photo":
            try:
                await callback.bot.send_photo(
                    callback.from_user.id,
                    item.get("file_id"),
                    caption=item.get("caption") or None,
                )
            except Exception:  # noqa: BLE001
                logger.warning("Dalil rasmini yuborishda xatolik.")
        elif item.get("type") == "document":
            try:
                await callback.bot.send_document(
                    callback.from_user.id,
                    item.get("file_id"),
                    caption=item.get("caption") or None,
                )
            except Exception:  # noqa: BLE001
                logger.warning("Dalil faylini yuborishda xatolik.")


@router.callback_query(IsOwner(), F.data.startswith("adm:dispute:"))
async def admin_dispute(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await _render_dispute(callback, session, _parse_page(callback.data))


@router.callback_query(IsOwner(), F.data.startswith("adm:resolve_buyer:"))
async def admin_resolve_buyer(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
) -> None:
    dispute_id = _parse_page(callback.data)
    dispute = await session.scalar(
        select(Dispute).where(Dispute.id == dispute_id).with_for_update()
    )
    if dispute is None:
        await callback.answer("Nizo topilmadi.", show_alert=True)
        return
    if dispute.status != "OPEN":
        await callback.answer("Nizo allaqachon hal qilingan.", show_alert=True)
        return
    tx = await session.scalar(
        select(Transaction).where(Transaction.id == dispute.transaction_id).with_for_update()
    )
    if tx is None:
        await callback.answer("Tranzaksiya topilmadi.", show_alert=True)
        return

    payments = await session.scalars(
        select(Payment).where(Payment.transaction_id == tx.id, Payment.status == "PAID")
    )
    notes: list[str] = []
    for payment in payments:
        if payment.provider == "balance":
            tx.buyer.balance = quantize_money(Decimal(tx.buyer.balance) + Decimal(tx.amount))
            payment.status = "REFUNDED"
            notes.append("Balansga qaytarildi")
        elif payment.provider == "click":
            payment.status = "REFUND_PENDING"
            notes.append("Click to'lovini qo'lda qaytarish kerak")

    tx.status = "CANCELLED"
    tx.account.status = "ACTIVE"
    dispute.status = "RESOLVED_BUYER"
    dispute.resolved_by = user.id
    dispute.resolved_at = utcnow()
    dispute.resolution_note = (
        "Admin qarori: xaridor foydasiga. " + ("; ".join(notes) if notes else "To'lov qaytarildi.")
    )
    add_notification(session, tx.buyer_id, "Nizo hal qilindi", f"{dispute.code}: xaridor foydasiga.")
    add_notification(session, tx.seller_id, "Nizo hal qilindi", f"{dispute.code}: xaridor foydasiga.")
    await session.commit()

    await callback.answer("↩️ Xaridor foydasiga hal qilindi")
    await send_user_message(callback.bot, tx.buyer.telegram_id, dispute_resolved_text(dispute, tx))
    await send_user_message(callback.bot, tx.seller.telegram_id, dispute_resolved_text(dispute, tx))
    if "Click to'lovini qo'lda qaytarish kerak" in dispute.resolution_note:
        await callback.message.answer(
            "⚠️ <b>Diqqat!</b> Click to'lovi bo'yicha qaytarishni Click kabinetida qo'lda "
            "amalga oshiring. Admin panel → To'lovlar bo'limida holat "
            "«Qaytarish kutilmoqda» deb turadi."
        )
    await _render_dispute(callback, session, dispute.id, send_evidence=False)


@router.callback_query(IsOwner(), F.data.startswith("adm:resolve_seller:"))
async def admin_resolve_seller(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
) -> None:
    dispute_id = _parse_page(callback.data)
    dispute = await session.scalar(
        select(Dispute).where(Dispute.id == dispute_id).with_for_update()
    )
    if dispute is None:
        await callback.answer("Nizo topilmadi.", show_alert=True)
        return
    if dispute.status != "OPEN":
        await callback.answer("Nizo allaqachon hal qilingan.", show_alert=True)
        return
    tx = await session.scalar(
        select(Transaction).where(Transaction.id == dispute.transaction_id).with_for_update()
    )
    if tx is None:
        await callback.answer("Tranzaksiya topilmadi.", show_alert=True)
        return

    await complete_transaction(session, tx)
    dispute.status = "RESOLVED_SELLER"
    dispute.resolved_by = user.id
    dispute.resolved_at = utcnow()
    dispute.resolution_note = "Admin qarori: sotuvchi foydasiga. Savdo yakunlandi."
    add_notification(session, tx.buyer_id, "Nizo hal qilindi", f"{dispute.code}: sotuvchi foydasiga.")
    add_notification(session, tx.seller_id, "Nizo hal qilindi", f"{dispute.code}: sotuvchi foydasiga.")
    await session.commit()

    await callback.answer("✅ Sotuvchi foydasiga hal qilindi")
    await send_user_message(callback.bot, tx.buyer.telegram_id, dispute_resolved_text(dispute, tx))
    await send_user_message(callback.bot, tx.seller.telegram_id, dispute_resolved_text(dispute, tx))
    await _render_dispute(callback, session, dispute.id, send_evidence=False)


@router.callback_query(IsOwner(), F.data == "adm:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.broadcast)
    await callback.answer()
    await safe_edit(
        callback,
        "📢 <b>XABAR YUBORISH</b>\n\n"
        "Barcha banlanmagan foydalanuvchilarga yuboriladigan xabar matnini kiriting.\n\n"
        "⚠️ Xabar oddiy matn sifatida yuboriladi (HTML ishlamaydi).",
        admin_back_keyboard("adm:settings", "🔙 Sozlamalar"),
    )


@router.message(IsOwner(), AdminStates.broadcast, F.text)
async def admin_broadcast_send(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    text = (message.text or "").strip()
    if not 1 <= len(text) <= 3000:
        await message.answer("⚠️ Xabar 1 tadan 3000 tagacha belgidan iborat bo'lishi kerak.")
        return
    telegram_ids = (
        await session.scalars(select(User.telegram_id).where(User.is_banned.is_(False)))
    ).all()
    await state.clear()

    success = 0
    failed = 0
    for telegram_id in telegram_ids:
        try:
            await message.bot.send_message(
                telegram_id,
                "📢 Admin xabari\n\n" + text,
                parse_mode=None,
            )
            success += 1
        except Exception:  # noqa: BLE001
            failed += 1
        await asyncio.sleep(0.05)

    await message.answer(
        "📢 <b>Xabar yuborildi</b>\n\n"
        f"✅ Yetkazildi: <b>{success}</b>\n"
        f"❌ Xatolik: <b>{failed}</b>\n\n"
        + await _panel_text(session),
        reply_markup=admin_panel_keyboard(),
    )


@router.callback_query(IsOwner(), F.data == "adm:settings")
async def admin_settings(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await safe_edit(callback, await _settings_text(session), admin_settings_keyboard())


@router.callback_query(IsOwner(), F.data.startswith("adm:set:"))
async def admin_set_value_start(callback: CallbackQuery, state: FSMContext) -> None:
    key = (callback.data or "").split(":", 2)[2]
    prompts = {
        "commission_percent": "💸 <b>Yangi komissiya foizini kiriting</b>\n\n0 dan 50 gacha raqam. Masalan: 10",
        "min_price": "💰 <b>Yangi minimal narxni kiriting</b>\n\nFaqat raqam. Masalan: 5000",
        "support_contact": "📞 <b>Yangi yordam kontaktini kiriting</b>\n\nMasalan: @admin_username",
    }
    if key not in prompts:
        await callback.answer("Noma'lum sozlama.", show_alert=True)
        return
    await state.set_state(AdminStates.set_value)
    await state.update_data(setting_key=key)
    await callback.answer()
    await safe_edit(
        callback,
        prompts[key],
        admin_back_keyboard("adm:settings", "🔙 Sozlamalar"),
    )


@router.message(IsOwner(), AdminStates.set_value, F.text)
async def admin_set_value(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    key = data.get("setting_key")
    raw = (message.text or "").strip()
    if not key:
        await state.clear()
        await message.answer("Sozlama aniqlanmadi.", reply_markup=admin_panel_keyboard())
        return

    if key == "commission_percent":
        try:
            value = Decimal(raw.replace(",", "."))
        except (InvalidOperation, ValueError):
            await message.answer("⚠️ Komissiya foizini raqamda kiriting. Masalan: 10")
            return
        if value < 0 or value > 50:
            await message.answer("⚠️ Komissiya 0 dan 50 gacha bo'lishi kerak.")
            return
        value_str = str(int(value)) if value == value.to_integral_value() else str(value)
        await set_setting(session, key, value_str)
    elif key == "min_price":
        from bot.utils.formatting import parse_price

        value = parse_price(raw)
        if value is None or value <= 0 or value > Decimal(1000000000):
            await message.answer("⚠️ Minimal narxni to'g'ri raqamda kiriting.")
            return
        await set_setting(session, key, str(value))
    elif key == "support_contact":
        if not 3 <= len(raw) <= 200:
            await message.answer("⚠️ Kontakt 3 tadan 200 tagacha belgidan iborat bo'lishi kerak.")
            return
        await set_setting(session, key, raw)
    else:
        await state.clear()
        await message.answer("Noma'lum sozlama.", reply_markup=admin_panel_keyboard())
        return

    await session.commit()
    await state.clear()
    await message.answer(await _settings_text(session), reply_markup=admin_settings_keyboard())


@router.callback_query(IsOwner(), F.data == "adm:toggle_maintenance")
async def admin_toggle_maintenance(callback: CallbackQuery, session: AsyncSession) -> None:
    current = await get_bool_setting(session, "maintenance", False)
    await set_setting(session, "maintenance", "false" if current else "true")
    await session.commit()
    await callback.answer("🟢 O'chirildi" if current else "🔴 Yoqildi")
    await safe_edit(callback, await _settings_text(session), admin_settings_keyboard())


@router.callback_query(IsOwner(), F.data == "adm:toggle_autoapprove")
async def admin_toggle_autoapprove(callback: CallbackQuery, session: AsyncSession) -> None:
    current = await get_bool_setting(session, "auto_approve", True)
    new_value = not current
    await set_setting(session, "auto_approve", "true" if new_value else "false")
    if new_value:
        pending = (await session.scalars(select(Account).where(Account.status == "PENDING"))).all()
        for account in pending:
            account.status = "ACTIVE"
            add_notification(
                session,
                account.seller_id,
                "E'lon tasdiqlandi",
                f"{account.public_id} avtomatik faollashtirildi.",
            )
    await session.commit()
    await callback.answer("🟢 Avtomatik tasdiqlash" if new_value else "🟡 Admin tasdiqlaydi")
    await safe_edit(callback, await _settings_text(session), admin_settings_keyboard())


@router.callback_query(F.data.startswith("adm:"))
async def admin_denied(callback: CallbackQuery) -> None:
    await callback.answer("⛔ Ruxsat yo'q. Bu bo'lim faqat bot egasi uchun.", show_alert=True)
