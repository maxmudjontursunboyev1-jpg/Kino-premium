import os
import asyncio
import logging
import sqlite3
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandObject
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)

# --- PREMIUM EMOJI ID-LARI ---
EMOJIS = {
    "welcome": "5199885118214255386",
    "sub": "5352640560718949874",
    "search": "5458774648621643551",
    "not_found": "5323329096845897690",
    "admin": "5323772371830588991",
    "ad_sending": "5422446685655676792"
}

def get_emo(name):
    emoji_id = EMOJIS.get(name)
    return f'<tg-emoji emoji-id="{emoji_id}">✨</tg-emoji>' if emoji_id else "✨"

# --- WEBSERVER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is alive!"

def run_webserver():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- SOZLAMALAR ---
API_TOKEN = "7774202263:AAE4lZbIdDZflKhFWTBmLfPz3D3XwlyXr38"
ADMIN_ID = 7339714216
MOVIE_CHANNEL_ID = "-1002619474183"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# --- BAZA ---
db = sqlite3.connect("bot_data.db", check_same_thread=False)
cursor = db.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
# Dinamik tugmalar uchun yangi jadval
cursor.execute("CREATE TABLE IF NOT EXISTS buttons (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, type TEXT)") 
db.commit()

# Default sozlamalar
defaults = [('sub_status', 'on')]
for k, v in defaults:
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
# Agar tugmalar bo'sh bo'lsa, bitta default tugma qo'shamiz
cursor.execute("SELECT COUNT(*) FROM buttons")
if cursor.fetchone()[0] == 0:
    cursor.execute("INSERT INTO buttons (name, url, type) VALUES (?, ?, ?)", ("🎬 Kanalimiz", "https://t.me/Kino_movie_TMR", "url"))
db.commit()

# --- FSM STATES ---
class AdminStates(StatesGroup):
    add_btn_name = State()
    add_btn_url = State()
    waiting_for_ad = State()

# --- KLAVIATURALAR ---
def main_admin_kb():
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    sub_text = "🟢 Obuna: YONIQ" if cursor.fetchone()[0] == 'on' else "🔴 Obuna: O'CHIQ"
    
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 Reklama")],
        [KeyboardButton(text="➕ Tugma qo'shish"), KeyboardButton(text="🗑 Tugmalarni tozalash")],
        [KeyboardButton(text=sub_text)]
    ], resize_keyboard=True)

def get_movie_kb():
    cursor.execute("SELECT name, url FROM buttons")
    btns = cursor.fetchall()
    keyboard = []
    for name, url in btns:
        keyboard.append([InlineKeyboardButton(text=name, url=url)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- STATUS TEKSHIRISH ---
async def check_sub(user_id: int) -> bool:
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    if cursor.fetchone()[0] == 'off': return True
    try:
        m = await bot.get_chat_member(MOVIE_CHANNEL_ID, user_id)
        return m.status in ['member', 'administrator', 'creator']
    except: return False

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    db.commit()
    
    args = command.args
    if args and args.isdigit():
        if await check_sub(user_id):
            try:
                await bot.copy_message(message.chat.id, MOVIE_CHANNEL_ID, int(args), reply_markup=get_movie_kb())
                return
            except:
                await message.answer(f"{get_emo('not_found')} <b>Kino topilmadi!</b>")
                return
        else:
            me = await bot.get_me()
            sub_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/{MOVIE_CHANNEL_ID.replace('@','')}")],
                [InlineKeyboardButton(text="✅ Tasdiqlash", url=f"https://t.me/{me.username}?start={args}")]
            ])
            await message.answer(f"{get_emo('sub')} <b>Kino ko'rish uchun kanalga a'zo bo'ling!</b>", reply_markup=sub_kb)
            return

    if user_id == ADMIN_ID:
        await message.answer(f"{get_emo('admin')} <b>Admin panel</b>", reply_markup=main_admin_kb())
    else:
        await message.answer(f"{get_emo('welcome')} <b>Xush kelibsiz!</b>\n\nKino kodini yuboring {get_emo('search')}")

@dp.message(F.text.regexp(r'^\d+$'))
async def search_movie(message: types.Message):
    if not await check_sub(message.from_user.id):
        me = await bot.get_me()
        sub_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/{MOVIE_CHANNEL_ID.replace('@','')}")],
            [InlineKeyboardButton(text="✅ Tasdiqlash", url=f"https://t.me/{me.username}?start={message.text}")]
        ])
        await message.answer(f"{get_emo('sub')} <b>Avval kanalga a'zo bo'ling!</b>", reply_markup=sub_kb)
        return
    try:
        await bot.copy_message(message.chat.id, MOVIE_CHANNEL_ID, int(message.text), reply_markup=get_movie_kb())
    except:
        await message.answer(f"{get_emo('not_found')} <b>Kino topilmadi!</b>")

# --- ADMIN FUNKSIYALARI ---

@dp.message(F.text.in_(["🟢 Obuna: YONIQ", "🔴 Obuna: O'CHIQ"]), F.from_user.id == ADMIN_ID)
async def toggle_sub(m: types.Message):
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    new_stat = 'off' if cursor.fetchone()[0] == 'on' else 'on'
    cursor.execute("UPDATE settings SET value=? WHERE key='sub_status'", (new_stat,))
    db.commit()
    await m.answer(f"Status o'zgardi!", reply_markup=main_admin_kb())

@dp.message(F.text == "➕ Tugma qo'shish", F.from_user.id == ADMIN_ID)
async def add_btn(m: types.Message, state: FSMContext):
    await m.answer("Tugma nomini yuboring:"); await state.set_state(AdminStates.add_btn_name)

@dp.message(AdminStates.add_btn_name)
async def set_name(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("Tugma linkini yuboring:"); await state.set_state(AdminStates.add_btn_url)

@dp.message(AdminStates.add_btn_url)
async def set_url(m: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("INSERT INTO buttons (name, url, type) VALUES (?, ?, ?)", (data['name'], m.text, "url"))
    db.commit()
    await m.answer("✅ Yangi tugma qo'shildi!", reply_markup=main_admin_kb()); await state.clear()

@dp.message(F.text == "🗑 Tugmalarni tozalash", F.from_user.id == ADMIN_ID)
async def clear_btns(m: types.Message):
    cursor.execute("DELETE FROM buttons"); db.commit()
    await m.answer("🗑 Barcha inline tugmalar o'chirildi!", reply_markup=main_admin_kb())

@dp.message(F.text == "📊 Statistika", F.from_user.id == ADMIN_ID)
async def stats(m: types.Message):
    cursor.execute("SELECT COUNT(*) FROM users"); count = cursor.fetchone()[0]
    await m.answer(f"📊 Foydalanuvchilar: <b>{count}</b>")

@dp.message(F.text == "📢 Reklama", F.from_user.id == ADMIN_ID)
async def ad_s(m: types.Message, state: FSMContext):
    await m.answer(f"{get_emo('ad_sending')} <b>Reklama xabarini yuboring:</b>"); await state.set_state(AdminStates.waiting_for_ad)

@dp.message(AdminStates.waiting_for_ad)
async def ad_f(m: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users"); users = cursor.fetchall()
    await m.answer("🚀 Tarqatilmoqda..."); c = 0
    for u in users:
        try: await m.copy_to(u[0]); c += 1; await asyncio.sleep(0.05)
        except: pass
    await m.answer(f"✅ {c} kishiga yuborildi.", reply_markup=main_admin_kb()); await state.clear()

# --- MAIN ---
async def main():
    Thread(target=run_webserver, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
