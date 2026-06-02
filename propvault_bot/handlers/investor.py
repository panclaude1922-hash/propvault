"""
handlers/investor.py — команды и кнопки для инвесторов
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from database import get_user
from keyboards import kb_investor_main
from config import WEBAPP_URL

router = Router()


@router.message(Command("start"))
async def cmd_start_investor(message: Message):
    user = await get_user(message.from_user.id)
    if not user or user["role"] != "investor":
        return  # обрабатывается в общем хендлере

    name = message.from_user.first_name
    await message.answer(
        f"👋 Привет, {name}!\n\n"
        "Добро пожаловать в <b>PropVault</b> — платформу инвестиций\n"
        "в российскую недвижимость.\n\n"
        "🏠 Нажмите кнопку ниже, чтобы открыть каталог объектов.\n"
        "Вход для инвесторов <b>полностью бесплатный</b>.",
        parse_mode="HTML",
        reply_markup=kb_investor_main(WEBAPP_URL)
    )


@router.message(F.text == "ℹ️ Как это работает")
async def how_it_works(message: Message):
    await message.answer(
        "<b>Как работает PropVault:</b>\n\n"
        "1️⃣ Просматривайте объекты недвижимости от проверенных риелторов\n"
        "2️⃣ Изучайте доходность, сроки и детали каждого проекта\n"
        "3️⃣ Нажмите «Показать контакт» — получите телефон и email риелтора\n"
        "4️⃣ Свяжитесь напрямую и договоритесь об инвестиции\n\n"
        "💡 Все объекты проходят модерацию перед публикацией.\n"
        "Связь с риелтором и сделки — вне приложения.",
        parse_mode="HTML",
        reply_markup=kb_investor_main(WEBAPP_URL)
    )
