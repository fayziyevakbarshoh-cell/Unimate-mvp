import asyncio
import json
import logging
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

# ================= SOZLAMALAR =================
BOT_TOKEN = "SIZNING_BOT_TOKENINGIZNI_SHU_YERGA_QO'YING"
WEBAPP_URL = "SIZNING_VERCEL_HAVOLANGIZ" 
ADMIN_ID = 123456789  # O'zingizning Telegram ID raqamingiz
# ==============================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect("unimate.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            service_title TEXT,
            price INTEGER,
            commission INTEGER,
            status TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mentors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            subject TEXT,
            price INTEGER,
            description TEXT,
            approved INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 UniMate Ilovasini Ochish", web_app=WebAppInfo(url=WEBAPP_URL))]
        ],
        resize_keyboard=True
    )
    welcome_text = (
        f"👋 Salom, <b>{message.from_user.full_name}</b>!\n\n"
        "<b>UniMate</b> — Millat Umidi universiteti talabalari uchun bilim almashish va tezkor akademik yordam platformasiga xush kelibsiz!\n\n"
        "👇 Platformaga kirish uchun pastdagi tugmani bosing:"
    )
    await message.answer(welcome_text, reply_markup=kb, parse_mode="HTML")

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    data = json.loads(message.web_app_data.data)
    action = data.get("action")
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name

    conn = sqlite3.connect("unimate.db")
    cur = conn.cursor()

    if action == "book":
        title = data.get("title")
        price = int(data.get("price"))
        commission = int(price * 0.25)

        cur.execute(
            "INSERT INTO orders (user_id, username, service_title, price, commission, status) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, title, price, commission, "Kutilmoqda")
        )
        order_id = cur.lastrowid
        conn.commit()

        pay_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 To'lov qilish ({price:,} so'm)", callback_data=f"pay_{order_id}")]
        ])

        await message.answer(
            f"✅ <b>Buyurtma #{order_id} yaratildi!</b>\n\n"
            f"📌 Xizmat: <b>{title}</b>\n"
            f"💰 Narxi: <b>{price:,} so'm</b>\n"
            f"🛡 <i>Xavfsiz bitim (Escrow): Pul dars yakunlangani tasdiqlangandan keyingina mentorga o'tkaziladi.</i>",
            reply_markup=pay_kb,
            parse_mode="HTML"
        )

    elif action == "new_mentor":
        name = data.get("name")
        subject = data.get("subject")
        price = int(data.get("price"))
        desc = data.get("desc")

        cur.execute(
            "INSERT INTO mentors (user_id, name, subject, price, description) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, subject, price, desc)
        )
        conn.commit()

        await message.answer(
            "🎉 <b>Arizangiz qabul qilindi!</b>\n"
            "Moderatorlarimiz ma'lumotlaringizni tekshirib, profilingizni mentorlar ro'yxatiga qo'shishadi.",
            parse_mode="HTML"
        )
        try:
            await bot.send_message(
                ADMIN_ID,
                f"🆕 <b>Yangi Mentor arizasi:</b>\nIsmi: {name}\nFan: {subject}\nNarx: {price:,} so'm\nIzoh: {desc}",
                parse_mode="HTML"
            )
        except Exception:
            pass

    elif action == "sos":
        await message.answer(
            "🚨 <b>SOS Tezkor Yordam so'rovi yuborildi!</b>\n\n"
            "Hozir onlayn bo'lgan barcha Top-Mentorlarga xabar yuborildi. 5 daqiqa ichida siz bilan bog'lanishadi.",
            parse_mode="HTML"
        )

    conn.close()

@dp.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: types.CallbackQuery):
    order_id = callback.data.split("_")[1]
    
    conn = sqlite3.connect("unimate.db")
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = 'Muzlatilgan (Escrow)' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()

    finish_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Dars yakunlandi (Pulni mentorga o'tkazish)", callback_data=f"done_{order_id}")]
    ])

    await callback.message.edit_text(
        f"💳 <b>To'lov muvaffaqiyatli qabul qilindi! (Buyurtma #{order_id})</b>\n\n"
        "🔒 Mablag' tizimda xavfsiz muzlatildi.\n"
        f"Mentor bilan bog'lanish kodi: <b>#MU{order_id}</b>\n\n"
        "<i>Dars tugagach, quyidagi tugmani bosing:</i>",
        reply_markup=finish_kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("done_"))
async def finish_lesson(callback: types.CallbackQuery):
    order_id = callback.data.split("_")[1]
    
    conn = sqlite3.connect("unimate.db")
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = 'Yakunlangan' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()

    await callback.message.edit_text(
        f"🌟 <b>Dars yakunlandi! (Buyurtma #{order_id})</b>\n\n"
        "Mablag' mentorga o'tkazildi va sizga <b>+10 UniCoin</b> bonus berildi! Rahmat!",
        parse_mode="HTML"
    )

async def serve_webapp(request):
    return web.FileResponse("index.html")

async def main():
    init_db()
    app = web.Application()
    app.router.add_get("/", serve_webapp)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("Mini-App server 8080-portda ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
