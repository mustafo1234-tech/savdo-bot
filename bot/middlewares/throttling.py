from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

logger = logging.getLogger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    """Bir foydalanuvchidan keladigan so'rovlarni cheklaydi (flood himoyasi)."""

    def __init__(self, limit: int = 8, window: float = 3.0) -> None:
        self.limit = max(1, limit)
        self.window = max(0.5, window)
        self._history: dict[int, deque[float]] = defaultdict(deque)
        self._notified: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user") or getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        now = time.monotonic()
        history = self._history[user.id]
        while history and now - history[0] > self.window:
            history.popleft()

        if len(history) >= self.limit:
            if now - self._notified.get(user.id, 0) > self.window:
                self._notified[user.id] = now
                text = "⏳ Juda ko'p so'rov yubordingiz. Iltimos, biroz kutib turing."
                try:
                    if isinstance(event, CallbackQuery):
                        await event.answer(text, show_alert=True)
                    elif isinstance(event, Message):
                        await event.answer(text)
                except Exception:  # noqa: BLE001
                    logger.debug("Throttling xabari yuborilmadi.")
            return None

        history.append(now)
        return await handler(event, data)
