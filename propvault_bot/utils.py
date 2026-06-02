"""
utils.py — вспомогательные функции
"""

from aiogram import Bot
from aiogram.types import User
from keyboards import kb_moderation
from config import ADMIN_IDS


async def notify_admins_new_property(bot: Bot, prop_id: int, data: dict, realtor: User):
    """Отправляет уведомление всем администраторам о новом объекте на модерации."""
    text = (
        f"🔔 <b>Новый объект на модерации</b>\n\n"
        f"🆔 <code>#{prop_id}</code>\n"
        f"🏠 <b>{data['title']}</b>\n"
        f"📍 {data['city']}, {data['region']}\n"
        f"📈 {data['yield_pct']}% · от ₽{data['min_entry']:,}\n"
        f"🎯 Цель: ₽{data['goal_amount']:,}\n"
        f"📅 Сдача: {data['deadline']}\n"
        f"👤 Риелтор: {realtor.full_name} "
        f"(@{realtor.username or 'нет username'})\n"
        f"📞 {data['phone']} · {data['email']}\n\n"
        f"📝 {data['description'][:200]}{'...' if len(data['description']) > 200 else ''}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                text,
                parse_mode="HTML",
                reply_markup=kb_moderation(prop_id)
            )
        except Exception:
            pass  # администратор мог не запустить бота
