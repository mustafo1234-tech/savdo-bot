from __future__ import annotations

from bot.constants import PAYOUT_METHODS, PROFILE_ACCEPTED
from bot.services.crypto import decrypt
from bot.utils.formatting import (
    account_status,
    h,
    money,
    num,
    platform_name,
    rating_text,
    tx_status,
    user_contact,
    user_display,
)

RULES_TEXT = (
    "📜 <b>BOT QOIDALARI VA SAVDO SHARTLARI</b>\n"
    "\n"
    "1️⃣ <b>Bot vositachi.</b> Bot o'yin akkauntlarini sotish va sotib olish uchun "
    "xavfsiz maydon yaratadi, lekin akkauntning o'ziga egalik qilmaydi.\n"
    "2️⃣ <b>Maxfiy ma'lumotlar.</b> Akkaunt paroli, email paroli, SMS kodi yoki "
    "boshqa maxfiy login ma'lumotlarini <b>hech qachon botga yubormang</b>. Bot ularni "
    "so'ramaydi va saqlamaydi.\n"
    "3️⃣ <b>Topshirish.</b> Akkaunt faqat platforma qoidalariga mos, xavfsiz usulda "
    "topshiriladi. Sotuvchi akkauntni xaridorga o'tkazishga tayyor bo'lishi shart.\n"
    "4️⃣ <b>Komissiya.</b> Platforma komissiyasi sotuvchi oladigan summadan ushlanadi. "
    "Aniq miqdor to'lovdan oldin ko'rsatiladi.\n"
    "5️⃣ <b>To'lov.</b> To'lov faqat payment provider tomonidan tasdiqlangandan keyin "
    "qabul qilinadi. Skrinshot yoki \"to'ladim\" degan xabar to'lov hisoblanmaydi.\n"
    "6️⃣ <b>Nizo.</b> Akkaunt e'longa mos kelmasa, xaridor dalillar bilan shikoyat "
    "ochishi mumkin. Nizoni admin ko'rib chiqadi.\n"
    "7️⃣ <b>Taqiqlangan.</b> Yolg'on e'lon, boshqa birovning akkaunti, soxta to'lov, "
    "haqorat va aldash — doimiy ban.\n"
    "8️⃣ <b>Maxfiylik.</b> Shaxsiy ma'lumotlar faqat bitimni bajarish doirasida "
    "ishtirokchilarga ko'rsatiladi.\n"
    "\n"
    "Davom etish uchun qoidalarni qabul qiling."
)

RULES_GATE_TEXT = "⚠️ <b>Avval bot qoidalarini qabul qilishingiz kerak.</b>"

RULES_REJECTED_TEXT = (
    "❌ <b>Siz qoidalarni rad etdingiz.</b>\n\n"
    "Qoidalarni qabul qilmasdan botdan foydalana olmaysiz. "
    "Qayta o'qib chiqish uchun quyidagi tugmani bosing."
)

PROFILE_CONSENT_TEXT = (
    "👤 <b>TELEGRAM PROFILINGIZ</b>\n\n"
    "Bot ismingiz, username va Telegram ID ni Telegram API orqali oladi.\n\n"
    "Savdo ishtirokchilari bir-birini ko'rishi va bog'lanishi uchun profilingiz "
    "bitim doirasida ulashiladi. Boshqa holatda shaxsiy ma'lumotlaringiz "
    "boshqa foydalanuvchilarga ko'rsatilmaydi.\n\n"
    "⚠️ Profilni ulashmasangiz, akkaunt sotib olish va sotish funksiyalari "
    "ishlamaydi.\n\n"
    "Davom etish uchun rozilik bildiring 👇"
)

PROFILE_ACCEPTED_TEXT = (
    "✅ <b>Profil ulashildi.</b>\n\n"
    "Endi savdo ishtirokchilari bitim doirasida profilingizni ko'ra oladi."
)

PROFILE_DECLINED_TEXT = (
    "🔐 <b>Profil yashirin rejimda.</b>\n\n"
    "Profilingiz boshqa foydalanuvchilarga ko'rsatilmaydi. "
    "Akkaunt sotib olish yoki sotish uchun keyinchalik profilni ulashingiz mumkin.\n\n"
    "Buning uchun «👤 Profilim» bo'limidagi «🔐 Profilni ulashish» tugmasini bosing."
)

PROFILE_REQUIRED_TEXT = (
    "🔐 <b>Avval profilingizni ulashingiz kerak.</b>\n\n"
    "Xavfsiz savdo uchun ishtirokchilar bir-birini ko'rishi zarur. "
    "Profilni ulash orqali davom etishingiz mumkin 👇"
)


def main_menu_text(user) -> str:
    return (
        "🎮 <b>GAME MARKETPLACE</b>\n"
        "\n"
        f"Assalomu alaykum, {user_display(user)}! 👋\n"
        "\n"
        "Bu yerda siz o'yin akkauntlarini xavfsiz sotishingiz va sotib olishingiz mumkin.\n"
        "\n"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
        f"⭐ Reyting: {rating_text(user)}\n"
        f"💰 Balans: <b>{money(user.balance)}</b>\n"
        "\n"
        "Kerakli bo'limni tanlang 👇"
    )


SELLER_INTRO_TEXT = (
    "💰 <b>AKKAUNT SOTISH</b>\n"
    "\n"
    "Qaysi platforma akkauntini sotmoqchisiz?\n"
    "Platformani tanlang 👇"
)

SELLER_PROMPTS: dict[str, str] = {
    "account_name": (
        "🏷 <b>Akkaunt nomi</b>\n\n"
        "Akkauntning ko'rinadigan nomini kiriting.\n"
        "<i>Masalan: ProPlayer_01</i>"
    ),
    "account_identifier": (
        "🆔 <b>Akkaunt ID</b>\n\n"
        "Faqat akkauntning ID raqamini kiriting.\n"
        "⚠️ <b>Parol, email paroli yoki SMS kodini yubormang!</b>"
    ),
    "level": (
        "🏆 <b>Akkaunt darajasi</b>\n\n"
        "Darajani kiriting.\n"
        "<i>Masalan: 45 yoki Legendary III</i>"
    ),
    "items": (
        "🎁 <b>Akkauntdagi narsalar va imkoniyatlar</b>\n\n"
        "Skinlar, qahramonlar, rank va boshqa muhim narsalarni sanang."
    ),
    "description": (
        "📝 <b>Akkaunt haqida batafsil</b>\n\n"
        "Akkaunt haqida qo'shimcha ma'lumot yozing. Xaridor qanchalik aniq "
        "ma'lumot olsa, savdo shunchalik tez bo'ladi."
    ),
    "price": (
        "💰 <b>Narx</b>\n\n"
        "Akkaunt narxini so'mda kiriting. Faqat raqam yuboring.\n"
        "<i>Masalan: 250000</i>"
    ),
    "contact": (
        "📞 <b>Aloqa ma'lumotlari</b>\n\n"
        "Telegram username yoki telefon raqamingizni kiriting.\n"
        "🔐 Bu ma'lumot shifrlangan holda saqlanadi va faqat bitim doirasida ko'rsatiladi."
    ),
}

SELLER_IMAGES_PROMPT = (
    "🖼 <b>Akkaunt rasmlari (ixtiyoriy)</b>\n\n"
    "1 tadan 5 tagacha rasm yuborishingiz mumkin. Rasm bo'lmasa ham e'lon joylanadi.\n\n"
    "Rasmlar yuborib bo'lgach <b>«Rasmlar tayyor»</b> tugmasini bosing."
)

SELLER_PAYOUT_TEXT = (
    "🏦 <b>To'lovni qabul qilish usuli</b>\n\n"
    "Sotuvchi sifatida pulni qanday qabul qilmoqchisiz? Tanlang 👇"
)

SELLER_OWNERSHIP_TEXT = (
    "🔐 <b>Egalikni tasdiqlash</b>\n\n"
    "E'lon joylashdan oldin quyidagilarni tasdiqlang:\n"
    "• Akkaunt haqiqatan ham sizga tegishli.\n"
    "• Akkauntni xaridorga platforma qoidalariga mos xavfsiz usulda topshira olasiz.\n"
    "• E'londagi barcha ma'lumotlar to'g'ri.\n\n"
    "⚠️ Yolg'on tasdiqlash doimiy ban bilan yakunlanadi."
)


def seller_preview_text(data: dict) -> str:
    images = data.get("images") or []
    payout = PAYOUT_METHODS.get(data.get("payout_method", ""), "—")
    return (
        "👀 <b>E'LONNI KO'RIB CHIQISH</b>\n"
        "\n"
        f"Platforma: <b>{h(platform_name(data.get('platform', '')))}</b>\n"
        f"🏷 Akkaunt nomi: <b>{h(data.get('account_name', '—'))}</b>\n"
        f"🆔 Akkaunt ID: <code>{h(data.get('account_identifier', '—'))}</code>\n"
        f"🏆 Daraja: <b>{h(data.get('level', '—'))}</b>\n"
        f"💰 Narx: <b>{money(data.get('price', 0))}</b>\n"
        f"🏦 To'lov usuli: {h(payout)}\n"
        f"📞 Aloqa: {h(data.get('contact', '—'))}\n"
        f"🖼 Rasmlar: {len(images)} ta\n"
        "\n"
        f"🎁 <b>Narsalar:</b>\n{h(data.get('items', '—'))}\n"
        "\n"
        f"📝 <b>Tavsif:</b>\n{h(data.get('description', '—'))}\n"
        "\n"
        "Ma'lumotlar to'g'rimi? Tasdiqlasangiz e'lon faol holatga o'tadi."
    )


SELLER_SUCCESS_TEXT = (
    "✅ <b>E'LON MUVAFFAQIYATLI JOYLANDI!</b>\n\n"
    "E'lon ID: <b>#{public_id}</b>\n"
    "Holati: ✅ Faol\n\n"
    "Endi xaridorlar e'loningizni ko'rishlari va sotib olishlari mumkin. "
    "Savdo boshlanganda sizga xabar beramiz."
)

SELLER_CANCELLED_TEXT = "❌ E'lon joylash bekor qilindi. Asosiy menyudasiz."

BUYER_ENTRY_TEXT = (
    "🛍 <b>AKKAUNT SOTIB OLISH</b>\n"
    "\n"
    "🔎 Akkaunt ID raqamini kiriting yoki barcha mavjud e'lonlarni ko'ring.\n"
    "\n"
    "ID namunasi: <code>ACC1025</code> yoki <code>1025</code>"
)

BUYER_SEARCH_TEXT = (
    "🔎 <b>Akkaunt ID sini kiriting</b>\n\n"
    "Masalan: <code>ACC1025</code> yoki <code>1025</code>"
)

BUYER_NOT_FOUND_TEXT = (
    "😕 <b>Bunday faol akkaunt topilmadi.</b>\n\n"
    "ID ni tekshirib qayta urinib ko'ring yoki barcha akkauntlarni ko'ring."
)

BUYER_EMPTY_TEXT = (
    "📭 <b>Hozircha faol akkauntlar yo'q.</b>\n\n"
    "Keyinroq qayta tekshirib ko'ring yoki o'zingiz akkaunt sotishingiz mumkin."
)


def buyer_list_text(page: int, pages: int, total: int) -> str:
    return (
        "📋 <b>MAVJUD AKKAUNTLAR</b>\n"
        "\n"
        f"Jami: <b>{total}</b> ta e'lon | Sahifa: <b>{page}/{pages}</b>\n"
        "\n"
        "Akkauntni tanlang 👇"
    )


def visible_contact(user) -> str:
    """Profil roziligi bo'lsa kontaktni, aks holda yashirin holatni qaytaradi."""
    if getattr(user, "profile_consent", None) == PROFILE_ACCEPTED:
        return user_contact(user)
    return "🔒 yashirin profil"


def account_detail_text(account) -> str:
    seller = account.seller
    if getattr(seller, "profile_consent", None) == PROFILE_ACCEPTED:
        seller_line = f"👤 Sotuvchi: {h(seller.full_name or 'Foydalanuvchi')}"
    else:
        seller_line = "👤 Sotuvchi: 🔒 yashirin profil"
    return (
        f"🆔 <b>#{h(account.public_id)}</b>\n"
        "\n"
        f"Platforma: <b>{h(platform_name(account.platform))}</b>\n"
        f"🏷 Nom: <b>{h(account.account_name)}</b>\n"
        f"🏆 Daraja: <b>{h(account.level)}</b>\n"
        f"💰 Narx: <b>{money(account.price)}</b>\n"
        f"👁 Ko'rishlar: {account.views}\n"
        "\n"
        f"🎁 <b>Narsalar:</b>\n{h(account.items)}\n"
        "\n"
        f"📝 <b>Tavsif:</b>\n{h(account.description)}\n"
        "\n"
        f"{seller_line}\n"
        f"⭐ Sotuvchi reytingi: {rating_text(seller)}\n"
        "\n"
        "ℹ️ Sotuvchining aloqa ma'lumotlari faqat to'lov tasdiqlangandan keyin ko'rsatiladi."
    )


def deal_preview_text(tx, account, commission_percent) -> str:
    return (
        "🛒 <b>SAVDO TAFSILOTLARI</b>\n"
        "\n"
        f"📜 Tranzaksiya: <code>{h(tx.code)}</code>\n"
        f"📦 E'lon: <b>#{h(account.public_id)}</b> — {h(platform_name(account.platform))}\n"
        f"🏷 {h(account.account_name)}\n"
        "\n"
        f"💵 Narx: <b>{money(tx.amount)}</b>\n"
        f"💸 Platforma komissiyasi ({num(commission_percent)}%): <b>{money(tx.commission_amount)}</b>\n"
        f"💰 Sotuvchi oladi: <b>{money(tx.seller_amount)}</b>\n"
        "\n"
        "ℹ️ Komissiya sotuvchi summasidan ushlanadi. Xaridor faqat e'londagi narxni to'laydi.\n"
        "\n"
        "⚠️ To'lov faqat payment provider tasdiqlagach qabul qilinadi. "
        "To'lovdan so'ng ishtirokchilarning aloqa ma'lumotlari ochiladi.\n"
        "\n"
        "To'lov usulini tanlang 👇"
    )


def deal_pending_text(tx, account) -> str:
    return (
        "⏳ <b>TO'LOV KUTILMOQDA</b>\n"
        "\n"
        f"📜 Tranzaksiya: <code>{h(tx.code)}</code>\n"
        f"📦 #{h(account.public_id)} — {h(account.account_name)}\n"
        f"💵 To'lov summasi: <b>{money(tx.amount)}</b>\n"
        "\n"
        "To'lov providerga o'ting va to'lovni yakunlang. So'ng «To'lovni tekshirish» "
        "tugmasini bosing yoki bot avtomatik xabar beradi."
    )


def click_payment_text(tx) -> str:
    return (
        "💳 <b>CLICK ORQALI TO'LOV</b>\n"
        "\n"
        f"📜 Tranzaksiya: <code>{h(tx.code)}</code>\n"
        f"💵 Summa: <b>{money(tx.amount)}</b>\n"
        "\n"
        "Quyidagi tugma orqali Click sahifasiga o'ting. To'lov muvaffaqiyatli "
        "bo'lsa, bot avtomatik tasdiqlaydi.\n"
        "\n"
        "⚠️ Faqat Click tomonidan tasdiqlangan to'lov qabul qilinadi."
    )


INSUFFICIENT_BALANCE_TEXT = (
    "❌ <b>Balansingiz yetarli emas.</b>\n\n"
    "Balansni to'ldirish uchun admin bilan bog'laning yoki Click orqali to'lang."
)

PAYMENT_CHECK_PENDING_TEXT = (
    "⏳ <b>To'lov hali tasdiqlanmagan.</b>\n\n"
    "Agar to'lovni amalga oshirgan bo'lsangiz, 1-2 daqiqadan so'ng qayta tekshiring. "
    "Providerga to'lov tushgach, bot avtomatik xabar beradi."
)


def deal_paid_buyer_text(tx, seller) -> str:
    return (
        "✅ <b>TO'LOV TASDIQLANDI!</b>\n"
        "\n"
        f"📜 Tranzaksiya: <code>{h(tx.code)}</code>\n"
        f"📦 E'lon: <b>#{h(tx.account.public_id)}</b> — {h(tx.account.account_name)}\n"
        f"💵 To'langan summa: <b>{money(tx.amount)}</b>\n"
        "\n"
        f"🆔 Akkaunt ID: <code>{h(decrypt(tx.account.account_identifier_encrypted))}</code>\n"
        f"📞 Sotuvchi aloqasi: {h(decrypt(tx.account.contact_encrypted))}\n"
        f"👤 Sotuvchi: {visible_contact(seller)}\n"
        "\n"
        "📌 <b>Keyingi qadam:</b>\n"
        "1. Sotuvchi bilan bog'lanib, akkauntni xavfsiz usulda topshirishni kelishib oling.\n"
        "2. Akkaunt ma'lumotlarini tekshiring.\n"
        "3. Hammasi e'longa mos bo'lsa, <b>«Akkauntni oldim»</b> tugmasini bosing.\n"
        "\n"
        "⚠️ Botga parol, email paroli yoki SMS kodini yubormang. "
        "Muammo bo'lsa, «Muammo bor» tugmasi orqali nizo oching.\n"
        "\n"
        "Pul sotuvchiga siz tasdiqlaganingizdan keyingina o'tadi."
    )


def deal_paid_seller_text(tx, buyer) -> str:
    return (
        "💰 <b>XARIDOR TO'LOVNI AMALGA OSHIRDI!</b>\n"
        "\n"
        f"📜 Tranzaksiya: <code>{h(tx.code)}</code>\n"
        f"📦 E'lon: <b>#{h(tx.account.public_id)}</b> — {h(tx.account.account_name)}\n"
        f"💵 Xaridor to'ladi: <b>{money(tx.amount)}</b>\n"
        f"💰 Sizning daromadingiz: <b>{money(tx.seller_amount)}</b>\n"
        f"💸 Platforma komissiyasi: {money(tx.commission_amount)}\n"
        "\n"
        f"👤 Xaridor: {visible_contact(buyer)}\n"
        "\n"
        "📌 Akkauntni platforma qoidalariga mos, xavfsiz usulda topshiring. "
        "Xaridor tasdiqlagach, daromadingiz balansingizga qo'shiladi.\n"
        "\n"
        "⚠️ Botga parol, email paroli yoki SMS kodini yubormang."
    )


def deal_success_buyer_text(tx) -> str:
    return (
        "✅ <b>SAVDO MUVAFFAQIYATLI YAKUNLANDI!</b>\n"
        "\n"
        f"📜 Tranzaksiya: <code>{h(tx.code)}</code>\n"
        f"📦 #{h(tx.account.public_id)} — {h(tx.account.account_name)}\n"
        f"💵 Summa: <b>{money(tx.amount)}</b>\n"
        "\n"
        "Xaridingiz uchun rahmat! 🎉\n"
        "Sotuvchini baholab qo'ying — bu boshqa xaridorlarga yordam beradi."
    )


def deal_success_seller_text(tx) -> str:
    return (
        "🎉 <b>SAVDO YAKUNLANDI — PUL BALANSINGIZGA QO'SHILDI!</b>\n"
        "\n"
        f"📜 Tranzaksiya: <code>{h(tx.code)}</code>\n"
        f"📦 #{h(tx.account.public_id)} — {h(tx.account.account_name)}\n"
        f"💰 Hisobingizga qo'shildi: <b>{money(tx.seller_amount)}</b>\n"
        "\n"
        "Pulni yechib olish uchun admin bilan bog'laning.\n"
        "Xaridorni baholab qo'ying — reytingingiz oshadi."
    )


DEAL_CANCELLED_TEXT = (
    "❌ <b>Savdo bekor qilindi.</b>\n\n"
    "E'lon yana boshqa xaridorlar uchun faol holatga qaytarildi."
)

DEAL_ALREADY_PAID_TEXT = (
    "ℹ️ <b>Bu savdo allaqachon to'langan.</b>\n\n"
    "To'lovni bekor qilib bo'lmaydi. Muammo bo'lsa, nizo oching."
)


def dispute_opened_buyer_text(dispute, tx) -> str:
    return (
        "⚠️ <b>NIZO OCHILDI</b>\n"
        "\n"
        f"🆔 Nizo ID: <code>{h(dispute.code)}</code>\n"
        f"📜 Tranzaksiya: <code>{h(tx.code)}</code>\n"
        "\n"
        "Xaridor muammo haqida xabar berdi. Admin tez orada ko'rib chiqadi.\n"
        f"👤 Sotuvchi: {user_contact(tx.seller)}\n"
        "\n"
        "📸 Dalil (skrinshot, video yoki matn) yuboring. Dalillar admin panelida ko'rinadi.\n"
        "Savdo nizo yakunlanguncha to'xtatilgan."
    )


def dispute_opened_seller_text(dispute, tx) -> str:
    return (
        "⚠️ <b>XARIDOR NIZO OCHDI</b>\n"
        "\n"
        f"🆔 Nizo ID: <code>{h(dispute.code)}</code>\n"
        f"📜 Tranzaksiya: <code>{h(tx.code)}</code>\n"
        f"📦 #{h(tx.account.public_id)} — {h(tx.account.account_name)}\n"
        "\n"
        "Xaridor akkaunt e'longa mos kelmayotganini bildirgan.\n"
        "\n"
        "📸 O'z dalillaringizni yuboring: akkaunt topshirilgani, yozishmalar va h.k.\n"
        "Admin ikkala tomon dalillarini ko'rib chiqadi."
    )


DISPUTE_EVIDENCE_PROMPT = (
    "📸 <b>DALIL YUBORISH</b>\n\n"
    "Rasm, skrinshot yoki matn ko'rinishidagi dalillaringizni yuboring. "
    "Bir nechta xabar yuborishingiz mumkin.\n\n"
    "Tugatgach <b>«Dalillarni yuborish»</b> tugmasini bosing."
)

DISPUTE_EVIDENCE_SAVED = "✅ Dalillaringiz saqlandi. Admin nizoni ko'rib chiqadi."


def dispute_resolved_text(dispute, tx) -> str:
    if dispute.status == "RESOLVED_BUYER":
        decision = "Xaridor foydasiga"
        extra = (
            "To'lov xaridorga qaytariladi. Balans orqali to'langan bo'lsa, summa darhol "
            "balansga qaytariladi. Click orqali to'langan bo'lsa, qaytarish admin "
            "tomonidan amalga oshiriladi."
        )
    else:
        decision = "Sotuvchi foydasiga"
        extra = "Savdo muvaffaqiyatli yakunlandi va pul sotuvchiga o'tkazildi."
    return (
        "⚖️ <b>NIZO HAL QILINDI</b>\n"
        "\n"
        f"🆔 Nizo ID: <code>{h(dispute.code)}</code>\n"
        f"📜 Tranzaksiya: <code>{h(tx.code)}</code>\n"
        f"👨‍⚖️ Qaror: <b>{decision}</b>\n"
        f"📝 Izoh: {h(dispute.resolution_note or '—')}\n"
        "\n"
        f"{extra}"
    )


def review_success_text(rating: int) -> str:
    return (
        "⭐ <b>BAHO YUBORILDI!</b>\n\n"
        f"Reyting: {'⭐' * rating} ({rating}/5)\n"
        "Fikringiz uchun rahmat! Reyting boshqa foydalanuvchilarga yordam beradi."
    )


def profile_text(user, sold: int, bought: int) -> str:
    if getattr(user, "profile_consent", None) == PROFILE_ACCEPTED:
        profile_state = "✅ Ulashilgan"
    elif getattr(user, "profile_consent", None):
        profile_state = "🔐 Yashirin"
    else:
        profile_state = "⏳ Hali so'ralmagan"
    return (
        "👤 <b>PROFILIM</b>\n"
        "\n"
        f"🧑 Ism: <b>{h(user.full_name or '—')}</b>\n"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
        f"📎 Username: {('@' + h(user.username)) if user.username else '—'}\n"
        f"🔐 Profil holati: <b>{profile_state}</b>\n"
        f"💰 Balans: <b>{money(user.balance)}</b>\n"
        f"⭐ Reyting: {rating_text(user)}\n"
        "\n"
        f"📦 Sotilgan akkauntlar: <b>{sold}</b>\n"
        f"🛒 Sotib olingan akkauntlar: <b>{bought}</b>\n"
        f"📜 Jami savdolar: <b>{sold + bought}</b>\n"
        "\n"
        "🔐 Shaxsiy ma'lumotlaringiz boshqa foydalanuvchilarga faqat bitim doirasida "
        "va sizning roziligingiz bilan ko'rsatiladi."
    )


def my_listings_text(page: int, pages: int, total: int) -> str:
    return (
        "📦 <b>MENING E'LONLARIM</b>\n"
        "\n"
        f"Jami: <b>{total}</b> ta | Sahifa: <b>{page}/{pages}</b>\n"
        "\n"
        "E'lonni tanlang 👇"
    )


def my_listing_detail_text(account) -> str:
    return (
        f"📦 <b>#{h(account.public_id)}</b>\n"
        "\n"
        f"{h(platform_name(account.platform))}\n"
        f"🏷 {h(account.account_name)}\n"
        f"🏆 Daraja: {h(account.level)}\n"
        f"💰 Narx: <b>{money(account.price)}</b>\n"
        f"📌 Holat: <b>{h(account_status(account.status))}</b>\n"
        f"👁 Ko'rishlar: {account.views}\n"
        f"📅 Yaratilgan: {account.created_at.strftime('%d.%m.%Y') if account.created_at else '—'}\n"
        "\n"
        f"📝 {h(account.description)}"
    )


def history_text(page: int, pages: int) -> str:
    return (
        "📜 <b>SAVDO TARIXI</b>\n"
        "\n"
        f"Sahifa: <b>{page}/{pages}</b>\n\n"
        "Tranzaksiyani tanlab, tafsilotlarni ko'ring 👇"
    )


def history_item_line(tx, user_id: int) -> str:
    role = "🛒 Xaridor" if tx.buyer_id == user_id else "💰 Sotuvchi"
    return (
        f"<code>{h(tx.code)}</code>\n"
        f"📦 #{h(tx.account.public_id)} · {role}\n"
        f"💵 {money(tx.amount)} · {tx_status(tx.status)}"
    )


def transaction_detail_text(tx, user) -> str:
    role = "Xaridor" if tx.buyer_id == user.id else "Sotuvchi"
    counterpart = tx.seller if role == "Xaridor" else tx.buyer
    lines = [
        "📜 <b>TRANZAKSIYA TAFSILOTLARI</b>",
        "",
        f"🆔 Kod: <code>{h(tx.code)}</code>",
        f"📦 E'lon: <b>#{h(tx.account.public_id)}</b> — {h(tx.account.account_name)}",
        f"{h(platform_name(tx.account.platform))}",
        f"👤 Sizning rolingiz: <b>{role}</b>",
        f"👥 Ikkinchi tomon: {visible_contact(counterpart)}",
        "",
        f"💵 Summa: <b>{money(tx.amount)}</b>",
        f"💸 Komissiya: {money(tx.commission_amount)} ({num(tx.commission_rate)}%)",
        f"💰 Sotuvchi oladi: {money(tx.seller_amount)}",
        "",
        f"📌 Holat: <b>{tx_status(tx.status)}</b>",
        f"📅 Yaratilgan: {tx.created_at.strftime('%d.%m.%Y %H:%M') if tx.created_at else '—'}",
    ]
    if tx.completed_at:
        lines.append(f"✅ Yakunlangan: {tx.completed_at.strftime('%d.%m.%Y %H:%M')}")
    if tx.dispute:
        lines.append(f"⚠️ Nizo: <code>{h(tx.dispute.code)}</code> ({tx.dispute.status})")
    return "\n".join(lines)


def payments_text(page: int, pages: int) -> str:
    return (
        "💳 <b>TO'LOVLARIM</b>\n"
        "\n"
        f"Sahifa: <b>{page}/{pages}</b>\n\n"
        "Oxirgi to'lovlar ro'yxati 👇"
    )


def payment_line(payment) -> str:
    from bot.utils.formatting import payment_status

    return (
        f"<code>{h(payment.payment_uid)}</code>\n"
        f"💵 {money(payment.amount)} · {h(payment.provider.upper())}\n"
        f"📌 {payment_status(payment.status)}"
    )


def support_text(support_contact: str) -> str:
    return (
        "📞 <b>YORDAM</b>\n"
        "\n"
        "Savolingiz yoki muammoingiz bo'lsa, quyidagi manzil orqali bog'laning:\n"
        f"👤 Admin: <b>{h(support_contact)}</b>\n"
        "\n"
        "❓ <b>Ko'p beriladigan savollar:</b>\n"
        "• <b>To'lov qanday ishlaydi?</b> To'lovni payment provider tasdiqlaydi, "
        "shundan keyingina savdo davom etadi.\n"
        "• <b>Parolni botga yuborsam bo'ladimi?</b> Yo'q. Hech qachon maxfiy "
        "ma'lumotlarni botga yubormang.\n"
        "• <b>Akkaunt mos kelmasa?</b> «Muammo bor» tugmasi orqali nizo oching va "
        "dalillar yuboring.\n"
        "• <b>Pulni qanday yechaman?</b> Balansdagi pulni yechish uchun admin bilan "
        "bog'laning.\n"
        "\n"
        "Murojaat yuborish uchun quyidagi tugmani bosing 👇"
    )


SUPPORT_PROMPT = (
    "📩 <b>MUROJAAT YUBORISH</b>\n\n"
    "Savolingiz yoki muammoingizni bitta xabar ko'rinishida yozing. "
    "Admin tez orada javob beradi."
)

SUPPORT_SENT_TEXT = "✅ Murojaatingiz adminga yuborildi. Tez orada javob olasiz."

ERROR_TEXT = (
    "⚠️ <b>Kutilmagan xatolik yuz berdi.</b>\n\n"
    "Iltimos, birozdan so'ng qayta urinib ko'ring. Muammo davom etsa, /start bosib "
    "qaytadan boshlang yoki yordam bo'limiga murojaat qiling."
)

NO_STATE_TEXT = "ℹ️ Bu amal uchun avval kerakli bo'limni tanlang."
