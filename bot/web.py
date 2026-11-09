from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot
from aiohttp import web
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import Config
from bot.services.deals import notify_deal_paid
from bot.services.payments import process_click_complete, process_click_prepare

logger = logging.getLogger(__name__)


async def _health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "game-marketplace-bot"})


async def _read_payload(request: web.Request) -> dict[str, Any]:
    content_type = request.content_type or ""
    if "application/json" in content_type:
        raw = await request.json()
        if isinstance(raw, dict):
            return {str(k): str(v) for k, v in raw.items()}
        return {}
    post = await request.post()
    return {str(k): str(v) for k, v in post.items()}


async def _notify_paid(
    bot: Bot,
    session: AsyncSession,
    transaction_id: int | None,
    newly_paid: bool,
) -> None:
    if not newly_paid or transaction_id is None:
        return
    try:
        await notify_deal_paid(bot, session, transaction_id)
    except Exception:
        logger.exception("Click to'lovi bildirishnomalarini yuborishda xatolik (tx=%s).", transaction_id)


async def _click_prepare(request: web.Request) -> web.Response:
    config: Config = request.app["config"]
    session_factory: async_sessionmaker[AsyncSession] = request.app["session_factory"]
    try:
        data = await _read_payload(request)
        async with session_factory() as session:
            result = await process_click_prepare(session, data, config)
        return web.json_response(result)
    except Exception:
        logger.exception("Click prepare ichki xatosi.")
        return web.json_response({"error": -8, "error_note": "Internal error"})


async def _click_complete(request: web.Request) -> web.Response:
    config: Config = request.app["config"]
    session_factory: async_sessionmaker[AsyncSession] = request.app["session_factory"]
    bot: Bot = request.app["bot"]
    try:
        data = await _read_payload(request)
        async with session_factory() as session:
            result, transaction_id, newly_paid = await process_click_complete(session, data, config)
            await _notify_paid(bot, session, transaction_id, newly_paid)
        return web.json_response(result)
    except Exception:
        logger.exception("Click complete ichki xatosi.")
        return web.json_response({"error": -8, "error_note": "Internal error"})


async def _click_callback(request: web.Request) -> web.Response:
    try:
        data = await _read_payload(request)
    except Exception:  # noqa: BLE001
        return web.json_response({"error": -8, "error_note": "Bad payload"})
    action = str(data.get("action", "")).strip()
    if action in {"0", "0.0"}:
        return await _click_prepare_from_data(request, data)
    if action in {"1", "1.0"}:
        return await _click_complete_from_data(request, data)
    return web.json_response({"error": -3, "error_note": "Action not found"})


async def _click_prepare_from_data(request: web.Request, data: dict[str, Any]) -> web.Response:
    config: Config = request.app["config"]
    session_factory: async_sessionmaker[AsyncSession] = request.app["session_factory"]
    try:
        async with session_factory() as session:
            result = await process_click_prepare(session, data, config)
        return web.json_response(result)
    except Exception:
        logger.exception("Click prepare (callback) ichki xatosi.")
        return web.json_response({"error": -8, "error_note": "Internal error"})


async def _click_complete_from_data(request: web.Request, data: dict[str, Any]) -> web.Response:
    config: Config = request.app["config"]
    session_factory: async_sessionmaker[AsyncSession] = request.app["session_factory"]
    bot: Bot = request.app["bot"]
    try:
        async with session_factory() as session:
            result, transaction_id, newly_paid = await process_click_complete(session, data, config)
            await _notify_paid(bot, session, transaction_id, newly_paid)
        return web.json_response(result)
    except Exception:
        logger.exception("Click complete (callback) ichki xatosi.")
        return web.json_response({"error": -8, "error_note": "Internal error"})


async def start_web(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    config: Config,
) -> web.AppRunner:
    app = web.Application(client_max_size=1024 * 1024)
    app["bot"] = bot
    app["config"] = config
    app["session_factory"] = session_factory

    app.router.add_get("/", _health)
    app.router.add_get("/health", _health)
    app.router.add_post("/click/prepare", _click_prepare)
    app.router.add_post("/click/complete", _click_complete)
    app.router.add_post("/click/callback", _click_callback)

    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, config.web_host, config.web_port)
    await site.start()
    logger.info("Web server %s:%s portida ishga tushdi.", config.web_host, config.web_port)
    return runner
