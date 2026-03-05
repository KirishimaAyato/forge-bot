import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
)
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set")
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL environment variable is not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = Database()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.first_name or "Воин"

    await db.ensure_user(user_id, username)

    kb = ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(
                text="⚔ Открыть FORGE",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user_id}")
            )
        ]],
        resize_keyboard=True
    )

    await message.answer(
        f"Привет, *{username}*\\! 👋\n\n"
        f"⚔ *FORGE* — твой персональный трекер тренировок\\.\n\n"
        f"Нажми кнопку ниже чтобы открыть приложение\\.\n"
        f"Твой прогресс сохраняется на сервере — заходи с любого устройства\\.",
        parse_mode="MarkdownV2",
        reply_markup=kb
    )


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    user_id = message.from_user.id
    data = await db.get_user_data(user_id)
    if not data:
        await message.answer("Нет данных. Открой приложение: /start")
        return

    s = data
    text = (
        f"📊 *Твоя статистика*\n\n"
        f"⚔ Уровень: *{s['level']}* — {s['level_title']}\n"
        f"⚡ XP: *{s['xp']}* / {s['xp_to_next']}\n"
        f"🔥 Серия: *{s['streak']}* дней\n\n"
        f"🧘 Йога: *{s['yoga']}*\n"
        f"🚶 Дорожка: *{s['walk']}*\n"
        f"🏠 Упражнения дома: *{s['home']}*\n"
        f"📦 Всего тренировок: *{s['total']}*"
    )
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("water"))
async def cmd_water(message: Message):
    user_id = message.from_user.id
    water = await db.get_today_water(user_id)
    goal = 2850
    pct = min(100, round(water / goal * 100))

    bar_filled = round(pct / 10)
    bar = "🟦" * bar_filled + "⬜" * (10 - bar_filled)

    await message.answer(
        f"💧 *Вода сегодня*\n\n"
        f"{bar}\n"
        f"*{water}* / {goal} мл ({pct}%)\n\n"
        f"{'✅ Норма выполнена!' if water >= goal else f'Осталось: {goal - water} мл'}",
        parse_mode="Markdown"
    )


@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Да, сбросить всё", callback_data="confirm_reset"),
        InlineKeyboardButton(text="Отмена", callback_data="cancel_reset"),
    ]])
    await message.answer(
        "⚠️ Сбросить весь прогресс?\nЭто удалит уровень, XP, историю тренировок.",
        reply_markup=kb
    )


@dp.callback_query(F.data == "confirm_reset")
async def confirm_reset(call: CallbackQuery):
    await db.reset_user(call.from_user.id)
    await call.message.edit_text("✅ Прогресс сброшен. Начинай заново: /start")


@dp.callback_query(F.data == "cancel_reset")
async def cancel_reset(call: CallbackQuery):
    await call.message.edit_text("Отменено.")
