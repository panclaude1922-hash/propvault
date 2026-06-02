"""
main.py — точка входа, регистрация роутеров, запуск поллинга
"""
 
import asyncio
import logging
 
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
 
from config import BOT_TOKEN
from database import init_db
from handlers import common, investor, realtor, admin
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)
 
 
async def main():
    # инициализируем БД
    await init_db()
    logger.info("База данных инициализирована")
 
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
 
    # Порядок роутеров важен:
    # common — первым (обрабатывает /start для новых пользователей)
    # admin — раньше investor/realtor (чтобы /start для админов не попал в другие хендлеры)
    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(realtor.router)
    dp.include_router(investor.router)
 
    logger.info("Запуск бота PropVault...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
 
 
if __name__ == "__main__":
    asyncio.run(main())
