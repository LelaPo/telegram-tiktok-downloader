import os
import logging
import requests
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor

load_dotenv()
API_TOKEN = os.getenv('API_TOKEN')  # ← теперь токен берётся из .env

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Функция для получения ссылки на видео без водяного знака
def download_tiktok_video(url: str) -> str:
    try:
        response = requests.get(f"https://tikwm.com/api/?url={url}")
        data = response.json()
        return data["data"]["play"]  # Прямая ссылка на видео
    except Exception as e:
        print("Ошибка:", e)
        return None

@dp.message_handler()
async def handle_message(message: Message):
    if "tiktok.com" in message.text:
        await message.reply("⏳ Скачиваю видео, подожди...")

        video_url = download_tiktok_video(message.text)
        if video_url:
            await message.answer_video(video_url, caption="🎬 Готово!")
        else:
            await message.reply("❌ Не удалось скачать видео. Убедись, что ссылка верна.")
    else:
        await message.reply("📎 Пришли мне ссылку на TikTok-видео.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)