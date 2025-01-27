from telegram.ext import Application, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv
import os
import yt_dlp
import logging
import re
from transliterate import translit
import subprocess
import math

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO)

# Загружаем переменные из файла .env
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

def sanitize_filename(filename):
    filename = translit(filename, 'ru', reversed=True)
    filename = re.sub(r'[^\w\s-]', '', filename).strip()
    filename = re.sub(r'[-\s]+', '_', filename)
    return filename

def calculate_segment_times(file_path, max_size_mb):
    """
    Вычисляет длины сегментов для файла, чтобы каждый сегмент был меньше max_size_mb.
    """
    # Получаем общую длину файла и битрейт
    command = ["ffprobe", "-v", "error", "-show_entries", "format=duration,bit_rate",
               "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise Exception(f"Ошибка ffprobe: {result.stderr}")

    duration, bit_rate = map(float, result.stdout.strip().split('\n'))

    # Вычисляем максимальную длину сегмента в секундах
    max_bytes = max_size_mb * 1024 * 1024
    max_duration = max_bytes / (bit_rate / 8)

    # Дробим на части, округляя до ближайшего целого числа секунд
    segment_times = []
    current_time = 0
    while current_time < duration:
        segment_times.append(min(max_duration, duration - current_time))
        current_time += max_duration

    return segment_times

def segment_audio_by_size(input_file, output_path, max_size_mb=49):
    """
    Сегментирует аудио файл по размеру в мегабайтах.
    """
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    base_name = os.path.splitext(os.path.basename(input_file))[0]
    segment_times = calculate_segment_times(input_file, max_size_mb)
    output_files = []

    start_time = 0
    for idx, duration in enumerate(segment_times):
        output_file = os.path.join(output_path, f"{base_name}_part_{idx + 1:03d}.mp3")
        command = [
            "ffmpeg", "-i", input_file, "-ss", str(int(start_time)), "-t", str(int(duration)),
            "-c", "copy", output_file
        ]
        logging.info(f"Выполняется команда: {' '.join(command)}")
        subprocess.run(command, check=True)
        output_files.append(output_file)
        start_time += duration

    return output_files

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
        safe_title = sanitize_filename(original_title)

        expected_path = os.path.join(output_path, f"{original_title}.mp3")
        safe_path = os.path.join(output_path, f"{safe_title}.mp3")

        if os.path.exists(expected_path):
            os.rename(expected_path, safe_path)
            segment_files = segment_audio_by_size(safe_path, output_path)
            os.remove(safe_path)
            return segment_files
        elif any(file.endswith(".mp3") for file in os.listdir(output_path)):
            logging.warning("Оригинальный файл не найден, но MP3 присутствует. Используем первый найденный.")
            mp3_file = next(file for file in os.listdir(output_path) if file.endswith(".mp3"))
            segment_files = segment_audio_by_size(os.path.join(output_path, mp3_file), output_path)
            os.remove(os.path.join(output_path, mp3_file))
            return segment_files
        else:
            raise FileNotFoundError(f"Файл {expected_path} не найден. Проверьте имя и путь.")

async def start(update, context):
    await update.message.reply_text(
        "Привет! Отправь мне ссылку на видео с YouTube, и я конвертирую её в аудио для тебя!"
    )

async def handle_message(update, context):
    link = update.message.text
    if "youtube.com" in link or "youtu.be" in link:
        try:
            await update.message.reply_text("Скачиваю и обрабатываю аудио, подожди немного...")
            audio_files = download_audio(link)

            for idx, audio_file in enumerate(audio_files, start=1):
                size_mb = os.path.getsize(audio_file) / (1024 * 1024)
                if size_mb > 49:
                    await update.message.reply_text(f"Ошибка: Сегмент {os.path.basename(audio_file)} слишком большой ({size_mb:.2f} MB). Попробуйте уменьшить размер файла.")
                    logging.error(f"Сегмент {audio_file} слишком большой: {size_mb:.2f} MB")
                    continue

                with open(audio_file, "rb") as file:
                    part_name = f"Part {idx} - " if len(audio_files) > 1 else ""
                    await update.message.reply_audio(file, filename=f"{part_name}{os.path.basename(audio_file)}")

                os.remove(audio_file)
        except Exception as e:
            await update.message.reply_text(f"Произошла ошибка: {e}")
            logging.error(f"Ошибка: {e}")
    else:
        await update.message.reply_text("Пожалуйста, отправь ссылку на YouTube.")

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == "__main__":
    main()
