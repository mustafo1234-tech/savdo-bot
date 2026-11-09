from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, ErrorEvent

from bot.config import Config, get_config, load_config
from bot.database.session import (
    create_engine_and_session,
    create_tables,
    ensure_schema_compatibility,
)
from bot.handlers import admin, buyer, deals, menu, seller, support
from bot.handlers import start as start_handler
from bot.logging_config import setup_logging
from bot.middlewares.database import DatabaseMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.middlewares.user import UserMiddleware
from bot.services.settings import ensure_default_settings
from bot.texts import ERROR_TEXT
from bot.web import start_web

logger = logging.getLogger(__name__)


def _register_middlewares(dp: Dispatcher, session_factory) -> None:
    config = get_config()
    throttle = ThrottlingMiddleware(config.throttle_limit, config.throttle_window)
    database = DatabaseMiddleware(session_factory)
    user = UserMiddleware(session_factory)

    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(throttle)
        observer.outer_middleware(database)
        observer.outer_middleware(user)


def _register_routers(dp: Dispatcher) -> None:
    dp.include_router(start_handler.router)
    dp.include_router(menu.router)
    dp.include_router(support.router)
    dp.include_router(seller.router)
    dp.include_router(buyer.router)
    dp.include_router(deals.router)
    dp.include_router(admin.router)


async def _set_commands(bot: Bot, config: Config) -> None:
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Boshlash / asosiy menyu"),
                BotCommand(command="menu", description="Asosiy menyu"),
                BotCommand(command="help", description="Yordam"),
            ]
        )
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Boshlash"),
                BotCommand(command="menu", description="Asosiy menyu"),
                BotCommand(command="admin", description="Admin panel"),
                BotCommand(command="help", description="Yordam"),
            ],
            scope=BotCommandScopeChat(chat_id=config.owner_id),
        )
    except Exception:  # noqa: BLE001
        logger.warning("Bot buyruqlarini o'rnatishda xatolik (owner chat topilmagan bo'lishi mumkin).")


def _error_user_id(event: ErrorEvent) -> int | None:
    update = event.update
    if update.message and update.message.from_user:
        return update.message.from_user.id
    if update.callback_query and update.callback_query.from_user:
        return update.callback_query.from_user.id
    return None


async def run() -> None:
    config = load_config()
    setup_logging(config.log_level)
    logger.info("Game Marketplace bot ishga tushmoqda... (owner sozlangan)")

    engine, session_factory = create_engine_and_session()
    bot: Bot | None = None
    web_runner = None
    try:
        if config.auto_create_tables:
            await create_tables(engine)
            logger.info("Database jadvallari tekshirildi/yaratildi.")
        await ensure_schema_compatibility(engine)

        async with session_factory() as session:
            await ensure_default_settings(session, config)

        bot = Bot(
            token=config.bot_token,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
                link_preview_is_disabled=True,
            ),
        )
        dp = Dispatcher(storage=MemoryStorage())
        _register_middlewares(dp, session_factory)
        _register_routers(dp)

        @dp.error()
        async def global_error_handler(event: ErrorEvent) -> None:
            logger.error(
                "Kutilmagan xatolik: %s",
                event.exception,
                exc_info=(type(event.exception), event.exception, event.exception.__traceback__),
            )
            user_id = _error_user_id(event)
            if user_id:
                try:
                    await bot.send_message(user_id, ERROR_TEXT)
                except Exception:  # noqa: BLE001
                    logger.debug("Xatolik xabarini yuborib bo'lmadi.")

        web_runner = await start_web(bot, session_factory, config)
        await _set_commands(bot, config)
        try:
            await bot.delete_webhook(drop_pending_updates=True)
        except Exception:  # noqa: BLE001
            logger.warning("Telegram webhook'ni o'chirishda xatolik.")

        logger.info("Polling boshlandi.")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if web_runner is not None:
            try:
                await web_runner.cleanup()
            except Exception:  # noqa: BLE001
                logger.debug("Web server to'xtatishda xatolik.")
        if bot is not None:
            try:
                await bot.session.close()
            except Exception:  # noqa: BLE001
                logger.debug("Bot sessiyasini yopishda xatolik.")
        await engine.dispose()
        logger.info("Bot to'xtatildi.")


def start() -> None:
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        pass
