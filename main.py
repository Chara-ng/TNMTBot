import asyncio
import logging
import json
import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import os

# Настройка бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OWNER_ID = 8100863185

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# База данных
users_db = {}

# Уровни подписок
SUBSCRIPTIONS = {
    "sayori": {
        "name": "💙 Сайори",
        "price": "299₽/мес",
        "level": 1,
        "content": ["Мемы", "Мини-спойлеры", "1 уровень поддержки"],
        "next_level": "natsuki"
    },
    "natsuki": {
        "name": "💗 Нацуки", 
        "price": "599₽/мес",
        "level": 2,
        "content": ["Приватные мемы", "Арты 16+", "2 уровень поддержки"],
        "next_level": "yuri"
    },
    "yuri": {
        "name": "💜 Юри",
        "price": "999₽/мес",
        "level": 3, 
        "content": ["Арты 18+", "3 уровень поддержки"],
        "next_level": "monika"
    },
    "monika": {
        "name": "💚 Моника",
        "price": "1499₽/мес",
        "level": 4,
        "content": ["Ранний доступ к играм", "Золотое место в списке поддержки"]
    }
}

def save_user_data():
    try:
        with open('users.json', 'w', encoding='utf-8') as f:
            json.dump(users_db, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error saving user data: {e}")

def load_user_data():
    global users_db
    try:
        with open('users.json', 'r', encoding='utf-8') as f:
            users_db = json.load(f)
    except FileNotFoundError:
        users_db = {}
        logging.info("users.json not found, creating new database")
    except Exception as e:
        users_db = {}
        logging.error(f"Error loading user data: {e}")

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id not in users_db:
        users_db[user_id] = {
            'username': message.from_user.username,
            'first_name': message.from_user.first_name,
            'subscription_level': 0,
            'subscription_end': None,
            'agreement_accepted': False
        }
        save_user_data()
    
    if not users_db[user_id]['agreement_accepted']:
        await show_license_agreement(message)
        return
    
    await show_main_menu(message)

async def show_license_agreement(message: types.Message):
    agreement_text = """
📜 <b>ЛИЦЕНЗИОННОЕ СОГЛАШЕНИЕ</b>

⚠️ <b>ЗАПРЕЩЕНО:</b>
• Распространение платного контента
• Передача файлов третьим лицам  
• Публикация материалов в открытых источниках

<b>НАРУШЕНИЕ ПРАВИЛ ПРИВОДИТ К:</b>
• Мгновенному снятию подписки
• Блокировке доступа
• Юридическим последствиям

Для продолжения необходимо принять соглашение.
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data="accept_agreement")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data="reject_agreement")]
    ])
    
    await message.answer(agreement_text, reply_markup=keyboard)

@dp.callback_query(F.data == "accept_agreement")
async def accept_agreement(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    users_db[user_id]['agreement_accepted'] = True
    save_user_data()
    await callback.message.edit_text("✅ Соглашение принято!")
    await show_main_menu(callback.message)

@dp.callback_query(F.data == "reject_agreement")
async def reject_agreement(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ Для использования бота необходимо принять соглашение.")

async def show_main_menu(message: types.Message):
    user_id = str(message.from_user.id)
    user_data = users_db.get(user_id, {})
    
    if user_data.get('subscription_level', 0) > 0:
        sub_name = [sub['name'] for sub in SUBSCRIPTIONS.values() if sub['level'] == user_data['subscription_level']][0]
        end_date = user_data.get('subscription_end', 'Неизвестно')
        status_text = f"✅ Активная подписка: {sub_name}\n📅 До: {end_date}"
    else:
        status_text = "❌ Нет активной подписки"
    
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 Список подписок")],
        [KeyboardButton(text="🎁 Мой контент"), KeyboardButton(text="👤 Моя подписка")],
        [KeyboardButton(text="📞 Поддержка")]
    ], resize_keyboard=True)
    
    await message.answer(
        f"👋 Добро пожаловать, {message.from_user.first_name}!\n\n"
        f"{status_text}\n\n"
        f"Выберите действие:",
        reply_markup=keyboard
    )

@dp.message(F.text == "📋 Список подписок")
async def show_subscriptions(message: types.Message):
    text = "🎭 <b>Доступные подписки:</b>\n\n"
    
    for key, sub in SUBSCRIPTIONS.items():
        text += f"{sub['name']} - {sub['price']}\n"
        text += f"Уровень: {sub['level']}\n"
        text += "Включает:\n"
        for item in sub['content']:
            text += f"• {item}\n"
        text += "\n"
    
    text += "\n💡 Каждый следующий уровень включает все предыдущие!"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=sub['name'], callback_data=f"buy_{key}")] 
        for key, sub in SUBSCRIPTIONS.items()
    ])
    
    await message.answer(text, reply_markup=keyboard)

@dp.message(F.text == "🎁 Мой контент")
async def show_my_content(message: types.Message):
    user_id = str(message.from_user.id)
    user_level = users_db.get(user_id, {}).get('subscription_level', 0)
    
    if user_level == 0:
        await message.answer("❌ У вас нет активной подписки!")
        return
    
    content_messages = []
    
    if user_level >= 1:  # Sayori
        content_messages.append("💙 <b>Контент Сайори:</b>\n• Мемы\n• Мини-спойлеры")
        
    if user_level >= 2:  # Natsuki  
        content_messages.append("💗 <b>Контент Нацуки:</b>\n• Приватные мемы\n• Арты 16+")
        
    if user_level >= 3:  # Yuri
        content_messages.append("💜 <b>Контент Юри:</b>\n• Арты 18+")
        
    if user_level >= 4:  # Monika
        content_messages.append("💚 <b>Контент Моники:</b>\n• Ранний доступ к играм")
    
    for msg in content_messages:
        await message.answer(msg)

@dp.message(F.text == "👤 Моя подписка")
async def show_my_subscription(message: types.Message):
    user_id = str(message.from_user.id)
    user_data = users_db.get(user_id, {})
    
    if user_data.get('subscription_level', 0) == 0:
        await message.answer("❌ У вас нет активной подписки!")
        return
    
    sub_name = [sub['name'] for sub in SUBSCRIPTIONS.values() if sub['level'] == user_data['subscription_level']][0]
    end_date = user_data.get('subscription_end', 'Неизвестно')
    
    text = f"""
📊 <b>Ваша подписка:</b>
🎭 Уровень: {sub_name}
📅 Действует до: {end_date}
👤 Ваш ID: {user_id}

💡 Доступные уровни: {', '.join([sub['name'] for sub in SUBSCRIPTIONS.values() if sub['level'] <= user_data['subscription_level']])}
    """
    
    await message.answer(text)

# Админ команды
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ Доступ запрещен!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Список подписчиков", callback_data="admin_users")],
        [InlineKeyboardButton(text="➕ Выдать подписку", callback_data="admin_add_sub")]
    ])
    
    await message.answer("👑 <b>Панель администратора</b>", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("admin_"))
async def admin_actions(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("❌ Доступ запрещен!")
        return
    
    action = callback.data
    
    if action == "admin_stats":
        active_subs = sum(1 for user in users_db.values() if user.get('subscription_level', 0) > 0)
        total_users = len(users_db)
        
        stats_text = f"""
📊 <b>Статистика:</b>
👥 Всего пользователей: {total_users}
✅ Активных подписок: {active_subs}

По уровням:
"""
        for level in range(1, 5):
            count = sum(1 for user in users_db.values() if user.get('subscription_level', 0) == level)
            level_name = [sub['name'] for sub in SUBSCRIPTIONS.values() if sub['level'] == level][0]
            stats_text += f"{level_name}: {count} пользователей\n"
        
        await callback.message.edit_text(stats_text)
    
    elif action == "admin_users":
        users_list = "👥 <b>Список подписчиков:</b>\n\n"
        for user_id, user_data in users_db.items():
            if user_data.get('subscription_level', 0) > 0:
                sub_name = [sub['name'] for sub in SUBSCRIPTIONS.values() if sub['level'] == user_data['subscription_level']][0]
                users_list += f"👤 {user_data['first_name']} (ID: {user_id})\n🎭 {sub_name}\n📅 До: {user_data.get('subscription_end', 'Неизвестно')}\n\n"
        
        await callback.message.edit_text(users_list or "❌ Нет активных подписчиков")
    
    elif action == "admin_add_sub":
        await callback.message.edit_text(
            "Выберите уровень подписки для выдачи:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=sub['name'], callback_data=f"addsub_{key}")] 
                for key, sub in SUBSCRIPTIONS.items()
            ])
        )

@dp.callback_query(F.data.startswith("addsub_"))
async def add_subscription_menu(callback: types.CallbackQuery):
    sub_key = callback.data.replace("addsub_", "")
    sub_level = SUBSCRIPTIONS[sub_key]['level']
    
    await callback.message.edit_text(
        f"Для выдачи подписки {SUBSCRIPTIONS[sub_key]['name']} используйте команду:\n\n"
        f"<code>/addsub USER_ID DAYS</code>\n\n"
        f"Пример: <code>/addsub 123456789 30</code>"
    )

@dp.message(Command("addsub"))
async def add_subscription_command(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("❌ Формат: /addsub USER_ID DAYS")
            return
            
        user_id = str(parts[1])
        days = int(parts[2])
        
        if user_id not in users_db:
            await message.answer("❌ Пользователь не найден в базе")
            return
        
        end_date = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%d.%m.%Y")
        users_db[user_id]['subscription_level'] = 4  # Максимальный уровень
        users_db[user_id]['subscription_end'] = end_date
        save_user_data()
        
        await message.answer(f"✅ Подписка Моника выдана пользователю {user_id} до {end_date}")
        
        # Уведомляем пользователя
        try:
            await bot.send_message(int(user_id), f"🎉 Вам выдана подписка Моника до {end_date}!")
        except:
            await message.answer("⚠️ Не удалось уведомить пользователя")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = """
🤖 <b>Доступные команды:</b>

/start - Начать работу
/help - Помощь

📋 <b>Основные функции:</b>
• Просмотр доступных подписок
• Получение контента по подписке
• Управление своей подпиской
"""
    await message.answer(help_text)

# Загрузка данных при старте
load_user_data()

async def main():
    logging.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
