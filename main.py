import os
import asyncio
import logging
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, 
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    BotCommand
)
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# ⚙️ SOZLAMALAR
BOT_TOKEN = os.getenv("BOT_TOKEN", "8745420312:AAE6xB0qADkWOWZIj0GleM8u-fioQsZQ_uc")
ADMIN_IDS = [8065627948]  # O'zingizning Telegram ID raqamingiz

# Kanalingiz ID raqami va taklif havolasi
REQUIRED_CHANNEL_ID = -1004483339199
CHANNEL_INVITE_LINK = "https://t.me/+Vg4FF3ipPfQ3NzA6"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Holatlar (FSM)
class OrderState(StatesGroup):
    waiting_for_movie_name = State()

class AdminAddMovieState(StatesGroup):
    code = State()
    title = State()
    genre = State()
    country = State()
    year = State()
    desc = State()
    photo = State()
    quality = State()
    video = State()

# Ma'lumotlar bazasini yaratish
def init_db():
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            title TEXT,
            genre TEXT,
            country TEXT,
            year TEXT,
            desc TEXT,
            photo TEXT,
            quality TEXT,
            video TEXT,
            views INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER,
            code TEXT,
            PRIMARY KEY (user_id, code)
        )
    """)
    conn.commit()
    conn.close()

# --- RENDER UCHUN VEB-SERVER ---
async def handle(request):
    return web.Response(text="Bot muvaffaqiyatli ishlayapti!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- MAJBURIY OBUNANI TEKSHIRISH FUNKSIYASI ---
async def check_subscription(user_id: int) -> bool:
    if not REQUIRED_CHANNEL_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL_ID, user_id=user_id)
        if member.status in ["creator", "administrator", "member"]:
            return True
    except Exception as e:
        print(f"Obunani tekshirishda xatolik: {e}")
    return False

# Obuna bo'lish tugmasi
def get_sub_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", url=CHANNEL_INVITE_LINK)],
            [InlineKeyboardButton(text="🔄 Obunani tekshirish", callback_data="check_sub")]
        ]
    )

# --- EKTRANDA CHIQADIGAN ASOSIY MENYU ---
def get_main_menu(user_id: int):
    keyboard = [
        [
            InlineKeyboardButton(text="🔍 Kino qidirish", callback_data="menu_search"),
            InlineKeyboardButton(text="📂 Kataloglar", callback_data="menu_catalogs")
        ],
        [
            InlineKeyboardButton(text="🎭 Janrlar", callback_data="menu_genres"),
            InlineKeyboardButton(text="⭐ Sevimlilar", callback_data="menu_favorites")
        ],
        [
            InlineKeyboardButton(text="🎬 Kino buyurtma qilish", callback_data="menu_order"),
            InlineKeyboardButton(text="ℹ️ Ma'lumot", callback_data="menu_info")
        ]
    ]
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_main_menu")])
        
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- ADMIN PANEL MENYUSI ---
def get_admin_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="➕ Yangi kino qo'shish", callback_data="admin_add_movie")],
            [InlineKeyboardButton(text="📋 Kinolar ro'yxati va o'chirish", callback_data="admin_movie_list")],
            [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")]
        ]
    )

# Kino tafsilotlarini yuborish
async def send_movie_details(message: Message, m, increment_views=True):
    code, title, genre, country, year, desc, photo, quality, video, views = m
    
    if increment_views:
        conn_up = sqlite3.connect("movies.db")
        cur_up = conn_up.cursor()
        cur_up.execute("UPDATE movies SET views = views + 1 WHERE code = ?", (code,))
        conn_up.commit()
        conn_up.close()
        views += 1

    caption = (
        f"🎬 **{title}** ({year})\n"
        f"────────────────────────\n"
        f"🌍 **Davlat:** {country}\n"
        f"📂 **Janr:** {genre}\n"
        f"✨ **Sifat:** {quality}\n"
        f"👀 **Ko'rishlar:** {views} ta\n"
        f"────────────────────────\n"
        f"📝 **Tavsif:** {desc}\n\n"
        f"📲 **Kino kodi:** `{code}`"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Sevimlilarga qo'shish", callback_data=f"fav_add_{code}")],
            [InlineKeyboardButton(text="💬 Izohlar & Baholash", callback_data=f"review_{code}")],
            [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")]
        ]
    )
    if video and video.startswith("http"):
        keyboard.inline_keyboard.insert(2, [InlineKeyboardButton(text="📥 Kinoni ko'rish (Kanalga o'tish)", url=video)])

    try:
        if photo and photo.startswith("http"):
            await message.answer_photo(photo=photo, caption=caption, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await message.answer(caption, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        print(f"Yuborishda xatolik: {e}")

# Start komandasi
@dp.message(Command("start"))
async def start_cmd(message: Message):
    user_id = message.from_user.id
    
    if not await check_subscription(user_id):
        await message.answer(
            "⚠️ **Botdan foydalanish uchun avval quyidagi kanalimizga obuna bo'ling!**\n\nObuna bo'lgach, **'🔄 Obunani tekshirish'** tugmasini bosing.",
            reply_markup=get_sub_keyboard(),
            parse_mode="Markdown"
        )
        return

    await message.answer(
        "👋 **Assalomu alaykum!** Kino izlash uchun kod yoki nom yuboring, yoki quyidagi menyu tugmalaridan foydalaning:",
        reply_markup=get_main_menu(user_id),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    if await check_subscription(user_id):
        await callback.message.delete()
        await callback.message.answer(
            "✅ **Obunangiz tasdiqlandi!** Marhamat, asosiy menyu:",
            reply_markup=get_main_menu(user_id),
            parse_mode="Markdown"
        )
    else:
        await callback.answer("❌ Siz hali kanalga obuna bo'lmadingiz!", show_alert=True)

@dp.message(Command("admin"))
async def admin_panel_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Sizda admin huquqi yo'q!")
        return
    await message.answer("👑 **Admin Boshqaruv Paneli:**\nKerakli bo'limni tanlang:", reply_markup=get_admin_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "admin_main_menu")
async def admin_main_menu_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.message.answer("👑 **Admin Boshqaruv Paneli:**", reply_markup=get_admin_menu(), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(views) FROM movies")
    total_movies, total_views = cursor.fetchone()
    conn.close()
    
    if not total_views:
        total_views = 0
        
    text = (
        f"📊 **Statistika ma'lumotlari:**\n"
        f"────────────────────────\n"
        f"🎬 Jami kinolar: {total_movies} ta\n"
        f"👀 Jami ko'rishlar: {total_views} ta"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Ortga", callback_data="admin_main_menu")]]
    )
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "admin_add_movie")
async def start_add_movie(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminAddMovieState.code)
    await callback.message.answer("➕ **Yangi kino qo'shish**\n\n1️⃣ Kino uchun unikal **kod** kiriting (masalan: `107`):", parse_mode="Markdown")
    await callback.answer()

@dp.message(AdminAddMovieState.code)
async def process_admin_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip())
    await state.set_state(AdminAddMovieState.title)
    await message.answer("2️⃣ Kino nomini yuboring:")

@dp.message(AdminAddMovieState.title)
async def process_admin_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AdminAddMovieState.genre)
    await message.answer("3️⃣ Janrini kiriting (masalan: *Komediya, Kriminal*):")

@dp.message(AdminAddMovieState.genre)
async def process_admin_genre(message: Message, state: FSMContext):
    await state.update_data(genre=message.text.strip())
    await state.set_state(AdminAddMovieState.country)
    await message.answer("4️⃣ Ishlab chiqarilgan davlatini kiriting:")

@dp.message(AdminAddMovieState.country)
async def process_admin_country(message: Message, state: FSMContext):
    await state.update_data(country=message.text.strip())
    await state.set_state(AdminAddMovieState.year)
    await message.answer("5️⃣ Chiqqan yilini kiriting (masalan: *2025*):")

@dp.message(AdminAddMovieState.year)
async def process_admin_year(message: Message, state: FSMContext):
    await state.update_data(year=message.text.strip())
    await state.set_state(AdminAddMovieState.desc)
    await message.answer("6️⃣ Kino haqida qisqacha tavsif yuboring:")

@dp.message(AdminAddMovieState.desc)
async def process_admin_desc(message: Message, state: FSMContext):
    await state.update_data(desc=message.text.strip())
    await state.set_state(AdminAddMovieState.photo)
    await message.answer("7️⃣ Kino rasmining havolasini (URL) yuboring (agar yo'q bo'lsa `none` deb yozing):")

@dp.message(AdminAddMovieState.photo)
async def process_admin_photo(message: Message, state: FSMContext):
    await state.update_data(photo=message.text.strip())
    await state.set_state(AdminAddMovieState.quality)
    await message.answer("8️⃣ Sifatini kiriting (masalan: *HD 1080*):")

@dp.message(AdminAddMovieState.quality)
async def process_admin_quality(message: Message, state: FSMContext):
    await state.update_data(quality=message.text.strip())
    await state.set_state(AdminAddMovieState.video)
    await message.answer("9️⃣ Yopiq kanaldagi kinoning to'g'ridan-to'g'ri havolasini (linkini) yuboring (masalan: https://t.me/c/...):")

@dp.message(AdminAddMovieState.video)
async def process_admin_video(message: Message, state: FSMContext):
    data = await state.get_data()
    video = message.text.strip()
    
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO movies (code, title, genre, country, year, desc, photo, quality, video, views)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            data['code'], data['title'], data['genre'], data['country'],
            data['year'], data['desc'], data['photo'], data['quality'], video
        ))
        conn.commit()
        await message.answer("✅ **Kino muvaffaqiyatli bazaga qo'shildi!**", reply_markup=get_admin_menu(), parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi (Kod band bo'lishi mumkin): {e}", reply_markup=get_admin_menu())
    finally:
        conn.close()
        await state.clear()

@dp.callback_query(F.data == "admin_movie_list")
async def admin_movie_list(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT code, title FROM movies LIMIT 10")
    movies = cursor.fetchall()
    conn.close()
    
    keyboard_buttons = []
    for code, title in movies:
        keyboard_buttons.append([
            InlineKeyboardButton(text=f"🎬 {title}", callback_data="none"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_movie_{code}")
        ])
    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data="admin_main_menu")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.answer("📋 **So'nggi qo'shilgan kinolar:**", reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("del_movie_"))
async def delete_movie(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    code = callback.data.split("_")[2]
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movies WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    
    await callback.answer(f"🗑 {code}-kodli kino o'chirildi!", show_alert=True)
    await callback.message.delete()

@dp.callback_query(F.data == "menu_search")
async def cb_search(callback: CallbackQuery):
    await callback.message.answer("🔍 Marhamat, qidirmoqchi bo'lgan kino kodini yoki nomini yuboring:")
    await callback.answer()

@dp.callback_query(F.data == "menu_catalogs")
async def cb_catalogs(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Eng ko'p ko'rilganlar", callback_data="cat_popular")],
            [InlineKeyboardButton(text="🆕 So'nggi qo'shilganlar", callback_data="cat_new")],
            [InlineKeyboardButton(text="📋 Barcha kinolar ro'yxati", callback_data="cat_all")],
            [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")]
        ]
    )
    await callback.message.answer("📂 **Katalog bo'limi:**\nKerakli turkum yoki ro'yxatni tanlang:", reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "menu_genres")
async def cb_genres(callback: CallbackQuery):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT genre FROM movies WHERE genre IS NOT NULL AND genre != ''")
    rows = cursor.fetchall()
    conn.close()
    
    genres_set = set()
    for (g,) in rows:
        for part in g.replace(",", "/").split("/"):
            cleaned = part.strip()
            if cleaned:
                genres_set.add(cleaned)
                
    if not genres_set:
        await callback.message.answer("⚠️ Hozircha bazada janrlar mavjud emas.")
        await callback.answer()
        return
        
    keyboard_buttons = []
    row = []
    for g in sorted(genres_set):
        row.append(InlineKeyboardButton(text=f"📌 {g}", callback_data=f"genre_{g}"))
        if len(row) == 2:
            keyboard_buttons.append(row)
            row = []
    if row:
        keyboard_buttons.append(row)
        
    keyboard_buttons.append([InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.answer("🎭 **Kinolar janrlari:**\nO'zingizga yoqqan janrni tanlang:", reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "menu_favorites")
async def cb_favorites(callback: CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.code, m.title, m.year, m.quality 
        FROM favorites f 
        JOIN movies m ON f.code = m.code 
        WHERE f.user_id = ?
    """, (user_id,))
    favs = cursor.fetchall()
    conn.close()
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")]]
    )
    
    if not favs:
        await callback.message.answer("⭐ Sizning sevimlilar ro'yxatingiz hozircha bo'sh.", reply_markup=keyboard)
        await callback.answer()
        return
        
    text = "⭐ **Sizning sevimli kinolaringiz:**\n────────────────────────\n\n"
    for idx, (code, title, year, quality) in enumerate(favs, 1):
        text += f"{idx}. 🎬 **{title}** ({year}) | ✨ {quality}\n  📲 Kodi: `{code}`\n\n"
        
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "menu_order")
async def cb_order(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.waiting_for_movie_name)
    await callback.message.answer("🎬 Qaysi kinoni qo'shish kerak? Iltimos, kino nomini yozib yuboring:")
    await callback.answer()

@dp.message(OrderState.waiting_for_movie_name)
async def process_movie_order(message: Message, state: FSMContext):
    movie_name = message.text
    user_name = message.from_user.full_name
    user_id = message.from_user.id
    
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")]]
    )
    await message.answer("✅ Buyurtmangiz qabul qilindi! Adminlarga yuborildi.", reply_markup=keyboard)
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📥 **Yangi kino buyurtmasi!**\n\n"
                f"👤 Foydalanuvchi: {user_name} (`{user_id}`)\n"
                f"🎬 Kino nomi: {movie_name}"
            )
        except Exception:
            pass

@dp.callback_query(F.data == "menu_info")
async def cb_info(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")]]
    )
    await callback.message.answer("ℹ️ Bu bot yordamida sevimli kinolaringizni kodlari va janrlari bo'yicha topishingiz mumkin.", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    await callback.message.answer("🏠 **Asosiy menyu:**", reply_markup=get_main_menu(user_id), parse_mode="Markdown")
    await callback.answer()

@dp.message(F.text, ~F.text.startswith("/"))
async def handle_message(message: Message):
    user_id = message.from_user.id
    
    if not await check_subscription(user_id):
        await message.answer(
            "⚠️ **Botdan foydalanish uchun avval kanalimizga obuna bo'ling!**",
            reply_markup=get_sub_keyboard(),
            parse_mode="Markdown"
        )
        return

    query = message.text.strip()
    
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT code, title, genre, country, year, desc, photo, quality, video, views FROM movies WHERE code LIKE ? COLLATE NOCASE", (query,))
    movie_row = cursor.fetchone()

    if movie_row:
        conn.close()
        await send_movie_details(message, movie_row)
        return

    cursor.execute("SELECT code, title, genre, country, year, desc, photo, quality, video, views FROM movies WHERE title LIKE ? COLLATE NOCASE", (f"%{query}%",))
    found_movies = cursor.fetchall()
    conn.close()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")]]
    )

    if len(found_movies) == 1:
        await send_movie_details(message, found_movies[0])
    elif len(found_movies) > 1:
        text = f"🔍 **'{query}' bo'yicha topilgan kinolar:**\n────────────────────────\n\n"
        for m in found_movies:
            code, title, genre, country, year, desc, photo, quality, video, views = m
            text += f"▪️ **{title}** ({year}) | ✨ {quality}\n  📲 Kodi: `{code}`\n\n"
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await message.answer(
            "❌ Kechirasiz, bunday kino topilmadi.\n\nQidiruv so'zini xato yozgan bo'lishingiz mumkin yoki bu kino bazada yo'q.",
            reply_markup=keyboard
        )

@dp.callback_query(F.data == "cat_popular")
async def show_popular_movies(callback: CallbackQuery):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, genre, country, year, desc, photo, quality, video, views FROM movies ORDER BY views DESC LIMIT 10")
    movies = cursor.fetchall()
    conn.close()
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")]]
    )
    if not movies:
        await callback.message.answer("⚠️ Hozircha kinolar mavjud emas.", reply_markup=keyboard)
        await callback.answer()
        return
        
    text = "🔥 **Eng ko'p ko'rilgan sara kinolar:**\n────────────────────────\n\n"
    for idx, m in enumerate(movies, 1):
        code, title, genre, country, year, desc, photo, quality, video, views = m
        text += f"{idx}. 🎬 **{title}** ({year})\n  📂 {genre} | 👀 {views} ta\n  📲 Kodi: `{code}`\n\n"
        
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "cat_new")
async def show_new_movies(callback: CallbackQuery):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, genre, country, year, desc, photo, quality, video, views FROM movies ORDER BY year DESC LIMIT 10")
    movies = cursor.fetchall()
    conn.close()
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")]]
    )
    if not movies:
        await callback.message.answer("⚠️ Hozircha kinolar mavjud emas.", reply_markup=keyboard)
        await callback.answer()
        return
        
    text = "🆕 **Eng so'nggi qo'shilgan kinolar:**\n────────────────────────\n\n"
    for idx, m in enumerate(movies, 1):
        code, title, genre, country, year, desc, photo, quality, video, views = m
        text += f"{idx}. 🎬 **{title}** ({year})\n  📂 {genre} | ✨ {quality}\n  📲 Kodi: `{code}`\n\n"
        
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "cat_all")
async def show_all_movies(callback: CallbackQuery):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, genre, country, year, desc, photo, quality, video, views FROM movies LIMIT 15")
    movies = cursor.fetchall()
    conn.close()
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")]]
    )
    if not movies:
        await callback.message.answer("⚠️ Hozircha kinolar mavjud emas.", reply_markup=keyboard)
        await callback.answer()
        return
        
    text = "📋 **Bazadagi kinolar ro'yxati:**\n────────────────────────\n\n"
    for idx, m in enumerate(movies, 1):
        code, title, genre, country, year, desc, photo, quality, video, views = m
        text += f"{idx}. 🎬 **{title}** ({year})\n  📲 Kodi: `{code}`\n\n"
        
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("genre_"))
async def show_genre_movies(callback: CallbackQuery):
    genre_name = callback.data.split("_", 1)[1]
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, genre, country, year, desc, photo, quality, video, views FROM movies WHERE genre LIKE ?", (f"%{genre_name}%",))
    movies = cursor.fetchall()
    conn.close()
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")]]
    )
    if not movies:
        await callback.message.answer(f"⚠️ '{genre_name}' janrida kinolar topilmadi.", reply_markup=keyboard)
        await callback.answer()
        return
        
    text = f"🎭 **'{genre_name}' janridagi kinolar:**\n────────────────────────\n\n"
    for idx, m in enumerate(movies, 1):
        code, title, genre, country, year, desc, photo, quality, video, views = m
        text += f"{idx}. 🎬 **{title}** ({year})\n  ✨ {quality} | 👀 {views}\n  📲 Kodi: `{code}`\n\n"
        
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("fav_add_"))
async def fav_add_callback(callback: CallbackQuery):
    code = callback.data.split("_")[2]
    user_id = callback.from_user.id
    
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO favorites (user_id, code) VALUES (?, ?)", (user_id, code))
        conn.commit()
        await callback.answer(f"⭐ Kino sevimlilarga qo'shildi!", show_alert=True)
    except sqlite3.IntegrityError:
        await callback.answer(f"⚠️ Bu kino allaqachon sevimlilaringizda bor!", show_alert=True)
    finally:
        conn.close()

@dp.callback_query(F.data.startswith("review_"))
async def review_callback(callback: CallbackQuery):
    code = callback.data.split("_")[1]
    await callback.message.answer(f"💬 {code}-kodli kino uchun izoh qoldirishingiz mumkin.")
    await callback.answer()

async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    print("🤖 Bot muvaffaqiyatli ishga tushdi!")
    
    await bot.set_my_commands([
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="admin", description="Admin panel")
    ])
    
    # Render uchun aiohttp veb-serverini fonda ishga tushiramiz
    asyncio.create_task(start_web_server())
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot to'xtatildi!")
