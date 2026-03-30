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

# --- EMOJILAR ---
EMOJIS = {
    "welcome": "5199885118214255386",
    "sub": "5352640560718949874",
    "search": "5458774648621643551",
    "not_found": "5323329096845897690",
    "admin": "5323772371830588991"
}

def get_emo(name):
    emoji_id = EMOJIS.get(name, "✨")
    return f'<tg-emoji emoji-id="{emoji_id}">✨</tg-emoji>'

# --- SOZLAMALAR ---
API_TOKEN = "8232377176:AAE2rn6WIk4NslzAQw_ABKYJN0A7O3FaY94"
ADMIN_ID = 6205634567
MOVIE_CHANNEL_ID = "@Kino_movie_TMR"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- BAZA ---
db = sqlite3.connect("bot_data.db", check_same_thread=False)
cursor = db.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")

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
    waiting_for_ad_text = State()

# --- TUGMALAR ---
def main_admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 Reklama yuborish")],
        [KeyboardButton(text="⚙️ Sozlamalar")],
        [KeyboardButton(text="📝 Tugma matni"), KeyboardButton(text="🔗 Tugma linki")],
        [KeyboardButton(text="📱 Ilova linki")]
    ], resize_keyboard=True)

def get_inline_button():
    cursor.execute("SELECT value FROM settings WHERE key='btn_text'"); t = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='btn_url'"); u = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='app_url'"); app_url = cursor.fetchone()[0]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, url=u)],
        [InlineKeyboardButton(text="📱 Ilovani ochish", web_app=types.WebAppInfo(url=app_url))]
    ])

# --- STATUS TEKSHIRISH ---
async def get_user_status(user_id: int) -> bool:
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
    
    args = command.args # Saytdan kelgan kod
    
    if args:
        if await get_user_status(user_id):
            try:
                await bot.copy_message(message.chat.id, MOVIE_CHANNEL_ID, int(args), reply_markup=get_inline_button())
            except:
                await message.answer(f"{get_emo('not_found')} Kino topilmadi!", parse_mode="HTML")
        else:
            # Obuna bo'lmagan bo'lsa, kodni saqlagan holda tugma beramiz
            me = await bot.get_me()
            retry_url = f"https://t.me/{me.username}?start={args}"
            sub_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/{MOVIE_CHANNEL_ID.replace('@','')}")],
                [InlineKeyboardButton(text="✅ A'zo bo'ldim / Kinoni ko'rish", url=retry_url)]
            ])
            await message.answer(f"{get_emo('sub')} <b>Kanalga a'zo bo'ling!</b>", reply_markup=sub_kb, parse_mode="HTML")
        return

    # ODDIY START
    if user_id == ADMIN_ID:
        await message.answer(f"{get_emo('admin')} <b>Admin panel</b>", reply_markup=main_admin_kb(), parse_mode="HTML")
    else:
        await message.answer(f"{get_emo('welcome')} <b>Xush kelibsiz!</b>\n\nKino kodini yuboring 🎥", parse_mode="HTML")

@dp.message(F.text.regexp(r'^\d+$'))
async def search_movie(message: types.Message):
    if not await get_user_status(message.from_user.id):
        await message.answer(f"{get_emo('sub')} <b>Avval a'zo bo'ling!</b>", reply_markup=get_inline_button(), parse_mode="HTML")
        return
    try:
        await bot.copy_message(message.chat.id, MOVIE_CHANNEL_ID, int(message.text), reply_markup=get_inline_button())
    except:
        await message.answer(f"{get_emo('not_found')} <b>Topilmadi!</b>", parse_mode="HTML")

# --- ADMIN FUNKSIYALARI (QAYTIB KELDI) ---

@dp.message(F.text == "📝 Tugma matni", F.from_user.id == ADMIN_ID)
async def edit_t(m: types.Message, state: FSMContext):
    await m.answer("Yangi tugma matnini yuboring:"); await state.set_state(AdminStates.waiting_for_btn_text)

@dp.message(AdminStates.waiting_for_btn_text)
async def s_t(m: types.Message, state: FSMContext):
    cursor.execute("UPDATE settings SET value=? WHERE key='btn_text'", (m.text,)); db.commit()
    await m.answer("✅ Saqlandi!", reply_markup=main_admin_kb()); await state.clear()

@dp.message(F.text == "📱 Ilova linki", F.from_user.id == ADMIN_ID)
async def edit_a(m: types.Message, state: FSMContext):
    await m.answer("Apps Script linkini yuboring:"); await state.set_state(AdminStates.waiting_for_app_url)

@dp.message(AdminStates.waiting_for_app_url)
async def s_a(m: types.Message, state: FSMContext):
    cursor.execute("UPDATE settings SET value=? WHERE key='app_url'", (m.text,)); db.commit()
    await m.answer("✅ Saqlandi!", reply_markup=main_admin_kb()); await state.clear()

@dp.message(F.text == "📊 Statistika", F.from_user.id == ADMIN_ID)
async def stats(m: types.Message):
    cursor.execute("SELECT COUNT(*) FROM users")
    await m.answer(f"📊 Foydalanuvchilar: {cursor.fetchone()[0]}")

@dp.message(F.text == "📢 Reklama yuborish", F.from_user.id == ADMIN_ID)
async def ad_s(m: types.Message, state: FSMContext):
    await m.answer("Xabarni yuboring:"); await state.set_state(AdminStates.waiting_for_ad_text)

@dp.message(AdminStates.waiting_for_ad_text)
async def ad_f(m: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users"); users = cursor.fetchall()
    await m.answer("Yuborish boshlandi..."); c = 0
    for u in users:
        try: await m.copy_to(u[0]); c += 1; await asyncio.sleep(0.05)
        except: pass
    await m.answer(f"✅ {c} kishiga yuborildi."); await state.clear()

# --- WEBSERVER & RUN ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is alive!"

def run_web(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

async def main():
    Thread(target=run_web).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
