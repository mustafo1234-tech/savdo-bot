from __future__ import annotations

import logging
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_config
from bot.database.models import Dispute, Payment, Review, Transaction, User
from bot.keyboards.inline import (
    cancel_keyboard,
    click_payment_keyboard,
    deal_paid_buyer_keyboard,
    deal_paid_seller_keyboard,
    dispute_evidence_keyboard,
    review_comment_keyboard,
    review_keyboard,
)
from bot.services.deals import (
    cancel_pending_transaction,
    complete_transaction,
    generate_dispute_code,
    generate_payment_uid,
    load_transaction,
    quantize_money,
    user_profile_url,
    utcnow,
)
from bot.services.notifications import add_notification, send_user_message
from bot.services.payments import build_click_payment_url
from bot.states import DisputeStates, ReviewStates
from bot.texts import (
    DEAL_ALREADY_PAID_TEXT,
    DEAL_CANCELLED_TEXT,
    DISPUTE_EVIDENCE_PROMPT,
    DISPUTE_EVIDENCE_SAVED,
    INSUFFICIENT_BALANCE_TEXT,
    PAYMENT_CHECK_PENDING_TEXT,
    click_payment_text,
    deal_paid_buyer_text,
    deal_paid_seller_text,
    deal_success_buyer_text,
    deal_success_seller_text,
    dispute_opened_buyer_text,
    dispute_opened_seller_text,
    review_success_text,
    transaction_detail_text,
)
from bot.utils.formatting import h, money, user_contact
from bot.utils.telegram import safe_edit

logger = logging.getLogger(__name__)
router = Router(name="deals")


async def _load_tx(session: AsyncSession, tx_id: int, lock: bool = False) -> Transaction | None:
    stmt = select(Transaction).where(Transaction.id == tx_id)
    if lock:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


def _is_participant(tx: Transaction, user: User) -> bool:
    return user.id in {tx.buyer_id, tx.seller_id}


@router.callback_query(F.data.startswith("deal:pay_balance:"))
async def pay_balance(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
) -> None:
    try:
        tx_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri tranzaksiya.", show_alert=True)
        return
    tx = await _load_tx(session, tx_id, lock=True)
    if tx is None or tx.buyer_id != user.id:
        await callback.answer("Tranzaksiya topilmadi.", show_alert=True)
        return
    if tx.status in {"VERIFYING", "SUCCESS", "DISPUTE"}:
        await callback.answer("To'lov allaqachon qilingan.", show_alert=True)
        return
    if tx.status != "PENDING":
        await callback.answer("Bu savdo bo'yicha to'lov qilib bo'lmaydi.", show_alert=True)
        return

    buyer = await session.scalar(select(User).where(User.id == user.id).with_for_update())
    if buyer is None:
        await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return
    if Decimal(buyer.balance) < Decimal(tx.amount):
        await callback.answer(INSUFFICIENT_BALANCE_TEXT, show_alert=True)
        return

    old_payments = await session.scalars(
        select(Payment).where(
            Payment.transaction_id == tx.id,
            Payment.status.in_(("CREATED", "PENDING")),
        )
    )
    for payment in old_payments:
        payment.status = "FAILED"

    buyer.balance = quantize_money(Decimal(buyer.balance) - Decimal(tx.amount))
    payment = Payment(
        payment_uid=generate_payment_uid(),
        transaction_id=tx.id,
        user_id=buyer.id,
        provider="balance",
        amount=tx.amount,
        status="PAID",
        paid_at=utcnow(),
        payload={"source": "internal_balance"},
    )
    session.add(payment)
    tx.status = "VERIFYING"

    add_notification(session, tx.buyer_id, "To'lov qilindi", f"{tx.code}: balansdan to'lov amalga oshirildi.")
    add_notification(session, tx.seller_id, "Xaridor to'lov qildi", f"{tx.code}: akkauntni topshirishingiz mumkin.")
    await session.commit()

    await callback.answer("✅ To'lov tasdiqlandi")
    await safe_edit(
        callback,
        deal_paid_buyer_text(tx, tx.seller),
        deal_paid_buyer_keyboard(tx.id, user_profile_url(tx.seller)),
    )
    await send_user_message(
        callback.bot,
        tx.seller.telegram_id,
        deal_paid_seller_text(tx, tx.buyer),
        deal_paid_seller_keyboard(tx.id, user_profile_url(tx.buyer)),
    )
    config = get_config()
    await send_user_message(
        callback.bot,
        config.owner_id,
        "💳 <b>Balans orqali to'lov</b>\n\n"
        f"📜 <code>{h(tx.code)}</code>\n"
        f"💵 {money(tx.amount)}\n"
        f"💸 Komissiya: {money(tx.commission_amount)}\n"
        f"🛒 {user_contact(tx.buyer)} → 💰 {user_contact(tx.seller)}",
    )


@router.callback_query(F.data.startswith("deal:pay_click:"))
async def pay_click(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
) -> None:
    try:
        tx_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri tranzaksiya.", show_alert=True)
        return
    config = get_config()
    if not config.click_enabled:
        await callback.answer("Click hozircha sozlanmagan. Balansdan to'lang.", show_alert=True)
        return

    tx = await _load_tx(session, tx_id, lock=True)
    if tx is None or tx.buyer_id != user.id:
        await callback.answer("Tranzaksiya topilmadi.", show_alert=True)
        return
    if tx.status in {"VERIFYING", "SUCCESS", "DISPUTE"}:
        await callback.answer(DEAL_ALREADY_PAID_TEXT, show_alert=True)
        return
    if tx.status != "PENDING":
        await callback.answer("Bu savdo bo'yicha to'lov qilib bo'lmaydi.", show_alert=True)
        return

    payment = await session.scalar(
        select(Payment).where(
            Payment.transaction_id == tx.id,
            Payment.provider == "click",
            Payment.status.in_(("CREATED", "PENDING")),
        )
    )
    if payment is None:
        payment = Payment(
            payment_uid=generate_payment_uid(),
            transaction_id=tx.id,
            user_id=tx.buyer_id,
            provider="click",
            amount=tx.amount,
            status="CREATED",
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)

    pay_url = build_click_payment_url(config, Decimal(tx.amount), payment.payment_uid)
    await callback.answer()
    await safe_edit(callback, click_payment_text(tx), click_payment_keyboard(tx.id, pay_url))


@router.callback_query(F.data.startswith("deal:check:"))
async def check_payment(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    try:
        tx_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri tranzaksiya.", show_alert=True)
        return
    tx = await _load_tx(session, tx_id)
    if tx is None or not _is_participant(tx, user):
        await callback.answer("Tranzaksiya topilmadi.", show_alert=True)
        return
    if tx.status in {"VERIFYING", "SUCCESS", "DISPUTE"}:
        await callback.answer("✅ To'lov tasdiqlangan.", show_alert=True)
        return
    if tx.status == "CANCELLED":
        await callback.answer("Savdo bekor qilingan.", show_alert=True)
        return
    await callback.answer(PAYMENT_CHECK_PENDING_TEXT, show_alert=True)


@router.callback_query(F.data.startswith("deal:cancel:"))
async def cancel_deal(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    try:
        tx_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri tranzaksiya.", show_alert=True)
        return
    tx = await _load_tx(session, tx_id, lock=True)
    if tx is None or not _is_participant(tx, user):
        await callback.answer("Tranzaksiya topilmadi.", show_alert=True)
        return
    if tx.status != "PENDING":
        await callback.answer(DEAL_ALREADY_PAID_TEXT, show_alert=True)
        return

    await cancel_pending_transaction(session, tx)
    other_id = tx.seller_id if user.id == tx.buyer_id else tx.buyer_id
    add_notification(session, other_id, "Savdo bekor qilindi", f"{tx.code} tranzaksiyasi bekor qilindi.")
    await session.commit()

    await callback.answer("Savdo bekor qilindi")
    await safe_edit(callback, DEAL_CANCELLED_TEXT, _home_keyboard())
    other = tx.seller if user.id == tx.buyer_id else tx.buyer
    await send_user_message(
        callback.bot,
        other.telegram_id,
        "❌ <b>SAVDO BEKOR QILINDI</b>\n\n"
        f"📜 Tranzaksiya: <code>{h(tx.code)}</code>\n"
        f"📦 #{h(tx.account.public_id)} — {h(tx.account.account_name)}\n\n"
        "E'lon yana faol holatga qaytarildi.",
    )


@router.callback_query(F.data.startswith("deal:confirm:"))
async def confirm_deal(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    try:
        tx_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri tranzaksiya.", show_alert=True)
        return
    tx = await _load_tx(session, tx_id, lock=True)
    if tx is None or tx.buyer_id != user.id:
        await callback.answer("Tranzaksiya topilmadi.", show_alert=True)
        return
    if tx.status == "SUCCESS":
        await callback.answer("Savdo allaqachon yakunlangan.", show_alert=True)
        return
    if tx.status == "DISPUTE":
        await callback.answer("Nizo ochilgan. Admin ko'rib chiqmoqda.", show_alert=True)
        return
    if tx.status not in {"VERIFYING", "PAID"}:
        await callback.answer("To'lov hali tasdiqlanmagan.", show_alert=True)
        return

    await complete_transaction(session, tx)
    add_notification(session, tx.seller_id, "Savdo yakunlandi", f"{tx.code}: pul balansingizga qo'shildi.")
    add_notification(session, tx.buyer_id, "Savdo yakunlandi", f"{tx.code}: xarid muvaffaqiyatli yakunlandi.")
    await session.commit()

    await callback.answer("✅ Savdo yakunlandi")
    await safe_edit(callback, deal_success_buyer_text(tx), review_keyboard(tx.id))
    await send_user_message(
        callback.bot,
        tx.seller.telegram_id,
        deal_success_seller_text(tx),
        review_keyboard(tx.id),
    )
    config = get_config()
    await send_user_message(
        callback.bot,
        config.owner_id,
        "✅ <b>Savdo yakunlandi</b>\n\n"
        f"📜 <code>{h(tx.code)}</code>\n"
        f"💵 {money(tx.amount)}\n"
        f"💸 Komissiya: {money(tx.commission_amount)}\n"
        f"💰 Sotuvchiga: {money(tx.seller_amount)}",
    )


@router.callback_query(F.data.startswith("deal:problem:"))
async def problem_start(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    try:
        tx_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri tranzaksiya.", show_alert=True)
        return
    tx = await _load_tx(session, tx_id)
    if tx is None or tx.buyer_id != user.id:
        await callback.answer("Tranzaksiya topilmadi.", show_alert=True)
        return
    if tx.status == "DISPUTE":
        await callback.answer("Nizo allaqachon ochilgan.", show_alert=True)
        return
    if tx.status == "SUCCESS":
        await callback.answer("Savdo yakunlangan. Nizo ochib bo'lmaydi.", show_alert=True)
        return
    if tx.status not in {"PAID", "VERIFYING"}:
        await callback.answer("Avval to'lovni yakunlang.", show_alert=True)
        return

    await state.set_state(DisputeStates.reason)
    await state.update_data(dispute_tx_id=tx.id)
    await callback.answer()
    await safe_edit(
        callback,
        "⚠️ <b>MUAMMO HAQIDA XABAR BERISH</b>\n\n"
        "Muammoni qisqacha va aniq yozing. Masalan: akkaunt ID boshqa, "
        "daraja e'londagidan farq qiladi, akkaunt topshirilmadi.\n\n"
        "Keyingi qadamda dalil (skrinshot) yuborishingiz mumkin.",
        cancel_keyboard(),
    )


@router.message(DisputeStates.reason, F.text)
async def problem_reason(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    data = await state.get_data()
    tx_id = data.get("dispute_tx_id")
    reason = (message.text or "").strip()
    if not tx_id:
        await state.clear()
        await message.answer("Tranzaksiya topilmadi. Qaytadan urinib ko'ring.")
        return
    if not 10 <= len(reason) <= 1000:
        await message.answer("⚠️ Muammo tavsifi 10 tadan 1000 tagacha belgidan iborat bo'lishi kerak.")
        return

    tx = await _load_tx(session, int(tx_id), lock=True)
    if tx is None or tx.buyer_id != user.id:
        await state.clear()
        await message.answer("Tranzaksiya topilmadi.")
        return
    if tx.status == "DISPUTE":
        await state.clear()
        await message.answer("Nizo allaqachon ochilgan.")
        return
    if tx.status not in {"PAID", "VERIFYING"}:
        await state.clear()
        await message.answer("Bu tranzaksiya uchun nizo ochib bo'lmaydi.")
        return

    dispute = Dispute(
        code=generate_dispute_code(),
        transaction_id=tx.id,
        opened_by=tx.buyer_id,
        reason=reason,
        evidence=[],
        status="OPEN",
    )
    session.add(dispute)
    tx.status = "DISPUTE"
    add_notification(session, tx.seller_id, "Nizo ochildi", f"{tx.code}: xaridor shikoyat qildi.")
    add_notification(session, tx.buyer_id, "Nizo ochildi", f"{tx.code}: shikoyatingiz qabul qilindi.")
    await session.commit()
    await session.refresh(dispute)

    await state.update_data(dispute_id=dispute.id)
    await state.set_state(DisputeStates.evidence)

    await message.answer(
        dispute_opened_buyer_text(dispute, tx),
        reply_markup=dispute_evidence_keyboard(dispute.id, user_profile_url(tx.seller)),
    )
    await message.answer(DISPUTE_EVIDENCE_PROMPT, reply_markup=dispute_evidence_keyboard(dispute.id))
    await send_user_message(
        message.bot,
        tx.seller.telegram_id,
        dispute_opened_seller_text(dispute, tx),
        dispute_evidence_keyboard(dispute.id, user_profile_url(tx.buyer)),
    )
    config = get_config()
    await send_user_message(
        message.bot,
        config.owner_id,
        "⚠️ <b>YANGI NIZO</b>\n\n"
        f"🆔 <code>{h(dispute.code)}</code>\n"
        f"📜 <code>{h(tx.code)}</code>\n"
        f"📦 #{h(tx.account.public_id)}\n"
        f"👤 Xaridor: {user_contact(tx.buyer)}\n"
        f"👤 Sotuvchi: {user_contact(tx.seller)}\n"
        f"📝 Sabab: {h(reason)}\n\n"
        "Admin panel → Shikoyatlar bo'limida ko'rib chiqing.",
    )


async def _dispute_for_user(
    session: AsyncSession,
    dispute_id: int,
    user: User,
) -> tuple[Dispute | None, Transaction | None]:
    dispute = await session.get(Dispute, dispute_id)
    if dispute is None:
        return None, None
    tx = await load_transaction(session, dispute.transaction_id)
    if tx is None or not _is_participant(tx, user):
        return None, None
    return dispute, tx


@router.callback_query(F.data.startswith("deal:evidence:"))
async def evidence_start(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    try:
        dispute_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri nizo.", show_alert=True)
        return
    dispute, _ = await _dispute_for_user(session, dispute_id, user)
    if dispute is None:
        await callback.answer("Nizo topilmadi.", show_alert=True)
        return
    if dispute.status != "OPEN":
        await callback.answer("Bu nizo allaqachon hal qilingan.", show_alert=True)
        return
    await state.set_state(DisputeStates.evidence)
    await state.update_data(dispute_id=dispute.id)
    await callback.answer()
    await safe_edit(callback, DISPUTE_EVIDENCE_PROMPT, dispute_evidence_keyboard(dispute.id))


@router.message(DisputeStates.evidence, F.photo | F.document)
async def evidence_media(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    data = await state.get_data()
    dispute_id = data.get("dispute_id")
    if not dispute_id:
        await state.clear()
        return
    dispute, _ = await _dispute_for_user(session, int(dispute_id), user)
    if dispute is None or dispute.status != "OPEN":
        await state.clear()
        await message.answer("Nizo topilmadi yoki yopilgan.")
        return
    evidence = list(dispute.evidence or [])
    if len(evidence) >= 20:
        await message.answer("⚠️ Dalillar soni yetarli (20 ta). «Dalillarni yuborish» tugmasini bosing.")
        return
    if message.photo:
        evidence.append(
            {"type": "photo", "file_id": message.photo[-1].file_id, "caption": message.caption or ""}
        )
    elif message.document:
        evidence.append(
            {"type": "document", "file_id": message.document.file_id, "caption": message.caption or ""}
        )
    dispute.evidence = evidence
    await session.commit()
    await message.answer(
        f"✅ Dalil qabul qilindi ({len(evidence)}/20). Yana yuborishingiz yoki yakunlashingiz mumkin.",
        reply_markup=dispute_evidence_keyboard(dispute.id),
    )


@router.message(DisputeStates.evidence, F.text)
async def evidence_text(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    data = await state.get_data()
    dispute_id = data.get("dispute_id")
    if not dispute_id:
        await state.clear()
        return
    text = (message.text or "").strip()
    if not 2 <= len(text) <= 1000:
        await message.answer("⚠️ Dalil matni 2 tadan 1000 tagacha belgidan iborat bo'lishi kerak.")
        return
    dispute, _ = await _dispute_for_user(session, int(dispute_id), user)
    if dispute is None or dispute.status != "OPEN":
        await state.clear()
        await message.answer("Nizo topilmadi yoki yopilgan.")
        return
    evidence = list(dispute.evidence or [])
    if len(evidence) >= 20:
        await message.answer("⚠️ Dalillar soni yetarli (20 ta). «Dalillarni yuborish» tugmasini bosing.")
        return
    evidence.append({"type": "text", "text": text})
    dispute.evidence = evidence
    await session.commit()
    await message.answer(
        f"✅ Dalil qabul qilindi ({len(evidence)}/20).",
        reply_markup=dispute_evidence_keyboard(dispute.id),
    )


@router.callback_query(F.data.startswith("deal:evidence_done:"))
async def evidence_done(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    try:
        dispute_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri nizo.", show_alert=True)
        return
    dispute, _ = await _dispute_for_user(session, dispute_id, user)
    if dispute is None:
        await callback.answer("Nizo topilmadi.", show_alert=True)
        return
    await state.clear()
    await callback.answer("Yuborildi")
    await safe_edit(callback, DISPUTE_EVIDENCE_SAVED, _home_keyboard())


async def _save_review(
    session: AsyncSession,
    tx: Transaction,
    author: User,
    rating: int,
    comment: str | None,
    bot=None,
) -> str | None:
    if tx.status != "SUCCESS":
        return "Faqat yakunlangan savdoni baholash mumkin."
    if not _is_participant(tx, author):
        return "Siz bu savdo ishtirokchisi emassiz."
    existing = await session.scalar(
        select(Review.id).where(
            Review.transaction_id == tx.id,
            Review.author_id == author.id,
        )
    )
    if existing is not None:
        return "Siz bu savdoni allaqachon baholagansiz."
    if not 1 <= rating <= 5:
        return "Baho 1 dan 5 gacha bo'lishi kerak."

    target_id = tx.seller_id if author.id == tx.buyer_id else tx.buyer_id
    target = await session.get(User, target_id)
    if target is None:
        return "Foydalanuvchi topilmadi."
    session.add(
        Review(
            transaction_id=tx.id,
            author_id=author.id,
            target_id=target_id,
            rating=rating,
            comment=comment,
        )
    )
    target.rating_sum += rating
    target.rating_count += 1
    add_notification(
        session,
        target_id,
        "Yangi baho",
        f"{tx.code} savdosi uchun sizga {rating}/5 baho berildi.",
    )
    await session.commit()
    if bot is not None:
        await send_user_message(
            bot,
            target.telegram_id,
            f"⭐ <b>Yangi baho!</b>\n\nSavdo: <code>{h(tx.code)}</code>\nBaho: {'⭐' * rating} ({rating}/5)",
        )
    return None


@router.callback_query(F.data.startswith("deal:rate:"))
async def rate_start(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    parts = (callback.data or "").split(":")
    try:
        tx_id = int(parts[2])
        rating = int(parts[3])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri baho.", show_alert=True)
        return
    if not 1 <= rating <= 5:
        await callback.answer("Baho 1-5 oralig'ida bo'lishi kerak.", show_alert=True)
        return
    tx = await _load_tx(session, tx_id)
    if tx is None or not _is_participant(tx, user):
        await callback.answer("Tranzaksiya topilmadi.", show_alert=True)
        return
    if tx.status != "SUCCESS":
        await callback.answer("Faqat yakunlangan savdoni baholash mumkin.", show_alert=True)
        return
    existing = await session.scalar(
        select(Review.id).where(Review.transaction_id == tx.id, Review.author_id == user.id)
    )
    if existing is not None:
        await callback.answer("Siz allaqachon baholagansiz.", show_alert=True)
        return

    await state.set_state(ReviewStates.comment)
    await state.update_data(review_tx_id=tx.id, review_rating=rating)
    await callback.answer()
    await safe_edit(
        callback,
        f"⭐ <b>BAHO: {'⭐' * rating} ({rating}/5)</b>\n\n"
        "Qo'shimcha izoh yozishingiz mumkin (ixtiyoriy).",
        review_comment_keyboard(tx.id, rating),
    )


@router.message(ReviewStates.comment, F.text)
async def rate_comment(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    data = await state.get_data()
    tx_id = data.get("review_tx_id")
    rating = int(data.get("review_rating") or 0)
    comment = (message.text or "").strip()
    if not tx_id:
        await state.clear()
        return
    if len(comment) > 500:
        await message.answer("⚠️ Izoh 500 belgidan oshmasligi kerak.")
        return
    tx = await _load_tx(session, int(tx_id))
    if tx is None:
        await state.clear()
        await message.answer("Tranzaksiya topilmadi.")
        return
    error = await _save_review(session, tx, user, rating, comment or None, message.bot)
    await state.clear()
    if error:
        await message.answer(f"⚠️ {h(error)}")
        return
    await message.answer(review_success_text(rating), reply_markup=_home_keyboard())


@router.callback_query(F.data.startswith("deal:rate_skip:"))
async def rate_skip(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    parts = (callback.data or "").split(":")
    try:
        tx_id = int(parts[2])
        rating = int(parts[3])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri baho.", show_alert=True)
        return
    tx = await _load_tx(session, tx_id)
    if tx is None:
        await callback.answer("Tranzaksiya topilmadi.", show_alert=True)
        return
    error = await _save_review(session, tx, user, rating, None, callback.bot)
    await state.clear()
    if error:
        await callback.answer(error, show_alert=True)
        return
    await callback.answer("Baho yuborildi")
    await safe_edit(callback, review_success_text(rating), _home_keyboard())


def _home_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Asosiy menyu", callback_data="menu:home")
    return builder.as_markup()


def _transaction_keyboard(tx: Transaction, user: User, has_review: bool):
    builder = InlineKeyboardBuilder()
    config = get_config()
    is_buyer = tx.buyer_id == user.id
    other = tx.seller if is_buyer else tx.buyer
    other_url = user_profile_url(other)

    if tx.status == "PENDING" and is_buyer:
        if config.click_enabled:
            builder.button(text="💳 Click orqali to'lash", callback_data=f"deal:pay_click:{tx.id}")
        builder.button(text="💰 Balansdan to'lash", callback_data=f"deal:pay_balance:{tx.id}")
        builder.button(text="❌ Savdoni bekor qilish", callback_data=f"deal:cancel:{tx.id}")
    elif tx.status == "PENDING":
        builder.button(text="❌ Savdoni bekor qilish", callback_data=f"deal:cancel:{tx.id}")
    elif tx.status in {"PAID", "VERIFYING"} and is_buyer:
        builder.button(text="✅ Akkauntni oldim", callback_data=f"deal:confirm:{tx.id}")
        builder.button(text="⚠️ Muammo bor", callback_data=f"deal:problem:{tx.id}")
        if other_url:
            builder.button(text="💬 Seller bilan bog'lanish", url=other_url)
    elif tx.status in {"PAID", "VERIFYING"} and other_url:
        builder.button(text="💬 Xaridor bilan bog'lanish", url=other_url)
    elif tx.status == "DISPUTE":
        if tx.dispute:
            builder.button(
                text="📸 Dalil qo'shish",
                callback_data=f"deal:evidence:{tx.dispute.id}",
            )
        if other_url:
            builder.button(text="💬 Ikkinchi tomon bilan bog'lanish", url=other_url)
    elif tx.status == "SUCCESS" and not has_review:
        for rating in range(1, 6):
            builder.button(text="⭐" * rating, callback_data=f"deal:rate:{tx.id}:{rating}")
    builder.button(text="🏠 Asosiy menyu", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data.startswith("txn:view:"))
async def transaction_view(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    try:
        tx_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri tranzaksiya.", show_alert=True)
        return
    await state.clear()
    tx = await _load_tx(session, tx_id)
    if tx is None or not _is_participant(tx, user):
        await callback.answer("Tranzaksiya topilmadi.", show_alert=True)
        return
    has_review = bool(
        await session.scalar(
            select(Review.id).where(Review.transaction_id == tx.id, Review.author_id == user.id)
        )
    )
    await callback.answer()
    await safe_edit(
        callback,
        transaction_detail_text(tx, user),
        _transaction_keyboard(tx, user, has_review),
    )

