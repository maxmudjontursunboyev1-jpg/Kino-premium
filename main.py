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

# --- PREMIUM EMOJI ID-LARI ---
EMOJIS = {
    "welcome": "5199885118214255386",
    "sub": "5352640560718949874",
    "search": "5458774648621643551",
    "not_found": "5323329096845897690",
    "admin": "5323772371830588991",
    "ad": "5422446685655676792",
    "link": "5438316440715273153",
    "app": "5431525043131652433"
}

def get_emo(name):
    emoji_id = EMOJIS.get(name, "✨")
    return f'<tg-emoji emoji-id="{emoji_id}">✨</tg-emoji>'

# --- WEBSERVER (Render/Replit uchun) ---
app = Flask(name)
@app.route('/')
def home(): return "Bot is alive!"

def run_webserver():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    thread = Thread(target=run_webserver)
    thread.daemon = True
    thread.start()

# --- SOZLAMALAR ---
# Tokenni o'zgartirishni unutmang
API_TOKEN = os.getenv('BOT_TOKEN') or "8232377176:AAE2rn6WIk4NslzAQw_ABKYJN0A7O3FaY94"
ADMIN_ID = int(os.getenv('ADMIN_ID')) if os.getenv('ADMIN_ID') else 6205634567
MOVIE_CHANNEL_ID = os.getenv('CHANNEL_ID') or "@Kino_movie_TMR"

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

defaults = [
    ('sub_status', 'on'),
    ('btn_text', 'Boshqa kino kodlari'),
    ('btn_url', 'http://t.me/Kino_movie_TMR'),
    ('app_url', 'https://script.google.com/')
]
for k, v in defaults:
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
db.commit()

# --- FSM STATES ---
class AdminStates(StatesGroup):
    waiting_for_btn_text = State()
    waiting_for_btn_url = State()
    waiting_for_app_url = State()
    waiting_for_channel_link = State()
    waiting_for_ad_text = State()

# --- TUGMALAR ---
def main_admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 Reklama yuborish")],
        [KeyboardButton(text="⚙️ Sozlamalar")],
        [KeyboardButton(text="📝 Tugma matni"), KeyboardButton(text="🔗 Tugma linki")],
        [KeyboardButton(text="📱 Ilova linki")]
    ], resize_keyboard=True)

def settings_kb():
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    status = cursor.fetchone()[0]
    sub_text = "🔴 Obuna: O'CHIQ" if status == 'off' else "🟢 Obuna: YOQIQ"
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=sub_text)],
        [KeyboardButton(text="➕ Majburiy obuna kanallari")],
        [KeyboardButton(text="⬅️ Ortga")]
    ], resize_keyboard=True)

def get_inline_button():
    cursor.execute("SELECT value FROM settings WHERE key='btn_text'")
    t = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='btn_url'")
    u = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='app_url'")
    app_url = cursor.fetchone()[0]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, url=u)],
        [InlineKeyboardButton(text="📱 Ilovani ochish", web_app=types.WebAppInfo(url=app_url))]
    ])# --- OBUNA TEKSHIRISH ---
async def get_user_status(user_id: int) -> bool:
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    if cursor.fetchone()[0] == 'off': return True
    try:
        m = await bot.get_chat_member(MOVIE_CHANNEL_ID, user_id)
        if m.status not in ['member', 'administrator', 'creator']: return False
    except: return False
    cursor.execute("SELECT link FROM channels")
    for row in cursor.fetchall():
        try:
            ch = await bot.get_chat_member(row[0], user_id)
            if ch.status not in ['member', 'administrator', 'creator']: return False
        except: continue
    return True

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject = None):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    db.commit()
    
    # Saytdan t.me/bot?start=123 bo'lib kelsa, 123 ni oladi
    args = command.args

    if user_id == ADMIN_ID and not args:
        await message.answer(f"{get_emo('admin')} <b>Admin panel</b>", reply_markup=main_admin_kb(), parse_mode="HTML")
    else:
        is_sub = await get_user_status(user_id)
        
        if args and args.isdigit():
            if is_sub:
                try:
                    await bot.copy_message(message.chat.id, MOVIE_CHANNEL_ID, int(args), reply_markup=get_inline_button())
                except:
                    await message.answer(f"{get_emo('not_found')} <b>Kino topilmadi!</b>", parse_mode="HTML")
            else:
                await message.answer(f"{get_emo('sub')} <b>Kino ko'rish uchun avval a'zo bo'ling!</b>", reply_markup=get_inline_button(), parse_mode="HTML")
        else:
            await message.answer(f"{get_emo('welcome')} <b>Xush kelibsiz!</b>\n\nKino kodini yuboring 🎥", parse_mode="HTML")

# --- ADMIN SOZLAMALARI ---
@dp.message(F.text == "📝 Tugma matni", F.from_user.id == ADMIN_ID)
async def edit_t(message: types.Message, state: FSMContext):
    await message.answer("Yangi tugma matnini yuboring:")
    await state.set_state(AdminStates.waiting_for_btn_text)

@dp.message(F.text == "🔗 Tugma linki", F.from_user.id == ADMIN_ID)
async def edit_u(message: types.Message, state: FSMContext):
    await message.answer("Yangi tugma linkini yuboring:")
    await state.set_state(AdminStates.waiting_for_btn_url)

@dp.message(F.text == "📱 Ilova linki", F.from_user.id == ADMIN_ID)
async def edit_a(message: types.Message, state: FSMContext):
    await message.answer("Yangi Ilova (Apps Script) linkini yuboring:")
    await state.set_state(AdminStates.waiting_for_app_url)

@dp.message(AdminStates.waiting_for_btn_text)
async def s_t(message: types.Message, state: FSMContext):
    cursor.execute("UPDATE settings SET value=? WHERE key='btn_text'", (message.text,))
    db.commit()
    await message.answer("✅ Matn saqlandi!", reply_markup=main_admin_kb())
    await state.clear()

@dp.message(AdminStates.waiting_for_btn_url)
async def s_u(message: types.Message, state: FSMContext):
    if "http" in message.text:
        cursor.execute("UPDATE settings SET value=? WHERE key='btn_url'", (message.text,))
        db.commit()
        await message.answer("✅ Link saqlandi!", reply_markup=main_admin_kb())
        await state.clear()
    else: await message.answer("❌ Xato link!")

@dp.message(AdminStates.waiting_for_app_url)
async def s_a(message: types.Message, state: FSMContext):
    if "http" in message.text:
        cursor.execute("UPDATE settings SET value=? WHERE key='app_url'", (message.text,))
        db.commit()
        await message.answer("✅ Ilova linki saqlandi!", reply_markup=main_admin_kb())
        await state.clear()
    else: await message.answer("❌ Xato link!")# --- ODDIY QIDIRUV (RAQAM YUBORILSA) ---
@dp.message(F.text.regexp(r'^\d+$'))
async def search_movie(message: types.Message):
    if not await get_user_status(message.from_user.id):
        await message.answer(f"{get_emo('sub')} <b>Avval a'zo bo'ling!</b>", reply_markup=get_inline_button(), parse_mode="HTML")
        return
    wait = await message.answer(f"{get_emo('search')} <b>Qidirilmoqda...</b>", parse_mode="HTML")
    try:
        await bot.copy_message(message.chat.id, MOVIE_CHANNEL_ID, int(message.text), reply_markup=get_inline_button())
        await wait.delete()
    except: await wait.edit_text(f"{get_emo('not_found')} <b>Topilmadi!</b>", parse_mode="HTML")

# --- QOLGAN ADMIN FUNKSIYALAR ---
@dp.message(F.text == "📊 Statistika", F.from_user.id == ADMIN_ID)
async def stats(m: types.Message):
    cursor.execute("SELECT COUNT(*) FROM users")
    await m.answer(f"📊 Foydalanuvchilar soni: {cursor.fetchone()[0]}")

@dp.message(F.text == "📢 Reklama yuborish", F.from_user.id == ADMIN_ID)
async def ad_s(m: types.Message, state: FSMContext):
    await m.answer("Reklama xabarini (rasm, matn, video) yuboring:")
    await state.set_state(AdminStates.waiting_for_ad_text)

@dp.message(AdminStates.waiting_for_ad_text)
async def ad_f(m: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    await m.answer("🚀 Reklama tarqatish boshlandi...")
    c = 0
    for u in users:
        try: 
            await m.copy_to(u[0])
            c += 1
            await asyncio.sleep(0.05)
        except: pass
    await m.answer(f"✅ Tugadi. {c} kishiga yuborildi.")
    await state.clear()

@dp.message(F.text == "⚙️ Sozlamalar", F.from_user.id == ADMIN_ID)
async def sets(m: types.Message):
    await m.answer("Sozlamalar bo'limi:", reply_markup=settings_kb())

@dp.message(F.text.contains("Obuna:"), F.from_user.id == ADMIN_ID)
async def toggle(m: types.Message):
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    current = cursor.fetchone()[0]
    new = 'off' if current == 'on' else 'on'
    cursor.execute("UPDATE settings SET value=? WHERE key='sub_status'", (new,))
    db.commit()
    await m.answer(f"✅ Majburiy obuna statusi: {new}", reply_markup=settings_kb())

@dp.message(F.text == "⬅️ Ortga", F.from_user.id == ADMIN_ID)
async def back(m: types.Message):
    await m.answer("Asosiy admin panel", reply_markup=main_admin_kb())

async def main():
    keep_alive()
    await dp.start_polling(bot)

if name == "main":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.error("Bot to'xtatildi!")
