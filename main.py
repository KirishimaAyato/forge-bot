"""
Точка входа — запускает бот и API сервер параллельно
"""
import asyncio
import logging
import os
import uvicorn
from bot import bot, dp, db as bot_db
from api import app, db as api_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def run_bot():
    logger.info("Starting Telegram bot...")
    await dp.start_polling(bot)


async def run_api():
    logger.info("Starting API server on port 8000...")
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    # Init DB once
    await bot_db.init()
    logger.info("Database initialized")

    # Run bot and API server concurrently
    await asyncio.gather(
        run_bot(),
        run_api(),
    )


if __name__ == "__main__":
    asyncio.run(main())
