import os
import asyncio
import logging
import sqlite3
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject # CommandObject qo'shildi
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
    try:
        app.run(host='0.0.0.0', port=port)
    except OSError as e:
        logging.error(f"Port xatoligi: {e}")

def keep_alive():
    thread = Thread(target=run_webserver)
    thread.daemon = True
    thread.start()

# --- SOZLAMALAR ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID')) if os.getenv('ADMIN_ID') else None
MOVIE_CHANNEL_ID = os.getenv('CHANNEL_ID')

if not API_TOKEN:
    exit("BOT_TOKEN o'rnatilmagan!")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- BAZA ---
DB_NAME = "bot_data.db"
db = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = db.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT UNIQUE, type TEXT, username TEXT)")
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('sub_status', 'on')")
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('btn_text', 'Kanalga aʼzo boʻling')")
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('btn_url', 'https://t.me/Kino_movie_TMR')")
db.commit()

class AdminStates(StatesGroup):
    waiting_for_btn_text = State()
    waiting_for_btn_url = State()
    waiting_for_channel_link = State()
    waiting_for_ad_text = State()

# --- KLAVIATURALAR ---

def main_admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 Reklama yuborish")],
        [KeyboardButton(text="⚙️ Sozlamalar")],
        [KeyboardButton(text="📝 Tugma matni"), KeyboardButton(text="🔗 Tugma linki")]
    ], resize_keyboard=True)

def settings_kb():
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    s = cursor.fetchone()[0]
    txt = "🔴 Obuna: O'CHIQ" if s == 'off' else "🟢 Obuna: YOQIQ"
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=txt)],
        [KeyboardButton(text="➕ Majburiy obuna kanallari")],
        [KeyboardButton(text="⬅️ Ortga")]
    ], resize_keyboard=True)

def get_inline_button():
    cursor.execute("SELECT value FROM settings WHERE key='btn_text'"); t = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='btn_url'"); u = cursor.fetchone()[0]
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, url=u)]])

async def get_user_status(user_id: int) -> bool:
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    if cursor.fetchone()[0] == 'off': return True
    try:
        member = await bot.get_chat_member(chat_id=MOVIE_CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

# --- ASOSIY START HANDLER (DEEPLINK BILAN) ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject): # command: CommandObject qo'shildi
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    db.commit()

    args = command.args # start=223 dagi '223' qismini oladi
    
    if args and args.isdigit(): # Agar havola orqali kod kelgan bo'lsa
        if await get_user_status(user_id):
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=MOVIE_CHANNEL_ID,
                    message_id=int(args),
                    reply_markup=get_inline_button()
                )
            except Exception as e:
                await message.answer("😔 Bu kod bilan kino topilmadi.")
        else:
            await message.answer("❌ Botdan foydalanish uchun kanalga a'zo bo'ling!", reply_markup=get_inline_button())
        return # Havola bilan kelganda shu yerda to'xtaydi

    # Oddiy start (havolasiz)
    if user_id == ADMIN_ID:
        await message.answer("🛠 <b>Admin panel</b>", reply_markup=main_admin_kb(), parse_mode="HTML")
    else:
        await message.answer("🍿 <b>Xush kelibsiz!</b>\n\nKino kodini yuboring 🎥", parse_mode="HTML")

# --- QIDIRUV HANDLERI ---
@dp.message(F.text.regexp(r'^\d+$'))
async def search_movie(message: types.Message):
    if not await get_user_status(message.from_user.id):
        await message.answer("❌ Avval kanalga a'zo bo'ling!", reply_markup=get_inline_button())
        return
    try:
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=MOVIE_CHANNEL_ID,
            message_id=int(message.text),
            reply_markup=get_inline_button()
        )
    except:
        await message.answer("😔 Kino topilmadi.")

# --- ADMIN BUYRUQLARI (O'ZGARISHSIZ QOLDI) ---

@dp.message(F.text == "📝 Tugma matni", F.from_user.id == ADMIN_ID)
async def cmd_set_btn_text(m: types.Message, state: FSMContext):
    await m.answer("Yangi matn yuboring:"); await state.set_state(AdminStates.waiting_for_btn_text)

@dp.message(AdminStates.waiting_for_btn_text)
async def save_btn_text(m: types.Message, state: FSMContext):
    cursor.execute("UPDATE settings SET value=? WHERE key='btn_text'", (m.text,)); db.commit()
    await m.answer("✅ Saqlandi!", reply_markup=main_admin_kb()); await state.clear()

@dp.message(F.text == "🔗 Tugma linki", F.from_user.id == ADMIN_ID)
async def cmd_set_btn_url(m: types.Message, state: FSMContext):
    await m.answer("Yangi link yuboring:"); await state.set_state(AdminStates.waiting_for_btn_url)

@dp.message(AdminStates.waiting_for_btn_url)
async def save_btn_url(m: types.Message, state: FSMContext):
    cursor.execute("UPDATE settings SET value=? WHERE key='btn_url'", (m.text,)); db.commit()
    await m.answer("✅ Saqlandi!", reply_markup=main_admin_kb()); await state.clear()

@dp.message(F.text == "📊 Statistika", F.from_user.id == ADMIN_ID)
async def stats(m: types.Message):
    cursor.execute("SELECT COUNT(*) FROM users")
    await m.answer(f"📊 Foydalanuvchilar: {cursor.fetchone()[0]}")

@dp.message(F.text == "📢 Reklama yuborish", F.from_user.id == ADMIN_ID)
async def cmd_send_ad(m: types.Message, state: FSMContext):
    await m.answer("Reklama matnini yuboring:"); await state.set_state(AdminStates.waiting_for_ad_text)

@dp.message(AdminStates.waiting_for_ad_text)
async def send_ad_to_users(m: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users"); users = cursor.fetchall()
    c = 0
    for u in users:
        try:
            await bot.send_message(u[0], m.text)
            c += 1; await asyncio.sleep(0.05)
        except: pass
    await m.answer(f"✅ {c} kishiga yuborildi."); await state.clear()

@dp.message(F.text == "⚙️ Sozlamalar", F.from_user.id == ADMIN_ID)
async def cmd_settings(m: types.Message):
    await m.answer("⚙️ Sozlamalar", reply_markup=settings_kb(), parse_mode="HTML")

@dp.message(F.text == "⬅️ Ortga", F.from_user.id == ADMIN_ID)
async def cmd_back(m: types.Message):
    await m.answer("🛠 Admin panel", reply_markup=main_admin_kb(), parse_mode="HTML")

# --- ISHGA TUSHIRISH ---
async def start_bot():
    keep_alive()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(start_bot())
