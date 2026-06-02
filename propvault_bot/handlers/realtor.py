"""
handlers/realtor.py — регистрация риелтора, подписка, добавление объектов
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import (
    get_user, get_active_subscription, create_subscription,
    get_property_count, create_property, get_realtor_properties,
    PLAN_LIMITS, PLAN_PRICES, PLAN_LABELS
)
from keyboards import (
    kb_realtor_main, kb_plans, kb_confirm_plan,
    kb_property_actions, kb_cancel
)
from config import WEBAPP_URL, ADMIN_IDS
from utils import notify_admins_new_property

router = Router()


# ── FSM: добавление объекта ──────────────────────────────

class AddProperty(StatesGroup):
    title       = State()
    region      = State()
    city        = State()
    yield_pct   = State()
    min_entry   = State()
    goal_amount = State()
    deadline    = State()
    description = State()
    phone       = State()
    email       = State()
    confirm     = State()


# ── СТАРТ / ГЛАВНОЕ МЕНЮ ─────────────────────────────────

@router.message(Command("start"))
async def cmd_start_realtor(message: Message):
    user = await get_user(message.from_user.id)
    if not user or user["role"] != "realtor":
        return

    sub = await get_active_subscription(message.from_user.id)
    if sub:
        plan_label = PLAN_LABELS.get(sub["plan"], sub["plan"])
        await message.answer(
            f"👋 Добро пожаловать, <b>{message.from_user.first_name}</b>!\n\n"
            f"Тариф: <b>{plan_label}</b> · действует до <b>{sub['expires_at'][:10]}</b>\n\n"
            "Используйте меню для управления объектами.",
            parse_mode="HTML",
            reply_markup=kb_realtor_main(WEBAPP_URL)
        )
    else:
        await message.answer(
            f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
            "Для размещения объектов нужна подписка.\n"
            "Выберите тариф:",
            parse_mode="HTML",
            reply_markup=kb_plans()
        )


# ── ТАРИФЫ ──────────────────────────────────────────────

@router.message(F.text == "💳 Мой тариф")
async def my_plan(message: Message):
    sub = await get_active_subscription(message.from_user.id)
    if not sub:
        await message.answer(
            "У вас нет активной подписки.\nВыберите тариф:",
            reply_markup=kb_plans()
        )
        return

    plan = sub["plan"]
    limit = PLAN_LIMITS[plan]
    count = await get_property_count(message.from_user.id)
    limit_str = "∞" if limit > 100 else str(limit)

    await message.answer(
        f"<b>Ваш тариф: {PLAN_LABELS[plan]}</b>\n\n"
        f"📅 Активен до: <b>{sub['expires_at'][:10]}</b>\n"
        f"🏠 Объектов: <b>{count} / {limit_str}</b>\n\n"
        "Для смены тарифа:",
        parse_mode="HTML",
        reply_markup=kb_plans()
    )


@router.callback_query(F.data.startswith("plan:"))
async def select_plan(call: CallbackQuery):
    plan = call.data.split(":")[1]
    price = PLAN_PRICES[plan]
    label = PLAN_LABELS[plan]
    limit = PLAN_LIMITS[plan]
    limit_str = "∞" if limit > 100 else str(limit)

    await call.message.edit_text(
        f"<b>Тариф {label}</b>\n\n"
        f"💰 Стоимость: <b>₽{price:,}/мес</b>\n"
        f"🏠 Объектов: <b>{limit_str}</b>\n\n"
        "⚠️ Сейчас используется тестовая оплата.\n"
        "В продакшне подключите ЮKassa или Telegram Stars.",
        parse_mode="HTML",
        reply_markup=kb_confirm_plan(plan, price)
    )
    await call.answer()


@router.callback_query(F.data == "back:plans")
async def back_to_plans(call: CallbackQuery):
    await call.message.edit_text("Выберите тариф:", reply_markup=kb_plans())
    await call.answer()


@router.callback_query(F.data.startswith("confirm_plan:"))
async def confirm_plan(call: CallbackQuery):
    plan = call.data.split(":")[1]
    result = await create_subscription(call.from_user.id, plan)
    label = PLAN_LABELS[plan]

    await call.message.edit_text(
        f"✅ <b>Подписка {label} активирована!</b>\n\n"
        f"Действует до: <b>{result['expires_at']}</b>\n\n"
        "Теперь вы можете добавлять объекты.",
        parse_mode="HTML"
    )
    await call.message.answer(
        "Используйте меню для работы с объектами.",
        reply_markup=kb_realtor_main(WEBAPP_URL)
    )
    await call.answer("Подписка активирована!")


# ── МОИ ОБЪЕКТЫ ─────────────────────────────────────────

@router.message(F.text == "📋 Мои объекты")
async def my_properties(message: Message):
    props = await get_realtor_properties(message.from_user.id)
    if not props:
        await message.answer(
            "У вас пока нет объектов.\n\nНажмите «➕ Добавить объект» для размещения.",
            reply_markup=kb_realtor_main(WEBAPP_URL)
        )
        return

    status_icons = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
    status_labels = {"pending": "На модерации", "approved": "Опубликован", "rejected": "Отклонён"}

    for p in props:
        icon = status_icons.get(p["status"], "❓")
        label = status_labels.get(p["status"], p["status"])
        text = (
            f"{icon} <b>{p['title']}</b>\n"
            f"📍 {p['city']}, {p['region']}\n"
            f"📈 {p['yield_pct']}% · от ₽{p['min_entry']:,}\n"
            f"📌 Статус: <b>{label}</b>"
        )
        if p["status"] == "rejected" and p.get("reject_reason"):
            text += f"\n💬 Причина: {p['reject_reason']}"

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=kb_property_actions(p["id"], p["status"])
        )


# ── ДОБАВИТЬ ОБЪЕКТ (FSM) ────────────────────────────────

@router.message(F.text == "➕ Добавить объект")
async def start_add_property(message: Message, state: FSMContext):
    # проверка подписки
    sub = await get_active_subscription(message.from_user.id)
    if not sub:
        await message.answer("❌ Для добавления объектов нужна активная подписка.", reply_markup=kb_plans())
        return

    # проверка лимита
    plan = sub["plan"]
    limit = PLAN_LIMITS[plan]
    count = await get_property_count(message.from_user.id)
    if count >= limit:
        await message.answer(
            f"❌ Достигнут лимит объектов для тарифа <b>{PLAN_LABELS[plan]}</b> ({limit} шт.).\n\n"
            "Обновите тариф или удалите существующий объект.",
            parse_mode="HTML",
            reply_markup=kb_plans()
        )
        return

    await state.set_state(AddProperty.title)
    await message.answer(
        "📝 <b>Добавление нового объекта</b>\n\n"
        "Шаг 1/10 — Введите <b>название объекта</b>:\n"
        "<i>Пример: Жилой комплекс Горки Парк</i>",
        parse_mode="HTML",
        reply_markup=kb_cancel()
    )


@router.message(AddProperty.title)
async def ap_title(message: Message, state: FSMContext):
    if len(message.text) < 3:
        await message.answer("Слишком короткое название. Попробуйте ещё раз:")
        return
    await state.update_data(title=message.text.strip())
    await state.set_state(AddProperty.region)
    await message.answer(
        "Шаг 2/10 — <b>Регион / область:</b>\n"
        "<i>Пример: Московская область</i>",
        parse_mode="HTML"
    )


@router.message(AddProperty.region)
async def ap_region(message: Message, state: FSMContext):
    await state.update_data(region=message.text.strip())
    await state.set_state(AddProperty.city)
    await message.answer(
        "Шаг 3/10 — <b>Город:</b>\n<i>Пример: Москва</i>",
        parse_mode="HTML"
    )


@router.message(AddProperty.city)
async def ap_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await state.set_state(AddProperty.yield_pct)
    await message.answer(
        "Шаг 4/10 — <b>Годовая доходность, %:</b>\n<i>Пример: 11.5</i>",
        parse_mode="HTML"
    )


@router.message(AddProperty.yield_pct)
async def ap_yield(message: Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        if not (0.1 <= val <= 50):
            raise ValueError
    except ValueError:
        await message.answer("Введите число от 0.1 до 50, например: 11.5")
        return
    await state.update_data(yield_pct=val)
    await state.set_state(AddProperty.min_entry)
    await message.answer(
        "Шаг 5/10 — <b>Минимальный вход, ₽:</b>\n<i>Пример: 1500000</i>",
        parse_mode="HTML"
    )


@router.message(AddProperty.min_entry)
async def ap_min_entry(message: Message, state: FSMContext):
    try:
        val = int(message.text.replace(" ", "").replace(",", ""))
        if val < 1000:
            raise ValueError
    except ValueError:
        await message.answer("Введите сумму в рублях, например: 1500000")
        return
    await state.update_data(min_entry=val)
    await state.set_state(AddProperty.goal_amount)
    await message.answer(
        "Шаг 6/10 — <b>Цель сбора, ₽:</b>\n<i>Пример: 25000000</i>",
        parse_mode="HTML"
    )


@router.message(AddProperty.goal_amount)
async def ap_goal(message: Message, state: FSMContext):
    try:
        val = int(message.text.replace(" ", "").replace(",", ""))
        if val < 10000:
            raise ValueError
    except ValueError:
        await message.answer("Введите сумму в рублях, например: 25000000")
        return
    await state.update_data(goal_amount=val)
    await state.set_state(AddProperty.deadline)
    await message.answer(
        "Шаг 7/10 — <b>Срок сдачи:</b>\n<i>Пример: Q3 2026</i>",
        parse_mode="HTML"
    )


@router.message(AddProperty.deadline)
async def ap_deadline(message: Message, state: FSMContext):
    await state.update_data(deadline=message.text.strip())
    await state.set_state(AddProperty.description)
    await message.answer(
        "Шаг 8/10 — <b>Описание объекта</b> (минимум 30 символов):",
        parse_mode="HTML"
    )


@router.message(AddProperty.description)
async def ap_description(message: Message, state: FSMContext):
    if len(message.text) < 30:
        await message.answer("Описание слишком короткое (минимум 30 символов). Расскажите подробнее:")
        return
    await state.update_data(description=message.text.strip())
    await state.set_state(AddProperty.phone)
    await message.answer(
        "Шаг 9/10 — <b>Ваш телефон для инвесторов:</b>\n<i>Пример: +7 999 000 11 22</i>",
        parse_mode="HTML"
    )


@router.message(AddProperty.phone)
async def ap_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if len(phone) < 7:
        await message.answer("Введите корректный номер телефона:")
        return
    await state.update_data(phone=phone)
    await state.set_state(AddProperty.email)
    await message.answer(
        "Шаг 10/10 — <b>Email для инвесторов:</b>\n<i>Пример: agent@realty.ru</i>",
        parse_mode="HTML"
    )


@router.message(AddProperty.email)
async def ap_email(message: Message, state: FSMContext):
    email = message.text.strip()
    if "@" not in email or "." not in email:
        await message.answer("Введите корректный email:")
        return
    await state.update_data(email=email)
    await state.set_state(AddProperty.confirm)

    data = await state.get_data()
    await message.answer(
        "<b>📋 Проверьте данные объекта:</b>\n\n"
        f"🏠 <b>{data['title']}</b>\n"
        f"📍 {data['city']}, {data['region']}\n"
        f"📈 Доходность: <b>{data['yield_pct']}%</b>\n"
        f"💰 Мин. вход: <b>₽{data['min_entry']:,}</b>\n"
        f"🎯 Цель: <b>₽{data['goal_amount']:,}</b>\n"
        f"📅 Сдача: <b>{data['deadline']}</b>\n"
        f"📞 {data['phone']}\n"
        f"📧 {data['email']}\n\n"
        f"📝 {data['description'][:150]}{'...' if len(data['description']) > 150 else ''}\n\n"
        "Отправить на модерацию?",
        parse_mode="HTML",
        reply_markup=_kb_confirm_property()
    )


def _kb_confirm_property():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="✅ Отправить на модерацию", callback_data="prop:submit")
    b.button(text="✖️ Отмена",                callback_data="cancel")
    b.adjust(1)
    return b.as_markup()


@router.callback_query(F.data == "prop:submit")
async def submit_property(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    data["realtor_id"] = call.from_user.id

    prop_id = await create_property(data)
    await state.clear()

    await call.message.edit_text(
        f"✅ <b>Объект отправлен на модерацию!</b>\n\n"
        f"🆔 ID: <code>{prop_id}</code>\n"
        f"🏠 {data['title']}\n\n"
        "Мы уведомим вас о результате проверки.",
        parse_mode="HTML"
    )
    await call.message.answer(
        "Используйте меню для управления объектами.",
        reply_markup=kb_realtor_main(WEBAPP_URL)
    )
    await call.answer()

    # уведомляем модераторов
    await notify_admins_new_property(bot, prop_id, data, call.from_user)


@router.callback_query(F.data == "cancel")
async def cancel_fsm(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("✖️ Отменено.")
    await call.answer()
