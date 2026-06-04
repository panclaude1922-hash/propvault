"""
handlers/common.py — /start, выбор роли, смена роли (/changerole)
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command

from database import get_user, create_user, set_user_role, get_active_subscription
from keyboards import (
    kb_role_choice, kb_investor_main, kb_realtor_main,
    kb_admin_main, kb_change_role, kb_confirm_role_change, kb_plans
)
from config import WEBAPP_URL, ADMIN_IDS

router = Router()

ROLE_LABELS = {
    "investor": "👤 Инвестор",
    "realtor":  "🏢 Риелтор",
    "admin":    "👮 Модератор",
}


# ── /start ───────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    tg_id = message.from_user.id
    user = await get_user(tg_id)

    if not user:
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


# ── Выбор роли при регистрации ───────────────────────────

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
            "✅ <b>Вы зарегистрированы как инвестор.</b>\n\n"
            "Вход в каталог объектов бесплатный.",
            parse_mode="HTML"
        )
        await call.message.answer(
            "🏠 Открывайте PropVault:",
            reply_markup=kb_investor_main(WEBAPP_URL)
        )
    elif role == "realtor":
        await call.message.edit_text(
            "✅ <b>Вы зарегистрированы как риелтор.</b>\n\n"
            "Для размещения объектов нужна подписка.",
            parse_mode="HTML"
        )
        await call.message.answer(
            "Выберите тариф:",
            reply_markup=kb_plans()
        )

    await call.answer()


# ── /changerole — смена роли ─────────────────────────────

@router.message(Command("changerole"))
async def cmd_change_role(message: Message):
    tg_id = message.from_user.id
    user = await get_user(tg_id)

    if not user:
        await message.answer("Сначала зарегистрируйтесь — напишите /start")
        return

    if user["role"] == "admin":
        await message.answer("👮 Роль модератора нельзя изменить.")
        return

    current_label = ROLE_LABELS.get(user["role"], user["role"])
    await message.answer(
        f"Ваша текущая роль: <b>{current_label}</b>\n\n"
        "На кого хотите переключиться?",
        parse_mode="HTML",
        reply_markup=kb_change_role(user["role"])
    )


# Также вызывается из меню кнопкой
@router.message(F.text == "🔄 Сменить роль")
async def btn_change_role(message: Message):
    await cmd_change_role(message)


@router.callback_query(F.data.startswith("changerole:"))
async def change_role_confirm(call: CallbackQuery):
    new_role = call.data.split(":")[1]
    tg_id = call.from_user.id
    user = await get_user(tg_id)

    if not user:
        await call.answer("Сначала зарегистрируйтесь.", show_alert=True)
        return

    if user["role"] == "admin":
        await call.answer("Роль модератора нельзя изменить.", show_alert=True)
        return

    role_labels = {"investor": "инвестора", "realtor": "риелтора"}
    current_label = ROLE_LABELS.get(user["role"], user["role"])
    new_label = role_labels.get(new_role, new_role)

    warn = ""
    if user["role"] == "realtor" and new_role == "investor":
        sub = await get_active_subscription(tg_id)
        if sub:
            warn = (
                "\n\n⚠️ <b>Внимание:</b> у вас активная подписка "
                f"<b>{sub['plan'].upper()}</b> до {sub['expires_at'][:10]}.\n"
                "Ваши объекты останутся в базе, но будут скрыты."
            )

    await call.message.edit_text(
        f"Текущая роль: <b>{current_label}</b>\n"
        f"Новая роль: <b>{ROLE_LABELS.get(new_role, new_role)}</b>"
        f"{warn}\n\nПодтвердить смену?",
        parse_mode="HTML",
        reply_markup=kb_confirm_role_change(new_role)
    )
    await call.answer()


@router.callback_query(F.data.startswith("confirmrole:"))
async def confirm_role_change(call: CallbackQuery):
    new_role = call.data.split(":")[1]
    tg_id = call.from_user.id

    user = await get_user(tg_id)
    if not user or user["role"] == "admin":
        await call.answer("Невозможно изменить роль.", show_alert=True)
        return

    await set_user_role(tg_id, new_role)

    await call.message.edit_text(
        f"✅ Роль изменена на <b>{ROLE_LABELS.get(new_role, new_role)}</b>",
        parse_mode="HTML"
    )

    if new_role == "investor":
        await call.message.answer(
            "🏠 Теперь вы инвестор. Открывайте каталог объектов:",
            reply_markup=kb_investor_main(WEBAPP_URL)
        )
    elif new_role == "realtor":
        sub = await get_active_subscription(tg_id)
        if sub:
            from keyboards import kb_realtor_main
            await call.message.answer(
                "🏢 Добро пожаловать обратно как риелтор!",
                reply_markup=kb_realtor_main(WEBAPP_URL)
            )
        else:
            await call.message.answer(
                "🏢 Теперь вы риелтор. Выберите тариф для размещения объектов:",
                reply_markup=kb_plans()
            )

    await call.answer("Роль изменена!")


@router.callback_query(F.data == "cancel")
async def cancel_action(call: CallbackQuery):
    await call.message.edit_text("✖️ Отменено.")
    await call.answer()
