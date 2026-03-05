"""
Точка входа — запускает бот и API сервер параллельно
"""
import asyncio
import logging
import os
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def run_bot():
    # Import here so a missing BOT_TOKEN raises with a clear message,
    # not a silent crash during module-level import
    from bot import bot, dp
    logger.info("Starting Telegram bot polling...")
    await dp.start_polling(bot)


async def run_api():
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting API server on port {port}...")
    config = uvicorn.Config(
        "api:app",          # import string so uvicorn manages lifespan correctly
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    # Start API first and give it a moment to bind the port.
    # Railway healthcheck hits /health — it must be up before the bot starts.
    api_task = asyncio.create_task(run_api())
    await asyncio.sleep(2)

    bot_task = asyncio.create_task(run_bot())

    # Surface the first exception instead of hanging forever
    done, pending = await asyncio.wait(
        [api_task, bot_task],
        return_when=asyncio.FIRST_EXCEPTION,
    )

    for task in done:
        exc = task.exception()
        if exc:
            logger.error(f"Task failed: {exc}", exc_info=exc)
            for p in pending:
                p.cancel()
            raise exc

    await asyncio.gather(*pending)


if __name__ == "__main__":
    asyncio.run(main())
