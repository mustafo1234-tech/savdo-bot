from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.constants import PAYOUT_METHODS, PLATFORMS
from bot.utils.formatting import num, platform_name, truncate


def rules_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Qabul qilish", callback_data="rules:accept")
    builder.button(text="❌ Rad etish", callback_data="rules:reject")
    builder.adjust(1)
    return builder.as_markup()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🛍 Akkaunt sotib olish", callback_data="menu:buy")
    builder.button(text="💰 Akkaunt sotish", callback_data="menu:sell")
    builder.button(text="👤 Profilim", callback_data="menu:profile")
    builder.button(text="📦 Mening e'lonlarim", callback_data="menu:listings")
    builder.button(text="💳 To'lovlarim", callback_data="menu:payments")
    builder.button(text="📜 Savdo tarixi", callback_data="menu:history")
    builder.button(text="📞 Yordam", callback_data="menu:support")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def home_keyboard(text: str = "🏠 Asosiy menyu") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=text, callback_data="menu:home")
    return builder.as_markup()


def cancel_keyboard(text: str = "❌ Bekor qilish", back_callback: str = "menu:home") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=text, callback_data=back_callback)
    return builder.as_markup()


def seller_platform_keyboard(prefix: str = "seller:platform") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, label in PLATFORMS.items():
        builder.button(text=label, callback_data=f"{prefix}:{key}")
    builder.button(text="❌ Bekor qilish", callback_data="cancel")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def seller_images_keyboard(count: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=f"✅ Rasmlar tayyor ({count}/5)", callback_data="seller:images:done")
    builder.button(text="⏭ Rasmsiz davom etish", callback_data="seller:images:skip")
    builder.button(text="❌ Bekor qilish", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


def seller_payout_keyboard(prefix: str = "seller:payout") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, label in PAYOUT_METHODS.items():
        builder.button(text=label, callback_data=f"{prefix}:{key}")
    builder.button(text="❌ Bekor qilish", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


def seller_ownership_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ha, akkaunt menga tegishli", callback_data="seller:own:yes")
    builder.button(text="❌ Yo'q, bekor qilish", callback_data="seller:own:no")
    builder.adjust(1)
    return builder.as_markup()


def seller_preview_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ E'lonni tasdiqlash", callback_data="seller:preview:confirm")
    builder.button(text="✏️ Tahrirlash", callback_data="seller:preview:edit")
    builder.button(text="❌ Bekor qilish", callback_data="seller:preview:cancel")
    builder.adjust(1)
    return builder.as_markup()


def seller_edit_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎮 Platforma", callback_data="seller:edit:platform")
    builder.button(text="🏷 Akkaunt nomi", callback_data="seller:edit:account_name")
    builder.button(text="🆔 Akkaunt ID", callback_data="seller:edit:account_identifier")
    builder.button(text="🏆 Daraja", callback_data="seller:edit:level")
    builder.button(text="🎁 Narsalar", callback_data="seller:edit:items")
    builder.button(text="📝 Tavsif", callback_data="seller:edit:description")
    builder.button(text="💰 Narx", callback_data="seller:edit:price")
    builder.button(text="🖼 Rasmlar", callback_data="seller:edit:images")
    builder.button(text="📞 Aloqa", callback_data="seller:edit:contact")
    builder.button(text="🏦 To'lov usuli", callback_data="seller:edit:payout")
    builder.button(text="🔙 Ko'rib chiqishga qaytish", callback_data="seller:preview")
    builder.adjust(2, 2, 2, 2, 2, 1)
    return builder.as_markup()


def buyer_entry_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔎 ID bo'yicha qidirish", callback_data="buyer:search")
    builder.button(text="📋 Barcha akkauntlarni ko'rish", callback_data="buyer:browse")
    builder.button(text="🏠 Asosiy menyu", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()


def buyer_browse_keyboard(accounts, page: int, pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for account in accounts:
        label = (
            f"#{account.public_id} | {platform_name(account.platform)} | "
            f"{truncate(account.account_name, 12)} | {num(account.price)}"
        )
        builder.button(text=label, callback_data=f"buyer:view:{account.id}:{page}")
    builder.adjust(1)
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"buyer:page:{page - 1}"))
    if page < pages:
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"buyer:page:{page + 1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu:home"))
    return builder.as_markup()


def buyer_account_keyboard(account_id: int, page: int, can_buy: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_buy:
        builder.button(text="🛒 Sotib olish", callback_data=f"buyer:buy:{account_id}")
    else:
        builder.button(text="⚠️ Bu sizning e'loningiz", callback_data="noop")
    back_page = page if page > 0 else 1
    builder.button(text="🔙 Orqaga", callback_data=f"buyer:page:{back_page}")
    builder.button(text="🏠 Asosiy menyu", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()


def deal_payment_keyboard(txn_id: int, click_enabled: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if click_enabled:
        builder.button(text="💳 Click orqali to'lash", callback_data=f"deal:pay_click:{txn_id}")
    builder.button(text="💰 Balansdan to'lash", callback_data=f"deal:pay_balance:{txn_id}")
    builder.button(text="🔄 To'lovni tekshirish", callback_data=f"deal:check:{txn_id}")
    builder.button(text="❌ Savdoni bekor qilish", callback_data=f"deal:cancel:{txn_id}")
    builder.adjust(1)
    return builder.as_markup()


def click_payment_keyboard(txn_id: int, pay_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Click sahifasiga o'tish", url=pay_url)
    builder.button(text="🔄 To'lovni tekshirish", callback_data=f"deal:check:{txn_id}")
    builder.button(text="❌ Savdoni bekor qilish", callback_data=f"deal:cancel:{txn_id}")
    builder.adjust(1)
    return builder.as_markup()


def deal_paid_buyer_keyboard(txn_id: int, seller_url: str | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Akkauntni oldim", callback_data=f"deal:confirm:{txn_id}")
    builder.button(text="⚠️ Muammo bor", callback_data=f"deal:problem:{txn_id}")
    if seller_url:
        builder.button(text="💬 Seller bilan bog'lanish", url=seller_url)
    builder.button(text="📜 Savdo tafsilotlari", callback_data=f"txn:view:{txn_id}")
    builder.adjust(1)
    return builder.as_markup()


def deal_paid_seller_keyboard(txn_id: int, buyer_url: str | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if buyer_url:
        builder.button(text="💬 Xaridor bilan bog'lanish", url=buyer_url)
    builder.button(text="📜 Savdo tafsilotlari", callback_data=f"txn:view:{txn_id}")
    builder.adjust(1)
    return builder.as_markup()


def review_keyboard(txn_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for rating in range(1, 6):
        stars = "⭐" * rating
        builder.button(text=stars, callback_data=f"deal:rate:{txn_id}:{rating}")
    builder.adjust(5)
    return builder.as_markup()


def review_comment_keyboard(txn_id: int, rating: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⏭ Izohsiz yuborish", callback_data=f"deal:rate_skip:{txn_id}:{rating}")
    return builder.as_markup()


def dispute_evidence_keyboard(dispute_id: int, contact_url: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Dalillarni yuborish", callback_data=f"deal:evidence_done:{dispute_id}")
    builder.button(text="📸 Yana dalil qo'shish", callback_data=f"deal:evidence:{dispute_id}")
    if contact_url:
        builder.button(text="💬 Ikkinchi tomon bilan bog'lanish", url=contact_url)
    builder.button(text="🏠 Asosiy menyu", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()


def profile_consent_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Roziman, profilni ulashish", callback_data="profile:share")
    builder.button(text="🔐 Yashirin rejimda davom etish", callback_data="profile:decline")
    builder.adjust(1)
    return builder.as_markup()


def profile_keyboard(profile_consent: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if profile_consent != "accepted":
        builder.button(text="🔐 Profilni ulashish", callback_data="profile:share")
    builder.button(text="📜 Savdo tarixi", callback_data="menu:history")
    builder.button(text="💳 To'lovlarim", callback_data="menu:payments")
    builder.button(text="🏠 Asosiy menyu", callback_data="menu:home")
    builder.adjust(1, 2, 1)
    return builder.as_markup()


def support_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📩 Murojaat yuborish", callback_data="support:message")
    builder.button(text="🏠 Asosiy menyu", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()


def mylist_account_keyboard(account_id: int, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == "ACTIVE":
        builder.button(text="⏸ Faoliyatdan chiqarish", callback_data=f"mylist:deactivate:{account_id}")
    elif status in {"INACTIVE", "PENDING", "REJECTED"}:
        builder.button(text="▶️ Qayta faollashtirish", callback_data=f"mylist:activate:{account_id}")
    builder.button(text="🔙 E'lonlarim", callback_data="menu:listings")
    builder.button(text="🏠 Asosiy menyu", callback_data="menu:home")
    builder.adjust(1)
    return builder.as_markup()


def pagination_keyboard(
    prefix: str,
    page: int,
    pages: int,
    *,
    back_text: str = "🏠 Asosiy menyu",
    back_callback: str = "menu:home",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"{prefix}:{page - 1}"))
    if page < pages:
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"{prefix}:{page + 1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text=back_text, callback_data=back_callback))
    return builder.as_markup()


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Statistika", callback_data="adm:stats")
    builder.button(text="👥 Foydalanuvchilar", callback_data="adm:users:1")
    builder.button(text="📦 Barcha e'lonlar", callback_data="adm:accounts:1")
    builder.button(text="💳 To'lovlar", callback_data="adm:payments:1")
    builder.button(text="📜 Tranzaksiyalar", callback_data="adm:transactions:1")
    builder.button(text="⚠️ Shikoyatlar", callback_data="adm:disputes:1")
    builder.button(text="📢 Xabar yuborish", callback_data="adm:broadcast")
    builder.button(text="⚙️ Sozlamalar", callback_data="adm:settings")
    builder.adjust(2, 2, 2, 2)
    return builder.as_markup()


def admin_back_keyboard(callback: str = "adm:home", text: str = "🔙 Admin panel") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=text, callback_data=callback)
    return builder.as_markup()


def admin_user_keyboard(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_banned:
        builder.button(text="✅ Bandan chiqarish", callback_data=f"adm:unban:{user_id}")
    else:
        builder.button(text="🚫 Ban qilish", callback_data=f"adm:ban:{user_id}")
    builder.button(text="🔙 Foydalanuvchilar", callback_data="adm:users:1")
    builder.adjust(1)
    return builder.as_markup()


def admin_account_keyboard(account_id: int, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == "PENDING":
        builder.button(text="✅ Tasdiqlash", callback_data=f"adm:acc_approve:{account_id}")
        builder.button(text="🚫 Bloklash", callback_data=f"adm:acc_block:{account_id}")
    elif status == "BLOCKED":
        builder.button(text="✅ Blokdan chiqarish", callback_data=f"adm:acc_unblock:{account_id}")
    elif status not in {"RESERVED", "SOLD"}:
        builder.button(text="🚫 Bloklash", callback_data=f"adm:acc_block:{account_id}")
    builder.button(text="🔙 E'lonlar", callback_data="adm:accounts:1")
    builder.adjust(1)
    return builder.as_markup()


def admin_dispute_keyboard(dispute_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="↩️ Xaridor foydasiga", callback_data=f"adm:resolve_buyer:{dispute_id}")
    builder.button(text="✅ Sotuvchi foydasiga", callback_data=f"adm:resolve_seller:{dispute_id}")
    builder.button(text="🔙 Shikoyatlar", callback_data="adm:disputes:1")
    builder.adjust(1)
    return builder.as_markup()


def admin_settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💸 Komissiya foizi", callback_data="adm:set:commission_percent")
    builder.button(text="💰 Minimal narx", callback_data="adm:set:min_price")
    builder.button(text="📞 Yordam kontakti", callback_data="adm:set:support_contact")
    builder.button(text="🛠 Texnik xizmat rejimi", callback_data="adm:toggle_maintenance")
    builder.button(text="🕓 E'lon moderatsiyasi", callback_data="adm:toggle_autoapprove")
    builder.button(text="🔙 Admin panel", callback_data="adm:home")
    builder.adjust(1)
    return builder.as_markup()


def admin_payment_keyboard(payment_id: int, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == "REFUND_PENDING":
        builder.button(text="✅ Qaytarildi deb belgilash", callback_data=f"adm:refund_done:{payment_id}")
    builder.button(text="🔙 To'lovlar", callback_data="adm:payments:1")
    builder.adjust(1)
    return builder.as_markup()

