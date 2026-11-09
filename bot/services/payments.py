from __future__ import annotations

import hashlib
import hmac
import logging
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.database.models import Payment
from bot.services.deals import load_transaction, quantize_money, utcnow
from bot.services.notifications import add_notification

logger = logging.getLogger(__name__)

CLICK_ERROR_SIGN = -1
CLICK_ERROR_AMOUNT = -2
CLICK_ERROR_ACTION = -3
CLICK_ERROR_ALREADY_PAID = -4
CLICK_ERROR_PAYMENT_NOT_FOUND = -6
CLICK_ERROR_REQUEST = -8
CLICK_ERROR_CANCELLED = -9


def build_click_payment_url(config: Config, amount: Decimal, payment_uid: str) -> str:
    amount_str = f"{Decimal(amount):.2f}"
    params = {
        "service_id": config.click_service_id,
        "merchant_id": config.click_merchant_id,
        "amount": amount_str,
        "transaction_param": payment_uid,
    }
    return "https://my.click.uz/services/pay?" + urlencode(params)


def _sign_string(data: dict[str, Any], secret_key: str) -> str:
    action = str(data.get("action", ""))
    prepare_id = str(data.get("merchant_prepare_id", "")) if action in {"1", "1.0"} else ""
    raw = (
        f"{data.get('click_trans_id', '')}"
        f"{data.get('service_id', '')}"
        f"{secret_key}"
        f"{data.get('merchant_trans_id', '')}"
        f"{prepare_id}"
        f"{data.get('amount', '')}"
        f"{action}"
        f"{data.get('sign_time', '')}"
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def verify_click_signature(data: dict[str, Any], secret_key: str) -> bool:
    provided = str(data.get("sign_string", "")).strip()
    expected = _sign_string(data, secret_key)
    return bool(provided) and hmac.compare_digest(provided.lower(), expected.lower())


def _response(error: int, note: str, data: dict[str, Any], **extra: Any) -> dict[str, Any]:
    payload = {
        "error": error,
        "error_note": note,
        "click_trans_id": data.get("click_trans_id"),
        "merchant_trans_id": data.get("merchant_trans_id"),
    }
    payload.update(extra)
    return payload


async def _find_payment(
    session: AsyncSession,
    payment_uid: str,
    *,
    lock: bool = False,
) -> Payment | None:
    stmt = select(Payment).where(
        Payment.payment_uid == payment_uid,
        Payment.provider == "click",
    )
    if lock:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def _has_other_paid_payment(
    session: AsyncSession,
    transaction_id: int,
    payment_id: int,
) -> bool:
    return (
        await session.scalar(
            select(Payment.id).where(
                Payment.transaction_id == transaction_id,
                Payment.status == "PAID",
                Payment.id != payment_id,
            )
        )
    ) is not None



def _amount_matches(raw_amount: Any, payment: Payment) -> bool:
    try:
        supplied = quantize_money(Decimal(str(raw_amount)))
    except (InvalidOperation, ValueError):
        return False
    return supplied == quantize_money(Decimal(payment.amount))


async def process_click_prepare(
    session: AsyncSession,
    data: dict[str, Any],
    config: Config,
) -> dict[str, Any]:
    if not config.click_enabled or config.click_secret_key is None:
        return _response(CLICK_ERROR_REQUEST, "Click sozlanmagan", data)
    if str(data.get("action", "")) not in {"0", "0.0"}:
        return _response(CLICK_ERROR_ACTION, "Noto'g'ri action", data)
    if str(data.get("service_id", "")) != str(config.click_service_id):
        return _response(CLICK_ERROR_REQUEST, "Service ID mos emas", data)
    if not verify_click_signature(data, config.click_secret_key):
        logger.warning("Click prepare: imzo tekshiruvi muvaffaqiyatsiz (payment_uid=%s).", data.get("merchant_trans_id"))
        return _response(CLICK_ERROR_SIGN, "Imzo xato", data)

    payment_uid = str(data.get("merchant_trans_id", ""))
    payment = await _find_payment(session, payment_uid, lock=True)
    if payment is None:
        return _response(CLICK_ERROR_PAYMENT_NOT_FOUND, "To'lov topilmadi", data)
    if payment.status == "PAID":
        return _response(CLICK_ERROR_ALREADY_PAID, "Allaqachon to'langan", data)
    if payment.status in {"FAILED", "REFUNDED", "REFUND_PENDING"}:
        return _response(CLICK_ERROR_CANCELLED, "To'lov bekor qilingan", data)
    if not _amount_matches(data.get("amount"), payment):
        return _response(CLICK_ERROR_AMOUNT, "Summa mos emas", data)

    tx = await load_transaction(session, payment.transaction_id, lock=True)
    if tx is None:
        return _response(CLICK_ERROR_PAYMENT_NOT_FOUND, "Tranzaksiya topilmadi", data)
    if tx.status in {"CANCELLED"}:
        return _response(CLICK_ERROR_CANCELLED, "Tranzaksiya bekor qilingan", data)
    if tx.status in {"VERIFYING", "SUCCESS", "DISPUTE", "PAID"} or await _has_other_paid_payment(
        session, tx.id, payment.id
    ):
        return _response(CLICK_ERROR_ALREADY_PAID, "Tranzaksiya allaqachon to'langan", data)

    payment.status = "PENDING"
    payment.payload = {str(k): str(v) for k, v in data.items()}
    await session.commit()
    return _response(
        0,
        "Success",
        data,
        merchant_prepare_id=payment.id,
    )



async def process_click_complete(
    session: AsyncSession,
    data: dict[str, Any],
    config: Config,
) -> tuple[dict[str, Any], int | None, bool]:
    """Natija: (javob, tranzaksiya_id, yangi_to'lov_bo'ldimi)."""
    if not config.click_enabled or config.click_secret_key is None:
        return _response(CLICK_ERROR_REQUEST, "Click sozlanmagan", data), None, False
    if str(data.get("action", "")) not in {"1", "1.0"}:
        return _response(CLICK_ERROR_ACTION, "Noto'g'ri action", data), None, False
    if str(data.get("service_id", "")) != str(config.click_service_id):
        return _response(CLICK_ERROR_REQUEST, "Service ID mos emas", data), None, False
    if not verify_click_signature(data, config.click_secret_key):
        logger.warning("Click complete: imzo tekshiruvi muvaffaqiyatsiz (payment_uid=%s).", data.get("merchant_trans_id"))
        return _response(CLICK_ERROR_SIGN, "Imzo xato", data), None, False

    payment_uid = str(data.get("merchant_trans_id", ""))
    payment = await _find_payment(session, payment_uid, lock=True)
    if payment is None:
        return _response(CLICK_ERROR_PAYMENT_NOT_FOUND, "To'lov topilmadi", data), None, False

    prepare_id = data.get("merchant_prepare_id")
    if prepare_id not in (None, "") and str(prepare_id) != str(payment.id):
        return _response(CLICK_ERROR_REQUEST, "Prepare ID mos emas", data), None, False

    click_error = str(data.get("error", "0"))
    if click_error not in {"0", "0.0", ""}:
        payment.status = "FAILED"
        payment.payload = {str(k): str(v) for k, v in data.items()}
        await session.commit()
        return _response(CLICK_ERROR_CANCELLED, "Click to'lovi bekor qilindi", data), None, False

    if not _amount_matches(data.get("amount"), payment):
        return _response(CLICK_ERROR_AMOUNT, "Summa mos emas", data), None, False

    tx = await load_transaction(session, payment.transaction_id, lock=True)
    if tx is None:
        return _response(CLICK_ERROR_PAYMENT_NOT_FOUND, "Tranzaksiya topilmadi", data), None, False

    if payment.status == "PAID":
        return _response(
            0, "Success", data, merchant_confirm_id=tx.id
        ), None, False

    if tx.status == "CANCELLED":
        payment.status = "REFUND_PENDING"
        payment.payload = {str(k): str(v) for k, v in data.items()}
        add_notification(
            session,
            tx.buyer_id,
            "Click to'lovi kechikdi",
            f"{tx.code} tranzaksiyasi bekor qilingan, lekin Click to'lovi kelgan. Admin qaytarishni amalga oshiradi.",
        )
        await session.commit()
        logger.warning("Click to'lovi bekor qilingan tranzaksiyaga keldi: %s", tx.code)
        return _response(CLICK_ERROR_CANCELLED, "Tranzaksiya bekor qilingan", data), None, False

    if tx.status in {"VERIFYING", "SUCCESS", "DISPUTE", "PAID"} or await _has_other_paid_payment(
        session, tx.id, payment.id
    ):
        payment.status = "REFUND_PENDING"
        payment.provider_trans_id = str(data.get("click_trans_id") or "")
        payment.payload = {str(k): str(v) for k, v in data.items()}
        add_notification(
            session,
            tx.buyer_id,
            "Click to'lovi qaytarilishi kerak",
            f"{tx.code} tranzaksiyasi boshqa usulda to'langan. Click to'lovi uchun qaytarish kutilmoqda.",
        )
        add_notification(
            session,
            tx.seller_id,
            "Click to'lovi qaytarilishi kerak",
            f"{tx.code} uchun ortiqcha Click to'lovi keldi. Admin qaytarishni amalga oshiradi.",
        )
        await session.commit()
        logger.warning("Click to'lovi allaqachon to'langan tranzaksiyaga keldi: %s", tx.code)
        return _response(CLICK_ERROR_ALREADY_PAID, "Tranzaksiya allaqachon to'langan", data), None, False

    if tx.status == "PENDING":
        tx.status = "VERIFYING"
        newly_paid = True
    else:
        newly_paid = False

    payment.status = "PAID"
    payment.provider_trans_id = str(data.get("click_trans_id") or "")
    payment.paid_at = utcnow()
    payment.payload = {str(k): str(v) for k, v in data.items()}
    add_notification(
        session,
        tx.buyer_id,
        "To'lov tasdiqlandi",
        f"{tx.code} tranzaksiyasi uchun Click to'lovi tasdiqlandi.",
    )
    add_notification(
        session,
        tx.seller_id,
        "Xaridor to'lov qildi",
        f"{tx.code} tranzaksiyasi uchun to'lov tasdiqlandi. Akkauntni topshiring.",
    )
    await session.commit()
    return (
        _response(0, "Success", data, merchant_confirm_id=tx.id),
        tx.id,
        newly_paid,
    )

