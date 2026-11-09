from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from bot.config import get_config


class IsOwner(BaseFilter):
    async def __call__(self, event: TelegramObject, **kwargs) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and user.id == get_config().owner_id)
