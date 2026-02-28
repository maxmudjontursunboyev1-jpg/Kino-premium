import os
import asyncio
import logging
import sqlite3
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
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
    "ad": "5422446685655676792"
}

def get_emo(name):
    """Emoji ID ni HTML formatda qaytaradi."""
    emoji_id = EMOJIS.get(name)
    return f'<tg-emoji emoji-id="{emoji_id}">✨</tg-emoji>'

# --- WEBSERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_webserver():
    port = int(os.environ.get('PORT', 8080))
    try:
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logging.error(f"Webserver xatoligi: {e}")

def keep_alive():
    thread = Thread(target=run_webserver)
    thread.daemon = True
    thread.start()

# --- SOZLAMALAR ---
API_TOKEN = os.getenv('BOT_TOKEN') or "8232377176:AAE2rn6WIk4NslzAQw_ABKYJN0A7O3FaY94"
ADMIN_ID = int(os.getenv('ADMIN_ID')) if os.getenv('ADMIN_ID') else 6205634567
MOVIE_CHANNEL_ID = os.getenv('CHANNEL_ID')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- BAZA ---
DB_NAME = "bot_data.db"
db = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = db.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT UNIQUE, type TEXT, username TEXT)")
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('sub_status', 'on'), ('btn_text', 'Boshqa kino kodlari '), ('btn_url', 'http://t.me/Kino_movie_TMR')")
db.commit()

class AdminStates(StatesGroup):
    waiting_for_btn_text = State()
    waiting_for_btn_url = State()
    waiting_for_channel_link = State()
    waiting_for_ad_text = State()

# --- TUGMALAR ---
def main_admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 Reklama yuborish")],
        [KeyboardButton(text="⚙️ Sozlamalar")],
        [KeyboardButton(text="📝 Tugma matni"), KeyboardButton(text="🔗 Tugma linki")]
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
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, url=u)]])

# --- ASOSIY FUNKSIYALAR ---
async def get_user_status(user_id: int) -> bool:
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    if cursor.fetchone()[0] == 'off': return True
    if MOVIE_CHANNEL_ID:
        try:
            m = await bot.get_chat_member(MOVIE_CHANNEL_ID, user_id)
            if m.status in ['member', 'administrator', 'creator']: return True
        except: pass
    return False

# --- HANDLERLAR ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    db.commit()

    if user_id == ADMIN_ID:
        await message.answer(f"{get_emo('admin')} <b>Admin panel</b>", reply_markup=main_admin_kb(), parse_mode="HTML")
    else:
        if await get_user_status(user_id):
            await message.answer(f"{get_emo('welcome')} <b>Xush kelibsiz!</b>\n\nKino kodini yuboring 🎥", parse_mode="HTML")
        else:
            await message.answer(f"{get_emo('sub')} <b>Botdan foydalanish uchun kanalga a'zo bo'ling!</b>", reply_markup=get_inline_button(), parse_mode="HTML")

@dp.message(F.text.regexp(r'^\d+$'))
async def search_movie(message: types.Message):
    if not await get_user_status(message.from_user.id):
        await message.answer(f"{get_emo('sub')} <b>Avval kanalga a'zo bo'ling!</b>", reply_markup=get_inline_button(), parse_mode="HTML")
        return

    wait_msg = await message.answer(f"{get_emo('search')} <b>Qidirilmoqda...</b>", parse_mode="HTML")
    try:
        await bot.copy_message(chat_id=message.chat.id, from_chat_id=MOVIE_CHANNEL_ID, message_id=int(message.text), reply_markup=get_inline_button())
        await wait_msg.delete()
    except:
        await wait_msg.edit_text(f"{get_emo('not_found')} <b>Kino topilmadi!</b>", parse_mode="HTML")

@dp.message(F.text == "📢 Reklama yuborish", F.from_user.id == ADMIN_ID)
async def cmd_ad(message: types.Message, state: FSMContext):
    await message.answer(f"{get_emo('ad')} <b>Reklama matnini yuboring:</b>", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_ad_text)

@dp.message(AdminStates.waiting_for_ad_text)
async def send_ad(message: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    await message.answer("🚀 <b>Yuborish boshlandi...</b>", parse_mode="HTML")
    count = 0
    for u in users:
        try:
            await message.copy_to(u[0])
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ <b>{count} ta foydalanuvchiga yuborildi!</b>", parse_mode="HTML")
    await state.clear()

@dp.message(F.text == "📊 Statistika", F.from_user.id == ADMIN_ID)
async def stats(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM users")
    await message.answer(f"📊 <b>Umumiy foydalanuvchilar:</b> {cursor.fetchone()[0]}", parse_mode="HTML")

@dp.message(F.text == "⚙️ Sozlamalar", F.from_user.id == ADMIN_ID)
async def settings(message: types.Message):
    await message.answer("⚙️ <b>Sozlamalar</b>", reply_markup=settings_kb(), parse_mode="HTML")

@dp.message(F.text == "⬅️ Ortga", F.from_user.id == ADMIN_ID)
async def back(message: types.Message):
    await message.answer("🛠 <b>Asosiy panel</b>", reply_markup=main_admin_kb(), parse_mode="HTML")

async def main():
    keep_alive()
    logging.info("Bot ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
