import os
import asyncio
import logging
import sqlite3
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- WEBSERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_webserver():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    thread = Thread(target=run_webserver)
    thread.daemon = True
    thread.start()

# --- SOZLAMALAR ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID')) if os.getenv('ADMIN_ID') else None
MOVIE_CHANNEL_ID = os.getenv('CHANNEL_ID')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- BAZA ---
DB_NAME = "bot_data.db"
db = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = db.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT UNIQUE)")

# Standart sozlamalar
defaults = [
    ('sub_status', 'on'),
    ('btn_text', 'Boshqa kino kodlari'),
    ('btn_url', 'http://t.me/Kino_movie_TMR'),
    ('app_url', 'https://script.google.com/')
]
for k, v in defaults:
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
db.commit()

# --- FSM HOLATLARI ---
class AdminStates(StatesGroup):
    waiting_for_btn_text = State()
    waiting_for_btn_url = State()
    waiting_for_app_url = State() # Ilova linki uchun holat
    waiting_for_ad_text = State()

# --- TUGMALAR ---
def main_admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 Reklama yuborish")],
        [KeyboardButton(text="⚙️ Sozlamalar")],
        [KeyboardButton(text="📝 Tugma matni"), KeyboardButton(text="🔗 Tugma linki")],
        [KeyboardButton(text="📱 Ilova linki")] # Mana shu tugma qaytdi
    ], resize_keyboard=True)

def settings_kb():
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    status = cursor.fetchone()[0]
    txt = "🔴 Obuna: O'CHIQ" if status == 'off' else "🟢 Obuna: YOQIQ"
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=txt)],
        [KeyboardButton(text="⬅️ Ortga")]
    ], resize_keyboard=True)

def get_inline_button():
    cursor.execute("SELECT value FROM settings WHERE key='btn_text'"); t = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='btn_url'"); u = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='app_url'"); app_url = cursor.fetchone()[0]
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, url=u)],
        [InlineKeyboardButton(text="📱 Ilovani ochish", web_app=types.WebAppInfo(url=app_url))]
    ])

async def get_user_status(user_id: int) -> bool:
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    if cursor.fetchone()[0] == 'off': return True
    try:
        m = await bot.get_chat_member(chat_id=MOVIE_CHANNEL_ID, user_id=user_id)
        return m.status in ['member', 'administrator', 'creator']
    except: return False

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    db.commit()

    args = command.args # Deep Link (start=223)
    
    if args and args.isdigit():
        if await get_user_status(user_id):
            try:
                await bot.copy_message(message.chat.id, MOVIE_CHANNEL_ID, int(args), reply_markup=get_inline_button())
            except:
                await message.answer("😔 Kino topilmadi.")
        else:
            await message.answer("❌ Kanalga a'zo bo'ling!", reply_markup=get_inline_button())
        return

    if user_id == ADMIN_ID:
        await message.answer("🛠 <b>Admin panel</b>", reply_markup=main_admin_kb(), parse_mode="HTML")
    else:
        await message.answer("🍿 <b>Xush kelibsiz!</b>\n\nKino kodini yuboring 🎥", parse_mode="HTML")

@dp.message(F.text.regexp(r'^\d+$'))
async def search_movie(message: types.Message):
    if not await get_user_status(message.from_user.id):
        await message.answer("❌ Avval kanalga a'zo bo'ling!", reply_markup=get_inline_button())
        return
    try:
        await bot.copy_message(message.chat.id, MOVIE_CHANNEL_ID, int(message.text), reply_markup=get_inline_button())
    except:
        await message.answer("😔 Kino topilmadi.")

# --- ADMIN SOZLAMALARI ---

@dp.message(F.text == "📱 Ilova linki", F.from_user.id == ADMIN_ID)
async def edit_app_url(m: types.Message, state: FSMContext):
    await m.answer("Yangi Ilova (Apps Script) linkini yuboring:"); await state.set_state(AdminStates.waiting_for_app_url)

@dp.message(AdminStates.waiting_for_app_url)
async def save_app_url(m: types.Message, state: FSMContext):
    cursor.execute("UPDATE settings SET value=? WHERE key='app_url'", (m.text,)); db.commit()
    await m.answer("✅ Ilova linki saqlandi!", reply_markup=main_admin_kb()); await state.clear()

@dp.message(F.text == "📝 Tugma matni", F.from_user.id == ADMIN_ID)
async def edit_btn_text(m: types.Message, state: FSMContext):
    await m.answer("Tugma matnini yuboring:"); await state.set_state(AdminStates.waiting_for_btn_text)

@dp.message(AdminStates.waiting_for_btn_text)
async def save_btn_text(m: types.Message, state: FSMContext):
    cursor.execute("UPDATE settings SET value=? WHERE key='btn_text'", (m.text,)); db.commit()
    await m.answer("✅ Saqlandi!", reply_markup=main_admin_kb()); await state.clear()

@dp.message(F.text == "🔗 Tugma linki", F.from_user.id == ADMIN_ID)
async def edit_btn_url(m: types.Message, state: FSMContext):
    await m.answer("Tugma linkini yuboring:"); await state.set_state(AdminStates.waiting_for_btn_url)

@dp.message(AdminStates.waiting_for_btn_url)
async def save_btn_url(m: types.Message, state: FSMContext):
    cursor.execute("UPDATE settings SET value=? WHERE key='btn_url'", (m.text,)); db.commit()
    await m.answer("✅ Saqlandi!", reply_markup=main_admin_kb()); await state.clear()

@dp.message(F.text == "📊 Statistika", F.from_user.id == ADMIN_ID)
async def stats(m: types.Message):
    cursor.execute("SELECT COUNT(*) FROM users")
    await m.answer(f"📊 Foydalanuvchilar: {cursor.fetchone()[0]}")

@dp.message(F.text == "📢 Reklama yuborish", F.from_user.id == ADMIN_ID)
async def ad_start(m: types.Message, state: FSMContext):
    await m.answer("Reklama matnini yuboring:"); await state.set_state(AdminStates.waiting_for_ad_text)

@dp.message(AdminStates.waiting_for_ad_text)
async def ad_send(m: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users"); users = cursor.fetchall()
    c = 0
    for u in users:
        try:
            await bot.send_message(u[0], m.text)
            c += 1; await asyncio.sleep(0.05)
        except: pass
    await m.answer(f"✅ {c} kishiga yuborildi.", reply_markup=main_admin_kb()); await state.clear()

@dp.message(F.text == "⚙️ Sozlamalar", F.from_user.id == ADMIN_ID)
async def cmd_settings(m: types.Message):
    await m.answer("⚙️ Sozlamalar", reply_markup=settings_kb())

@dp.message(F.text == "⬅️ Ortga", F.from_user.id == ADMIN_ID)
async def cmd_back(m: types.Message):
    await m.answer("Admin panel", reply_markup=main_admin_kb())

# --- ISHGA TUSHIRISH ---
async def start_bot():
    keep_alive()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(start_bot())
