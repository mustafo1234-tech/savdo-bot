from __future__ import annotations

import secrets
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constants import ACTIVE_TRANSACTION_STATUSES
from bot.database.models import Account, Payment, Transaction, User
from bot.keyboards.inline import deal_paid_buyer_keyboard, deal_paid_seller_keyboard
from bot.services.notifications import send_user_message
from bot.texts import deal_paid_buyer_text, deal_paid_seller_text


def utcnow() -> datetime:
    return datetime.now(UTC)


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def generate_transaction_code() -> str:
    stamp = utcnow().strftime("%y%m%d")
    return f"TX-{stamp}-{secrets.token_hex(3).upper()}"


def generate_payment_uid() -> str:
    return f"PAY-{secrets.token_hex(10).upper()}"


def generate_dispute_code() -> str:
    stamp = utcnow().strftime("%y%m%d")
    return f"DSP-{stamp}-{secrets.token_hex(3).upper()}"


def user_profile_url(user: User) -> str | None:
    if user.username:
        return f"https://t.me/{user.username}"
    return None


async def load_transaction(
    session: AsyncSession,
    transaction_id: int,
    *,
    lock: bool = False,
) -> Transaction | None:
    stmt = select(Transaction).where(Transaction.id == transaction_id)
    if lock:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def create_transaction(
    session: AsyncSession,
    buyer: User,
    account_id: int,
    commission_percent: Decimal,
) -> tuple[Transaction | None, str | None]:
    account = await session.scalar(
        select(Account).where(Account.id == account_id).with_for_update()
    )
    if account is None:
        return None, "not_found"
    if account.status != "ACTIVE":
        return None, "not_active"
    if account.seller_id == buyer.id:
        return None, "own_account"

    existing = await session.scalar(
        select(Transaction.id).where(
            Transaction.account_id == account.id,
            Transaction.status.in_(ACTIVE_TRANSACTION_STATUSES),
        )
    )
    if existing is not None:
        return None, "busy"

    amount = quantize_money(Decimal(account.price))
    commission_amount = quantize_money(amount * commission_percent / Decimal(100))
    seller_amount = quantize_money(amount - commission_amount)

    for _ in range(5):
        code = generate_transaction_code()
        if not await session.scalar(select(Transaction.id).where(Transaction.code == code)):
            break
    else:
        return None, "code_error"

    tx = Transaction(
        code=code,
        account_id=account.id,
        seller_id=account.seller_id,
        buyer_id=buyer.id,
        amount=amount,
        commission_rate=commission_percent,
        commission_amount=commission_amount,
        seller_amount=seller_amount,
        status="PENDING",
    )
    account.status = "RESERVED"
    session.add(tx)
    await session.commit()

    return await load_transaction(session, tx.id), None


async def complete_transaction(session: AsyncSession, tx: Transaction) -> None:
    tx.status = "SUCCESS"
    tx.completed_at = utcnow()
    tx.account.status = "SOLD"
    tx.seller.balance = quantize_money(Decimal(tx.seller.balance) + Decimal(tx.seller_amount))


async def cancel_pending_transaction(session: AsyncSession, tx: Transaction) -> None:
    tx.status = "CANCELLED"
    tx.account.status = "ACTIVE"
    payments = await session.scalars(
        select(Payment).where(
            Payment.transaction_id == tx.id,
            Payment.status.in_(("CREATED", "PENDING")),
        )
    )
    for payment in payments:
        payment.status = "FAILED"


async def notify_deal_paid(bot: Bot, session: AsyncSession, transaction_id: int) -> None:
    tx = await load_transaction(session, transaction_id)
    if tx is None:
        return
    await send_user_message(
        bot,
        tx.buyer.telegram_id,
        deal_paid_buyer_text(tx, tx.seller),
        deal_paid_buyer_keyboard(tx.id, user_profile_url(tx.seller)),
    )
    await send_user_message(
        bot,
        tx.seller.telegram_id,
        deal_paid_seller_text(tx, tx.buyer),
        deal_paid_seller_keyboard(tx.id, user_profile_url(tx.buyer)),
    )
