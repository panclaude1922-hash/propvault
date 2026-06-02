"""
keyboards.py — все inline и reply клавиатуры
"""

from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ── ГЛАВНОЕ МЕНЮ ────────────────────────────────────────

def kb_investor_main(webapp_url: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(
                text="🏠 Открыть PropVault",
                web_app=WebAppInfo(url=webapp_url)
            )
        ]],
        resize_keyboard=True
    )


def kb_realtor_main(webapp_url: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Открыть PropVault", web_app=WebAppInfo(url=webapp_url))],
            [KeyboardButton(text="📋 Мои объекты"), KeyboardButton(text="💳 Мой тариф")],
            [KeyboardButton(text="➕ Добавить объект")]
        ],
        resize_keyboard=True
    )


def kb_admin_main(webapp_url: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Открыть PropVault", web_app=WebAppInfo(url=webapp_url))],
            [KeyboardButton(text="🔍 Очередь модерации"), KeyboardButton(text="📊 Статистика")],
        ],
        resize_keyboard=True
    )


# ── РЕГИСТРАЦИЯ ──────────────────────────────────────────

def kb_role_choice() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Я инвестор — смотрю объекты", callback_data="role:investor")
    builder.button(text="🏢 Я риелтор — размещаю объекты", callback_data="role:realtor")
    builder.adjust(1)
    return builder.as_markup()


# ── ТАРИФЫ ──────────────────────────────────────────────

def kb_plans() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Старт — ₽1 900/мес (1 объект)",   callback_data="plan:start")
    builder.button(text="Pro — ₽4 900/мес (5 объектов)",    callback_data="plan:pro")
    builder.button(text="Elite — ₽12 900/мес (безлимит)",   callback_data="plan:elite")
    builder.adjust(1)
    return builder.as_markup()


def kb_confirm_plan(plan: str, price: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=f"✅ Оплатить ₽{price:,}".replace(",", " "), callback_data=f"confirm_plan:{plan}")
    builder.button(text="← Назад", callback_data="back:plans")
    builder.adjust(1)
    return builder.as_markup()


# ── МОДЕРАЦИЯ ────────────────────────────────────────────

def kb_moderation(prop_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Одобрить",   callback_data=f"mod:approve:{prop_id}")
    builder.button(text="❌ Отклонить",  callback_data=f"mod:reject:{prop_id}")
    builder.adjust(2)
    return builder.as_markup()


def kb_moderation_approved(prop_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Одобрено", callback_data=f"mod:done:{prop_id}")
    builder.adjust(1)
    return builder.as_markup()


def kb_moderation_rejected(prop_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отклонено", callback_data=f"mod:done:{prop_id}")
    builder.adjust(1)
    return builder.as_markup()


# ── ОБЪЕКТЫ РИЕЛТОРА ─────────────────────────────────────

def kb_property_actions(prop_id: int, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == "rejected":
        builder.button(text="🔄 Переподать на модерацию", callback_data=f"prop:resubmit:{prop_id}")
    builder.button(text="🗑 Удалить", callback_data=f"prop:delete:{prop_id}")
    builder.adjust(1)
    return builder.as_markup()


# ── ОБЩИЕ ────────────────────────────────────────────────

def kb_cancel() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✖️ Отмена", callback_data="cancel")
    return builder.as_markup()
