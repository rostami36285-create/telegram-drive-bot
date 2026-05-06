"""Entry point: Telegram bot (polling) + FastAPI OAuth callback server."""
import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from telegram.ext import Application

from config import TELEGRAM_BOT_TOKEN, SERVER_HOST, SERVER_PORT
from database.db import init_db
from bot.handlers import register
from services.queue import UploadQueue
from oauth.server import create_router

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_bot_app: Application | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _bot_app

    await init_db()
    logger.info("Database initialized")

    queue = UploadQueue()
    _bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    _bot_app.bot_data["upload_queue"] = queue

    register(_bot_app)

    await _bot_app.initialize()
    await _bot_app.start()

    asyncio.create_task(queue.start(_bot_app.bot))
    asyncio.create_task(_bot_app.updater.start_polling(drop_pending_updates=True))
    logger.info("Bot started (polling mode)")

    yield

    logger.info("Shutting down...")
    await _bot_app.updater.stop()
    await _bot_app.stop()
    await _bot_app.shutdown()


web = FastAPI(lifespan=lifespan, title="Telegram Drive Bot")
web.include_router(create_router(lambda: _bot_app))


if __name__ == "__main__":
    uvicorn.run(web, host=SERVER_HOST, port=SERVER_PORT, log_level="info")
