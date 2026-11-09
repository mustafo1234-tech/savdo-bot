from __future__ import annotations

import logging
import secrets
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_config
from bot.constants import PAYOUT_METHODS, PLATFORMS, PROFILE_ACCEPTED
from bot.database.models import Account, AccountImage, User
from bot.keyboards.inline import (
    cancel_keyboard,
    profile_consent_keyboard,
    seller_edit_keyboard,
    seller_images_keyboard,
    seller_ownership_keyboard,
    seller_payout_keyboard,
    seller_platform_keyboard,
    seller_preview_keyboard,
)
from bot.services.crypto import encrypt
from bot.services.notifications import send_user_message
from bot.services.settings import auto_approve, get_min_price
from bot.states import SellerStates
from bot.texts import (
    PROFILE_REQUIRED_TEXT,
    SELLER_CANCELLED_TEXT,
    SELLER_IMAGES_PROMPT,
    SELLER_INTRO_TEXT,
    SELLER_OWNERSHIP_TEXT,
    SELLER_PAYOUT_TEXT,
    SELLER_PROMPTS,
    SELLER_SUCCESS_TEXT,
    seller_preview_text,
)
from bot.utils.formatting import h, money, platform_name, user_display
from bot.utils.telegram import safe_edit

logger = logging.getLogger(__name__)
router = Router(name="seller")


async def _reset_to_platform(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SellerStates.platform)
    await callback.answer()
    await safe_edit(callback, SELLER_INTRO_TEXT, seller_platform_keyboard())


@router.callback_query(F.data == "menu:sell")
async def seller_entry(callback: CallbackQuery, user: User, state: FSMContext) -> None:
    if user.profile_consent != PROFILE_ACCEPTED:
        await state.clear()
        await callback.answer("🔐 Profilni ulashish kerak", show_alert=True)
        await safe_edit(callback, PROFILE_REQUIRED_TEXT, profile_consent_keyboard())
        return
    await _reset_to_platform(callback, state)


@router.callback_query(SellerStates.platform, F.data.startswith("seller:platform:"))
async def choose_platform(callback: CallbackQuery, state: FSMContext) -> None:
    key = (callback.data or "").split(":")[2]
    if key not in PLATFORMS:
        await callback.answer("Noto'g'ri platforma.", show_alert=True)
        return
    await state.update_data(platform=key, images=[], ownership_confirmed=False)
    await state.set_state(SellerStates.account_name)
    await callback.answer()
    await safe_edit(callback, SELLER_PROMPTS["account_name"], cancel_keyboard())


@router.message(SellerStates.account_name, F.text)
async def input_account_name(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not 2 <= len(value) <= 80:
        await message.answer("⚠️ Akkaunt nomi 2 tadan 80 tagacha belgidan iborat bo'lishi kerak.")
        return
    await state.update_data(account_name=value)
    await state.set_state(SellerStates.account_identifier)
    await message.answer(SELLER_PROMPTS["account_identifier"], reply_markup=cancel_keyboard())


@router.message(SellerStates.account_identifier, F.text)
async def input_account_identifier(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not 2 <= len(value) <= 100:
        await message.answer("⚠️ Akkaunt ID 2 tadan 100 tagacha belgidan iborat bo'lishi kerak.")
        return
    await state.update_data(account_identifier=value)
    await state.set_state(SellerStates.level)
    await message.answer(SELLER_PROMPTS["level"], reply_markup=cancel_keyboard())


@router.message(SellerStates.level, F.text)
async def input_level(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not 1 <= len(value) <= 50:
        await message.answer("⚠️ Daraja 1 tadan 50 tagacha belgidan iborat bo'lishi kerak.")
        return
    await state.update_data(level=value)
    await state.set_state(SellerStates.items)
    await message.answer(SELLER_PROMPTS["items"], reply_markup=cancel_keyboard())


@router.message(SellerStates.items, F.text)
async def input_items(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not 2 <= len(value) <= 1000:
        await message.answer("⚠️ Narsalar ro'yxati 2 tadan 1000 tagacha belgidan iborat bo'lishi kerak.")
        return
    await state.update_data(items=value)
    await state.set_state(SellerStates.description)
    await message.answer(SELLER_PROMPTS["description"], reply_markup=cancel_keyboard())


@router.message(SellerStates.description, F.text)
async def input_description(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    value = (message.text or "").strip()
    if not 10 <= len(value) <= 2000:
        await message.answer("⚠️ Tavsif 10 tadan 2000 tagacha belgidan iborat bo'lishi kerak.")
        return
    await state.update_data(description=value)
    await state.set_state(SellerStates.price)
    min_price = await get_min_price(session)
    await message.answer(
        SELLER_PROMPTS["price"] + f"\n\n💡 Minimal narx: <b>{money(min_price)}</b>",
        reply_markup=cancel_keyboard(),
    )


@router.message(SellerStates.price, F.text)
async def input_price(message: Message, state: FSMContext, session: AsyncSession) -> None:
    from bot.utils.formatting import parse_price

    value = parse_price(message.text or "")
    if value is None:
        await message.answer("⚠️ Narxni faqat raqamlarda kiriting. Masalan: 250000")
        return
    min_price = await get_min_price(session)
    if value < min_price:
        await message.answer(f"⚠️ Minimal narx: <b>{money(min_price)}</b>. Qayta kiriting.")
        return
    if value > Decimal(1000000000):
        await message.answer("⚠️ Narx juda katta. Iltimos, oqilona narx kiriting.")
        return
    await state.update_data(price=str(value), images=[])
    await state.set_state(SellerStates.images)
    await message.answer(SELLER_IMAGES_PROMPT, reply_markup=seller_images_keyboard(0))


@router.message(SellerStates.images, F.photo)
async def input_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    images = list(data.get("images") or [])
    if len(images) >= 5:
        await message.answer("⚠️ Maksimal 5 ta rasm. «Rasmlar tayyor» tugmasini bosing.")
        return
    file_id = message.photo[-1].file_id
    images.append(file_id)
    await state.update_data(images=images)
    await message.answer(
        f"✅ Rasm qabul qilindi ({len(images)}/5). Yana rasm yuborishingiz yoki davom etishingiz mumkin.",
        reply_markup=seller_images_keyboard(len(images)),
    )


@router.message(SellerStates.images)
async def input_photo_wrong_type(message: Message) -> None:
    await message.answer(
        "🖼 Iltimos, rasm yuboring yoki «Rasmlar tayyor» / «Rasmsiz davom etish» tugmasini bosing."
    )


@router.callback_query(SellerStates.images, F.data == "seller:images:done")
async def images_done(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await callback.answer()
    if data.get("editing_images"):
        await state.update_data(editing_images=False)
        await state.set_state(SellerStates.preview)
        await _show_preview_callback(callback, state)
        return
    await state.set_state(SellerStates.contact)
    await safe_edit(callback, SELLER_PROMPTS["contact"], cancel_keyboard())


@router.callback_query(SellerStates.images, F.data == "seller:images:skip")
async def images_skip(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await callback.answer()
    if data.get("editing_images"):
        await state.update_data(editing_images=False, images=[])
        await state.set_state(SellerStates.preview)
        await _show_preview_callback(callback, state)
        return
    await state.update_data(images=[])
    await state.set_state(SellerStates.contact)
    await safe_edit(callback, SELLER_PROMPTS["contact"], cancel_keyboard())


@router.message(SellerStates.contact, F.text)
async def input_contact(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not 3 <= len(value) <= 150:
        await message.answer("⚠️ Aloqa ma'lumoti 3 tadan 150 tagacha belgidan iborat bo'lishi kerak.")
        return
    await state.update_data(contact=value)
    await state.set_state(SellerStates.payout)
    await message.answer(SELLER_PAYOUT_TEXT, reply_markup=seller_payout_keyboard())


@router.callback_query(SellerStates.payout, F.data.startswith("seller:payout:"))
async def choose_payout(callback: CallbackQuery, state: FSMContext) -> None:
    key = (callback.data or "").split(":")[2]
    if key not in PAYOUT_METHODS:
        await callback.answer("Noto'g'ri usul.", show_alert=True)
        return
    await state.update_data(payout_method=key)
    await state.set_state(SellerStates.ownership)
    await callback.answer()
    await safe_edit(callback, SELLER_OWNERSHIP_TEXT, seller_ownership_keyboard())


@router.callback_query(SellerStates.ownership, F.data == "seller:own:no")
async def ownership_no(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await safe_edit(callback, SELLER_CANCELLED_TEXT, _home_only_keyboard())


@router.callback_query(SellerStates.ownership, F.data == "seller:own:yes")
async def ownership_yes(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(ownership_confirmed=True)
    await state.set_state(SellerStates.preview)
    await callback.answer("✅ Egalik tasdiqlandi")
    await _show_preview_callback(callback, state)


def _home_only_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Asosiy menyu", callback_data="menu:home")
    return builder.as_markup()


async def _show_preview_callback(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await safe_edit(callback, seller_preview_text(data), seller_preview_keyboard())


async def _show_preview_message(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await message.answer(seller_preview_text(data), reply_markup=seller_preview_keyboard())


@router.callback_query(F.data == "seller:preview")
async def preview_return(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _show_preview_callback(callback, state)


@router.callback_query(SellerStates.preview, F.data == "seller:preview:edit")
async def preview_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await safe_edit(
        callback,
        "✏️ <b>Qaysi qismni tahrirlaysiz?</b>\n\nKerakli bo'limni tanlang.",
        seller_edit_keyboard(),
    )


@router.callback_query(SellerStates.preview, F.data == "seller:preview:cancel")
async def preview_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Bekor qilindi")
    await safe_edit(callback, SELLER_CANCELLED_TEXT, _home_only_keyboard())


@router.callback_query(SellerStates.preview, F.data.startswith("seller:edit:"))
async def preview_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    field = (callback.data or "").split(":")[2]
    if field == "platform":
        await callback.answer()
        await safe_edit(
            callback,
            "🎮 Yangi platformani tanlang 👇",
            seller_platform_keyboard("seller:editplat"),
        )
        return
    if field == "images":
        data = await state.get_data()
        images = list(data.get("images") or [])
        await state.update_data(editing_images=True)
        await state.set_state(SellerStates.images)
        await callback.answer()
        await safe_edit(
            callback,
            SELLER_IMAGES_PROMPT + f"\n\nHozir: <b>{len(images)}/5</b> rasm.",
            seller_images_keyboard(len(images)),
        )
        return
    if field == "payout":
        await callback.answer()
        await safe_edit(callback, SELLER_PAYOUT_TEXT, seller_payout_keyboard("seller:editpay"))
        return
    if field not in SELLER_PROMPTS:
        await callback.answer("Bu qismni tahrirlab bo'lmaydi.", show_alert=True)
        return
    await state.update_data(edit_field=field)
    await state.set_state(SellerStates.edit_value)
    await callback.answer()
    await safe_edit(
        callback,
        "✏️ <b>Yangi qiymat kiriting</b>\n\n" + SELLER_PROMPTS[field],
        cancel_keyboard("🔙 Ko'rib chiqishga qaytish", "seller:preview"),
    )


@router.callback_query(SellerStates.preview, F.data.startswith("seller:editplat:"))
async def edit_platform(callback: CallbackQuery, state: FSMContext) -> None:
    key = (callback.data or "").split(":")[2]
    if key not in PLATFORMS:
        await callback.answer("Noto'g'ri platforma.", show_alert=True)
        return
    await state.update_data(platform=key, editing_images=False)
    await state.set_state(SellerStates.preview)
    await callback.answer("Platforma yangilandi")
    await _show_preview_callback(callback, state)


@router.callback_query(SellerStates.preview, F.data.startswith("seller:editpay:"))
async def edit_payout(callback: CallbackQuery, state: FSMContext) -> None:
    key = (callback.data or "").split(":")[2]
    if key not in PAYOUT_METHODS:
        await callback.answer("Noto'g'ri usul.", show_alert=True)
        return
    await state.update_data(payout_method=key)
    await state.set_state(SellerStates.preview)
    await callback.answer("To'lov usuli yangilandi")
    await _show_preview_callback(callback, state)


async def _validate_edit_value(field: str, value: str, session: AsyncSession) -> tuple[str | None, str | None]:
    from bot.utils.formatting import parse_price

    if field == "account_name":
        if not 2 <= len(value) <= 80:
            return None, "Akkaunt nomi 2-80 belgi bo'lishi kerak."
        return value, None
    if field == "account_identifier":
        if not 2 <= len(value) <= 100:
            return None, "Akkaunt ID 2-100 belgi bo'lishi kerak."
        return value, None
    if field == "level":
        if not 1 <= len(value) <= 50:
            return None, "Daraja 1-50 belgi bo'lishi kerak."
        return value, None
    if field == "items":
        if not 2 <= len(value) <= 1000:
            return None, "Narsalar 2-1000 belgi bo'lishi kerak."
        return value, None
    if field == "description":
        if not 10 <= len(value) <= 2000:
            return None, "Tavsif 10-2000 belgi bo'lishi kerak."
        return value, None
    if field == "contact":
        if not 3 <= len(value) <= 150:
            return None, "Aloqa 3-150 belgi bo'lishi kerak."
        return value, None
    if field == "price":
        parsed = parse_price(value)
        if parsed is None:
            return None, "Narxni faqat raqamlarda kiriting."
        min_price = await get_min_price(session)
        if parsed < min_price:
            return None, f"Minimal narx: {money(min_price)}."
        if parsed > Decimal(1000000000):
            return None, "Narx juda katta."
        return str(parsed), None
    return None, "Noma'lum maydon."


@router.message(SellerStates.edit_value, F.text)
async def edit_value_input(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    field = data.get("edit_field")
    value = (message.text or "").strip()
    if not field:
        await state.set_state(SellerStates.preview)
        await _show_preview_message(message, state)
        return
    validated, error = await _validate_edit_value(field, value, session)
    if error or validated is None:
        await message.answer(f"⚠️ {h(error or 'Noto‘g‘ri qiymat.')}")
        return
    await state.update_data({field: validated})
    await state.set_state(SellerStates.preview)
    await message.answer("✅ Yangilandi.")
    await _show_preview_message(message, state)


@router.callback_query(SellerStates.preview, F.data == "seller:preview:confirm")
async def preview_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    data = await state.get_data()
    required = [
        "platform",
        "account_name",
        "account_identifier",
        "level",
        "items",
        "description",
        "price",
        "payout_method",
    ]
    missing = [key for key in required if not data.get(key)]
    if missing or not data.get("ownership_confirmed"):
        await callback.answer("Ma'lumotlar to'liq emas. Iltimos, qaytadan tekshiring.", show_alert=True)
        return

    try:
        price = Decimal(str(data["price"]))
    except Exception:  # noqa: BLE001
        await callback.answer("Narx noto'g'ri.", show_alert=True)
        return

    status = "ACTIVE" if await auto_approve(session) else "PENDING"
    account = Account(
        public_id=f"T{secrets.token_hex(8)}",
        seller_id=user.id,
        platform=str(data["platform"]),
        account_name=str(data["account_name"]),
        account_identifier_encrypted=encrypt(str(data["account_identifier"])),
        level=str(data["level"]),
        items=str(data["items"]),
        description=str(data["description"]),
        price=price,
        contact_encrypted=encrypt(str(data.get("contact", ""))),
        payout_method=str(data["payout_method"]),
        ownership_confirmed=True,
        status=status,
    )
    session.add(account)
    await session.flush()
    account.public_id = f"ACC{1000 + account.id}"
    for file_id in data.get("images") or []:
        session.add(AccountImage(account_id=account.id, file_id=str(file_id)))
    await session.commit()

    await state.clear()
    await callback.answer("✅ E'lon tasdiqlandi")
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 E'lonni ko'rish", callback_data=f"mylist:view:{account.id}")
    builder.button(text="🏠 Asosiy menyu", callback_data="menu:home")
    builder.adjust(1)
    await safe_edit(
        callback,
        SELLER_SUCCESS_TEXT.format(public_id=account.public_id)
        + ("\n\n🕓 E'lon admin tasdiqlashini kutmoqda." if status == "PENDING" else ""),
        builder.as_markup(),
    )

    config = get_config()
    if config.owner_id != user.telegram_id:
        await send_user_message(
            callback.bot,
            config.owner_id,
            "🆕 <b>Yangi e'lon</b>\n\n"
            f"🆔 #{h(account.public_id)}\n"
            f"{h(platform_name(account.platform))}\n"
            f"🏷 {h(account.account_name)}\n"
            f"💰 {money(account.price)}\n"
            f"👤 Sotuvchi: {user_display(user)}\n"
            f"📌 Holat: {h(status)}",
        )

