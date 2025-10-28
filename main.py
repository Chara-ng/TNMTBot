import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Настройка бота
BOT_TOKEN = "8192833881:AAH84QxRxPsdCUa2lXOZOn7MFnFa4NsU2kk"

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user = message.from_user
    
    welcome_text = f"""
👋 <b>Привет, {user.first_name}!</b>

Рад тебя видеть в нашем боте!
Твой ID: <code>{user.id}</code>

Используй команду /start чтобы увидеть это сообщение снова.
    """
    
    await message.answer(welcome_text)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
