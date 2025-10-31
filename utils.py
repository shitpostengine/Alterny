from telegram import Bot
from config import BOT_TOKEN

# Кеш для медиафайлов
media_cache = {}


async def send_video(update, file_path, caption=""):
    chat_id = update.effective_chat.id
    bot = Bot(BOT_TOKEN)

    # Используем кешированный file_id если есть
    if file_path in media_cache:
        await bot.send_video(chat_id=chat_id, video=media_cache[file_path], caption=caption)
        return

    # Первая отправка - сохраняем file_id
    with open(file_path, 'rb') as video_file:
        message = await bot.send_video(chat_id=chat_id, video=video_file, caption=caption)
        media_cache[file_path] = message.video.file_id