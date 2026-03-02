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
    "ad": "5422446685655676792",
    "link": "5438316440715273153",
    "app": "5431525043131652433"
}

def get_emo(name):
    emoji_id = EMOJIS.get(name, "✨")
    return f'<tg-emoji emoji-id="{emoji_id}">✨</tg-emoji>'

# --- WEBSERVER (KEEPALIVE) ---
app = Flask(__name__)
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
API_TOKEN = os.getenv('BOT_TOKEN') or "8232377176:AAE2rn6WIk4NslzAQw_ABKYJN0A7O3FaY94"
ADMIN_ID = int(os.getenv('ADMIN_ID')) if os.getenv('ADMIN_ID') else 6205634567
MOVIE_CHANNEL_ID = os.getenv('CHANNEL_ID') or "@Kino_movie_TMR"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- BAZA BILAN ISHLASH ---
DB_NAME = "bot_data.db"
db = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = db.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT UNIQUE)")

# Default sozlamalarni tekshirish va qo'shish
default_settings = [
    ('sub_status', 'on'),
    ('btn_text', 'Boshqa kino kodlari'),
    ('btn_url', 'http://t.me/Kino_movie_TMR'),
    ('app_url', 'https://script.google.com/') # Ilova uchun boshlang'ich link
]
for key, value in default_settings:
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
db.commit()

# --- FSM HOLATLARI ---
class AdminStates(StatesGroup):
    waiting_for_btn_text = State()
    waiting_for_btn_url = State()
    waiting_for_app_url = State() # Ilova linki uchun holat
    waiting_for_channel_link = State()
    waiting_for_ad_text = State()

# --- TUGMALAR ---
def main_admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 Reklama yuborish")],
        [KeyboardButton(text="⚙️ Sozlamalar")],
        [KeyboardButton(text="📝 Tugma matni"), KeyboardButton(text="🔗 Tugma linki")],
        [KeyboardButton(text="📱 Ilova linki")] # Yangi admin tugmasi
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
    """Kino tagida chiqadigan ikki qavatli tugmalar"""
    cursor.execute("SELECT value FROM settings WHERE key='btn_text'")
    t = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='btn_url'")
    u = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='app_url'")
    app_url = cursor.fetchone()[0]
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, url=u)],
        [InlineKeyboardButton(text="📱 Ilovani ochish", web_app=types.WebAppInfo(url=app_url))]
    ])

# --- ASOSIY LOGIKA ---
async def get_user_status(user_id: int) -> bool:
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    if cursor.fetchone()[0] == 'off': return True
    
    try:
        m = await bot.get_chat_member(MOVIE_CHANNEL_ID, user_id)
        if m.status not in ['member', 'administrator', 'creator']: return False
    except: return False

    cursor.execute("SELECT link FROM channels")
    rows = cursor.fetchall()
    for row in rows:
        try:
            ch_member = await bot.get_chat_member(row[0], user_id)
            if ch_member.status not in ['member', 'administrator', 'creator']: return False
        except: continue
    return True

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

# --- ADMIN FUNKSIYALARI ---

# Tugma matni
@dp.message(F.text == "📝 Tugma matni", F.from_user.id == ADMIN_ID)
async def set_btn_text(message: types.Message, state: FSMContext):
    await message.answer(f"{get_emo('link')} <b>Yangi tugma matnini yuboring:</b>", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_btn_text)

@dp.message(AdminStates.waiting_for_btn_text)
async def save_btn_text(message: types.Message, state: FSMContext):
    cursor.execute("UPDATE settings SET value=? WHERE key='btn_text'", (message.text,))
    db.commit()
    await message.answer("✅ Tugma matni yangilandi!", reply_markup=main_admin_kb())
    await state.clear()

# Tugma linki
@dp.message(F.text == "🔗 Tugma linki", F.from_user.id == ADMIN_ID)
async def set_btn_url(message: types.Message, state: FSMContext):
    await message.answer(f"{get_emo('link')} <b>Yangi tugma linkini yuboring:</b>", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_btn_url)

@dp.message(AdminStates.waiting_for_btn_url)
async def save_btn_url(message: types.Message, state: FSMContext):
    if message.text.startswith("http"):
        cursor.execute("UPDATE settings SET value=? WHERE key='btn_url'", (message.text,))
        db.commit()
        await message.answer("✅ Tugma linki yangilandi!", reply_markup=main_admin_kb())
        await state.clear()
    else:
        await message.answer("❌ Noto'g'ri link!")

# ILOVA LINKI (Yangi qo'shildi)
@dp.message(F.text == "📱 Ilova linki", F.from_user.id == ADMIN_ID)
async def set_app_url(message: types.Message, state: FSMContext):
    await message.answer(f"{get_emo('app')} <b>Yangi Ilova (Apps Script) linkini yuboring:</b>", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_app_url)

@dp.message(AdminStates.waiting_for_app_url)
async def save_app_url(message: types.Message, state: FSMContext):
    if message.text.startswith("http"):
        cursor.execute("UPDATE settings SET value=? WHERE key='app_url'", (message.text,))
        db.commit()
        await message.answer("✅ Ilova linki muvaffaqiyatli yangilandi!", reply_markup=main_admin_kb())
        await state.clear()
    else:
        await message.answer("❌ Xato! Link 'http' bilan boshlanishi kerak.")

# Boshqa sozlamalar
@dp.message(F.text.contains("Obuna:"), F.from_user.id == ADMIN_ID)
async def toggle_sub(message: types.Message):
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    new_val = 'off' if cursor.fetchone()[0] == 'on' else 'on'
    cursor.execute("UPDATE settings SET value=? WHERE key='sub_status'", (new_val,))
    db.commit()
    await message.answer(f"✅ Obuna: {new_val.upper()}", reply_markup=settings_kb())

@dp.message(F.text == "➕ Majburiy obuna kanallari", F.from_user.id == ADMIN_ID)
async def add_ch(message: types.Message, state: FSMContext):
    await message.answer("Kanal @username'ini yuboring:")
    await state.set_state(AdminStates.waiting_for_channel_link)

@dp.message(AdminStates.waiting_for_channel_link)
async def save_ch(message: types.Message, state: FSMContext):
    try:
        cursor.execute("INSERT INTO channels (link) VALUES (?)", (message.text,))
        db.commit()
        await message.answer("✅ Kanal qo'shildi!", reply_markup=settings_kb())
    except: await message.answer("❌ Xatolik.")
    await state.clear()

@dp.message(F.text == "📊 Statistika", F.from_user.id == ADMIN_ID)
async def stats(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM users")
    await message.answer(f"📊 <b>Umumiy foydalanuvchilar:</b> {cursor.fetchone()[0]}", parse_mode="HTML")

@dp.message(F.text == "📢 Reklama yuborish", F.from_user.id == ADMIN_ID)
async def ad_start(message: types.Message, state: FSMContext):
    await message.answer(f"{get_emo('ad')} <b>Reklama yuboring:</b>", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_ad_text)

@dp.message(AdminStates.waiting_for_ad_text)
async def ad_send(message: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    m = await message.answer("🚀 Yuborilmoqda...")
    count = 0
    for u in users:
        try:
            await message.copy_to(u[0])
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await m.edit_text(f"✅ {count} kishiga yuborildi!")
    await state.clear()

@dp.message(F.text == "⚙️ Sozlamalar", F.from_user.id == ADMIN_ID)
async def sets(message: types.Message):
    await message.answer("⚙️ <b>Sozlamalar</b>", reply_markup=settings_kb(), parse_mode="HTML")

@dp.message(F.text == "⬅️ Ortga", F.from_user.id == ADMIN_ID)
async def back(message: types.Message):
    await message.answer("🛠 <b>Panel</b>", reply_markup=main_admin_kb(), parse_mode="HTML")

async def main():
    keep_alive()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
