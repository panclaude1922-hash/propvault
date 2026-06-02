"""
main_api.py — запускает бота и API одновременно
Бот работает через polling, API через uvicorn на порту 8000
"""

import asyncio
import logging
import os

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import common, investor, realtor, admin
from api import app as fastapi_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def run_bot():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(realtor.router)
    dp.include_router(investor.router)
    logger.info("Бот запущен")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


async def run_api():
    port = int(os.getenv("PORT", 8000))
    config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    logger.info(f"API запущен на порту {port}")
    await server.serve()


async def main():
    await init_db()
    logger.info("База данных инициализирована")
    # Запускаем бота и API параллельно
    await asyncio.gather(
        run_bot(),
        run_api()
    )


if __name__ == "__main__":
    asyncio.run(main())
