import os
import yt_dlp
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# Загрузка переменных из .env
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Функция для скачивания аудио с использованием cookies
def download_audio_with_cookies(link, output_path="downloads"):
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{output_path}/%(title)s.%(ext)s",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        # Путь к файлу cookies. Убедитесь, что 'cookies.txt' существует.
        "cookiefile": "cookies.txt",
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(link, download=True)
        return info["title"]

# Команда /start
async def start(update, context):
    await update.message.reply_text(
        "Привет! Отправь мне ссылку на видео с YouTube, и я сконвертирую её в аудио для тебя!"
    )

# Обработка сообщений
async def handle_message(update, context):
    link = update.message.text
    if "youtube.com" in link or "youtu.be" in link:
        try:
            await update.message.reply_text("Скачиваю и обрабатываю аудио, подожди немного...")
            title = download_audio_with_cookies(link)
            await update.message.reply_text(f"Аудио {title} успешно скачано!")
        except Exception as e:
            await update.message.reply_text(f"Произошла ошибка: {e}")
    else:
        await update.message.reply_text("Пожалуйста, отправь ссылку на YouTube.")

# Основная функция
def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.run_polling()

if __name__ == "__main__":
    main()
