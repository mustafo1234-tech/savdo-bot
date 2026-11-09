from __future__ import annotations

PLATFORMS: dict[str, str] = {
    "pubg": "🎮 PUBG Mobile",
    "standoff": "🎮 Standoff 2",
    "brawl": "🎮 Brawl Stars",
    "cs2": "🎮 CS2",
    "steam": "🎮 Steam",
    "instagram": "📸 Instagram",
}

PAYOUT_METHODS: dict[str, str] = {
    "click": "💳 Click",
    "other": "🏦 Boshqa qo'llab-quvvatlanadigan usul",
}

ACCOUNT_STATUSES: dict[str, str] = {
    "PENDING": "🕓 Tekshiruvda",
    "ACTIVE": "✅ Faol",
    "RESERVED": "🔒 Band qilindi",
    "SOLD": "🤝 Sotilgan",
    "INACTIVE": "⏸ Faoliyatsiz",
    "BLOCKED": "🚫 Bloklangan",
    "REJECTED": "❌ Rad etilgan",
}

TRANSACTION_STATUSES: dict[str, str] = {
    "PENDING": "⏳ Kutilmoqda",
    "PAID": "💳 To'lov qilindi",
    "VERIFYING": "🔍 Tekshirilmoqda",
    "SUCCESS": "✅ Muvaffaqiyatli",
    "CANCELLED": "❌ Bekor qilindi",
    "DISPUTE": "⚠️ Nizo mavjud",
}

PAYMENT_STATUSES: dict[str, str] = {
    "CREATED": "🕓 Yaratildi",
    "PENDING": "⏳ Kutilmoqda",
    "PAID": "✅ To'landi",
    "FAILED": "❌ Muvaffaqiyatsiz",
    "REFUNDED": "↩️ Qaytarildi",
    "REFUND_PENDING": "⏳ Qaytarish kutilmoqda",
}

DISPUTE_STATUSES: dict[str, str] = {
    "OPEN": "⚠️ Ochiq",
    "RESOLVED_BUYER": "↩️ Xaridor foydasiga hal qilindi",
    "RESOLVED_SELLER": "✅ Sotuvchi foydasiga hal qilindi",
    "CLOSED": "🔒 Yopilgan",
}

ACTIVE_TRANSACTION_STATUSES = ("PENDING", "PAID", "VERIFYING", "DISPUTE")

DEFAULT_SETTINGS = {
    "commission_percent": "10",
    "min_price": "5000",
    "maintenance": "false",
    "support_contact": "@support",
    "auto_approve": "true",
}

PROFILE_ACCEPTED = "accepted"
PROFILE_DECLINED = "declined"

CALLBACK_CANCEL = "cancel"
CALLBACK_HOME = "menu:home"
