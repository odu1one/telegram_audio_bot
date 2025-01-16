from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from dotenv import load_dotenv
import os
import yt_dlp
import logging
import re
from transliterate import translit

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Загружаем переменные из файла .env
load_dotenv()

# Получаем токен из переменной окружения
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Функция для нормализации имени файла
def sanitize_filename(filename):
    # Преобразуем кириллицу в латиницу
    filename = translit(filename, 'ru', reversed=True)
    # Убираем все символы, кроме букв, цифр, пробелов и дефисов
    filename = re.sub(r'[^\w\s-]', '', filename).strip()
    # Преобразуем пробелы и дефисы в подчёркивания
    filename = re.sub(r'[-\s]+', '_', filename)
    return filename

# Функция для скачивания аудио
def download_audio(link, output_path="downloads"):
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{output_path}/%(title)s.%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(link, download=True)
        original_title = info['title']
        logging.info(f"Оригинальное имя видео: {original_title}")

        # Генерация безопасного имени файла
        safe_title = sanitize_filename(original_title)
        logging.info(f"Безопасное имя файла: {safe_title}")

        # Определяем пути
        expected_path = os.path.join(output_path, f"{original_title}.mp3")
        safe_path = os.path.join(output_path, f"{safe_title}.mp3")

        # Проверяем файлы в папке downloads
        logging.info("Файлы в папке 'downloads':")
        for file in os.listdir(output_path):
            logging.info(file)

        # Проверяем существование файла
        if os.path.exists(expected_path):
            logging.info(f"Файл найден: {expected_path}")
            os.rename(expected_path, safe_path)
            return safe_path
        elif any(file.endswith(".mp3") for file in os.listdir(output_path)):
            logging.warning("Оригинальный файл не найден, но MP3 присутствует. Используем первый найденный.")
            mp3_file = next(file for file in os.listdir(output_path) if file.endswith(".mp3"))
            return os.path.join(output_path, mp3_file)
        else:
            raise FileNotFoundError(
                f"Файл {expected_path} не найден. Проверьте имя и путь."
            )

# Обработка команды /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Привет! Отправь мне ссылку на видео с YouTube, и я конвертирую её в аудио для тебя!"
    )

# Обработка сообщений с ссылками
async def handle_message(update: Update, context: CallbackContext):
    link = update.message.text
    if "youtube.com" in link or "youtu.be" in link:
        try:
            await update.message.reply_text("Скачиваю и обрабатываю аудио, подожди немного...")
            audio_file = download_audio(link)
            with open(audio_file, "rb") as file:
                await update.message.reply_audio(file)
            os.remove(audio_file)
        except Exception as e:
            await update.message.reply_text(f"Произошла ошибка: {e}")
    else:
        await update.message.reply_text("Пожалуйста, отправь ссылку на YouTube.")

# Основная функция
def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == "__main__":
    main()
