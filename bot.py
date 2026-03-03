import asyncio
import os
import uuid
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
import yt_dlp

# === КОНФИГ ===
BOT_TOKEN = "8491652662:AAHlBurwLheVFbxMVqDBa3pPATtw8Eg5uc0"
CHANNEL_ID = "@scam_or_gem" # ID или username канала для проверки подписки
CHANNEL_URL = "https://t.me/scam_or_gem"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Временное хранилище найденных треков
search_cache = {}

# --- ПРОВЕРКА ПОДПИСКИ ---
async def is_subscribed(user_id: int):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# --- ФУНКЦИИ ПОИСКА И ЗАГРУЗКИ ---
# --- ФУНКЦИИ ПОИСКА И ЗАГРУЗКИ ---
def search_songs(query: str):
    # Удалили лишний def search_songs, который был на строке 31
    search_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'default_search': 'ytsearch5',
    }
    with yt_dlp.YoutubeDL(search_opts) as ydl:
        # Здесь куки не нужны для поиска
        info = ydl.extract_info(f"ytsearch5:{query}", download=False)
        return info['entries']

def download_audio(url: str):
    ydl_opts = {
        'format': 'bestaudio/best',
        # Оставляем только эту настройку для имени:
        'outtmpl': 'downloads/%(title)s.%(ext)s', 
        'cookiefile': 'vk.com_cookies', 
        'ffmpeg_location': os.getcwd(),
        'nocheckcertificate': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # 1. Скачиваем и получаем инфо о файле
        info = ydl.extract_info(url, download=True)
        # 2. Узнаем точное имя, которое дал yt-dlp
        file_path = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
        # 3. Возвращаем реальный путь и название для Телеграма
        return file_path, info.get('title', 'Unknown'), info.get('uploader', 'Artist')

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # Узнаем, как yt-dlp назвал файл
        file_path = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
        # Возвращаем ТРИ значения: путь, заголовок и артиста
        return file_path, info.get('title', 'Unknown'), info.get('uploader', 'Artist')

# --- ХЭНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    # Приветствие в стиле скриншотов
    text = (
        "👋 **Привет! Я помогу тебе найти и скачать любую музыку.**\n\n"
        "🔎 **Как искать?**\n"
        "Просто напиши название песни или имя исполнителя.\n\n"
        "📢 *Для работы бота нужно быть подписанным на наш канал:*"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подписаться на канал 🚀", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="Добавить в группу ⤴️", url=f"https://t.me/твой_бот?startgroup=true")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.message(F.text)
async def handle_search(message: Message):
    if not await is_subscribed(message.from_user.id):
        await message.answer("❌ **Доступ закрыт!**\nСначала подпишись на наш канал, чтобы скачивать музыку.", 
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="Подписаться", url=CHANNEL_URL)]
                             ]))
        return

    query = message.text
    status_msg = await message.answer(f"🔍 Ищу «{query}» по всему интернету...")

    try:
        results = await asyncio.to_thread(search_songs, query)
        
        kb_list = []
        for res in results:
            # Генерируем уникальный ключ для кэша
            track_key = str(uuid.uuid4())[:8]
            search_cache[track_key] = res['url']
            
            # Кнопка с названием и длительностью
            dur = f"{res['duration'] // 60}:{res['duration'] % 60:02d}"
            kb_list.append([InlineKeyboardButton(text=f"🎵 {res['title']} ({dur})", callback_data=f"song_{track_key}")])

        await status_msg.edit_text("Вот что я нашел 👇", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list))
    except:
        await status_msg.edit_text("❌ Ничего не нашлось. Попробуй уточнить название.")

@dp.callback_query(F.data.startswith("song_"))
async def process_dl(callback: CallbackQuery):
    track_key = callback.data.split("_")[1]
    url = search_cache.get(track_key)

    if not url:
        await callback.answer("Ошибка: поиск устарел. Введите запрос снова.")
        return

    await callback.message.answer("📥 Начинаю загрузку трека...")
    await callback.answer()

    file_id = str(uuid.uuid4())
    mp3_path = None

    try:
        # ПЕРЕДАЕМ ТОЛЬКО url. Никаких file_id!
        mp3_path, title, artist = await asyncio.to_thread(download_audio, url)
        
        audio = FSInputFile(mp3_path)
        
        # Отправляем с нормальными метаданными
        await bot.send_audio(
            chat_id=callback.message.chat.id,
            audio=audio,
            performer=artist, # Красивое имя артиста
            title=title,      # Красивое название песни
            caption=f"✅ {title} загружен!"
        )
    except Exception as e:
        await callback.message.answer("❌ Ошибка при скачивании этого файла.")
    finally:
        # ОЧИСТКА ДИСКА (сразу после отправки)
        if mp3_path and os.path.exists(mp3_path):
            os.remove(mp3_path)

async def main():
    if not os.path.exists('downloads'): os.makedirs('downloads')
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())