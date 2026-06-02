"""
handlers/admin.py — модерация объектов, статистика
"""

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import (
    get_pending_properties, get_property,
    approve_property, reject_property, get_stats
)
from keyboards import (
    kb_admin_main, kb_moderation,
    kb_moderation_approved, kb_moderation_rejected
)
from config import WEBAPP_URL, ADMIN_IDS

router = Router()


class RejectReason(StatesGroup):
    waiting_reason = State()


# ── ФИЛЬТР: только администраторы ───────────────────────

def is_admin(tg_id: int) -> bool:
    return tg_id in ADMIN_IDS


# ── СТАРТ ────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "👮 <b>Панель модератора PropVault</b>\n\n"
        "Используйте меню для проверки объектов.",
        parse_mode="HTML",
        reply_markup=kb_admin_main(WEBAPP_URL)
    )


# ── ОЧЕРЕДЬ МОДЕРАЦИИ ────────────────────────────────────

@router.message(F.text == "🔍 Очередь модерации")
async def moderation_queue(message: Message):
    if not is_admin(message.from_user.id):
        return

    props = await get_pending_properties()
    if not props:
        await message.answer("✅ Очередь пуста — новых объектов нет.")
        return

    await message.answer(f"⏳ Объектов на проверке: <b>{len(props)}</b>", parse_mode="HTML")

    for p in props:
        text = (
            f"🆔 <code>#{p['id']}</code>\n"
            f"🏠 <b>{p['title']}</b>\n"
            f"📍 {p['city']}, {p['region']}\n"
            f"📈 {p['yield_pct']}% · от ₽{p['min_entry']:,}\n"
            f"🎯 Цель: ₽{p['goal_amount']:,}\n"
            f"📅 Сдача: {p['deadline']}\n"
            f"👤 Риелтор: {p['realtor_name']} "
            f"(@{p['realtor_username'] or 'нет username'})\n"
            f"📞 {p['phone']} · {p['email']}\n\n"
            f"📝 {p['description'][:300]}{'...' if len(p['description']) > 300 else ''}"
        )
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=kb_moderation(p["id"])
        )


# ── ОДОБРИТЬ ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("mod:approve:"))
async def mod_approve(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return

    prop_id = int(call.data.split(":")[2])
    prop = await get_property(prop_id)
    if not prop:
        await call.answer("Объект не найден.", show_alert=True)
        return

    await approve_property(prop_id, call.from_user.id)

    await call.message.edit_reply_markup(
        reply_markup=kb_moderation_approved(prop_id)
    )
    await call.answer("✅ Объект одобрен!")

    # уведомляем риелтора
    try:
        await bot.send_message(
            prop["realtor_id"],
            f"✅ <b>Ваш объект одобрен и опубликован!</b>\n\n"
            f"🏠 <b>{prop['title']}</b>\n"
            f"📍 {prop['city']}, {prop['region']}\n\n"
            "Объект уже виден инвесторам в каталоге.",
            parse_mode="HTML"
        )
    except Exception:
        pass  # пользователь мог заблокировать бота


# ── ОТКЛОНИТЬ ────────────────────────────────────────────

@router.callback_query(F.data.startswith("mod:reject:"))
async def mod_reject_ask(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return

    prop_id = int(call.data.split(":")[2])
    await state.set_state(RejectReason.waiting_reason)
    await state.update_data(prop_id=prop_id, message_id=call.message.message_id)

    await call.message.answer(
        f"❌ Отклонение объекта <code>#{prop_id}</code>\n\n"
        "Напишите причину отклонения (риелтор её увидит):",
        parse_mode="HTML"
    )
    await call.answer()


@router.message(RejectReason.waiting_reason)
async def mod_reject_reason(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    prop_id = data["prop_id"]
    reason = message.text.strip()

    prop = await get_property(prop_id)
    if not prop:
        await message.answer("Объект не найден.")
        await state.clear()
        return

    await reject_property(prop_id, message.from_user.id, reason)
    await state.clear()

    await message.answer(
        f"❌ Объект <code>#{prop_id}</code> отклонён.\nПричина сохранена.",
        parse_mode="HTML"
    )

    # уведомляем риелтора
    try:
        await bot.send_message(
            prop["realtor_id"],
            f"❌ <b>Объект не прошёл модерацию</b>\n\n"
            f"🏠 <b>{prop['title']}</b>\n\n"
            f"💬 Причина: {reason}\n\n"
            "Исправьте описание и добавьте объект заново через «➕ Добавить объект».",
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("mod:done:"))
async def mod_done(call: CallbackQuery):
    await call.answer("Действие уже выполнено.", show_alert=True)


# ── СТАТИСТИКА ───────────────────────────────────────────

@router.message(F.text == "📊 Статистика")
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    s = await get_stats()
    mrr = s["subs_start"] * 1900 + s["subs_pro"] * 4900 + s["subs_elite"] * 12900

    await message.answer(
        "<b>📊 Статистика PropVault</b>\n\n"
        f"👥 Всего пользователей: <b>{s['total_users']}</b>\n"
        f"   · Инвесторов: {s['investors']}\n"
        f"   · Риелторов: {s['realtors']}\n\n"
        f"🏠 Объектов всего: <b>{s['properties_total']}</b>\n"
        f"   · На модерации: {s['pending']}\n"
        f"   · Опубликовано: {s['approved']}\n\n"
        f"💳 Активные подписки:\n"
        f"   · Старт: {s['subs_start']}\n"
        f"   · Pro: {s['subs_pro']}\n"
        f"   · Elite: {s['subs_elite']}\n\n"
        f"💰 Расчётный MRR: <b>₽{mrr:,}</b>",
        parse_mode="HTML"
    )
