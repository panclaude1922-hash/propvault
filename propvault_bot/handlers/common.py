"""
handlers/common.py — /start (первый вход), выбор роли
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

from database import get_user, create_user, set_user_role, get_active_subscription
from keyboards import kb_role_choice, kb_investor_main, kb_realtor_main
from config import WEBAPP_URL, ADMIN_IDS

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    tg_id = message.from_user.id
    user = await get_user(tg_id)

    # Новый пользователь
    if not user:
        # Если это администратор — сразу регистрируем как admin
        if tg_id in ADMIN_IDS:
            await create_user(
                tg_id,
                message.from_user.username,
                message.from_user.full_name,
                role="admin"
            )
            from handlers.admin import cmd_start_admin
            return await cmd_start_admin(message)

        await message.answer(
            f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
            "Добро пожаловать в <b>PropVault</b> —\n"
            "платформу инвестиций в российскую недвижимость.\n\n"
            "Кто вы?",
            parse_mode="HTML",
            reply_markup=kb_role_choice()
        )
        return

    # Существующий пользователь — перенаправляем
    role = user["role"]
    if role == "admin":
        from handlers.admin import cmd_start_admin
        return await cmd_start_admin(message)
    elif role == "realtor":
        from handlers.realtor import cmd_start_realtor
        return await cmd_start_realtor(message)
    else:
        from handlers.investor import cmd_start_investor
        return await cmd_start_investor(message)


@router.callback_query(F.data.startswith("role:"))
async def set_role(call: CallbackQuery):
    role = call.data.split(":")[1]
    tg_id = call.from_user.id

    await create_user(
        tg_id,
        call.from_user.username,
        call.from_user.full_name,
        role=role
    )

    if role == "investor":
        await call.message.edit_text(
            "✅ <b>Отлично! Вы зарегистрированы как инвестор.</b>\n\n"
            "Вход в каталог объектов бесплатный.\n"
            "Нажмите кнопку ниже, чтобы открыть приложение.",
            parse_mode="HTML"
        )
        await call.message.answer(
            "🏠 Открывайте PropVault и находите объекты для инвестиций:",
            reply_markup=kb_investor_main(WEBAPP_URL)
        )

    elif role == "realtor":
        await call.message.edit_text(
            "✅ <b>Отлично! Вы зарегистрированы как риелтор.</b>\n\n"
            "Для размещения объектов нужна подписка.\n"
            "Выберите подходящий тариф:",
            parse_mode="HTML"
        )
        from keyboards import kb_plans
        await call.message.answer(
            "Выберите тариф для начала работы:",
            reply_markup=kb_plans()
        )

    await call.answer()
