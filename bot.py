import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton,
    InputFile, FSInputFile
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# Настройки
BOT_TOKEN = "8192833881:AAE776v47HR-09Sfcszu0HEktAlDFI_3GoU"
OWNER_ID = 8100863185
USERS_FILE = "users.json"
CONTENT_FILE = "content.json"

# Уровни подписок
class SubscriptionLevel(Enum):
    NONE = 0
    SAYORI = 1
    NATSUKI = 2
    YURI = 3
    MONIKA = 4

# Названия и описания подписок
SUBSCRIPTION_INFO = {
    SubscriptionLevel.SAYORI: {
        "name": "💙 Сайори",
        "price": "500 руб/мес",
        "description": "• Мемы\n• Мини-спойлеры\n• Список поддержавших 1 уровня"
    },
    SubscriptionLevel.NATSUKI: {
        "name": "💗 Нацуки", 
        "price": "1000 руб/мес",
        "description": "• Всё из Сайори\n• Приватные мемы\n• Арты 16+\n• Список поддержавших 2 уровня"
    },
    SubscriptionLevel.YURI: {
        "name": "💜 Юри",
        "price": "1500 руб/мес", 
        "description": "• Всё из Нацуки\n• Арты 18+\n• Список поддержавших 3 уровня"
    },
    SubscriptionLevel.MONIKA: {
        "name": "💚 Моника",
        "price": "2000 руб/мес",
        "description": "• Всё из Юри\n• Ранний доступ к играм\n• Золотое место в списке поддержавших"
    }
}

# Состояния для FSM
class AdminStates(StatesGroup):
    waiting_content = State()
    waiting_level = State()
    waiting_days = State()
    waiting_user_id = State()

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище для активных чатов
active_chats = {}

# Функции для работы с JSON
def load_users() -> Dict:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users(users: Dict):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_content() -> Dict:
    if os.path.exists(CONTENT_FILE):
        with open(CONTENT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"sent_content": []}

def save_content(content: Dict):
    with open(CONTENT_FILE, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=2)

# Вспомогательные функции
def get_subscription_end_date(days: int) -> str:
    return (datetime.now() + timedelta(days=days)).strftime("%d.%m.%Y")

def is_subscription_active(user_data: Dict) -> bool:
    if user_data.get("subscription_level", 0) == 0:
        return False
    
    end_date = user_data.get("subscription_end")
    if not end_date:
        return False
    
    try:
        end = datetime.strptime(end_date, "%d.%m.%Y")
        return datetime.now() <= end
    except:
        return False

def get_active_subscription_level(user_data: Dict) -> int:
    if is_subscription_active(user_data):
        return user_data.get("subscription_level", 0)
    return 0

async def notify_owner_about_purchase(user_id: int, username: str, level: SubscriptionLevel):
    subscription_info = SUBSCRIPTION_INFO[level]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Начать чат", callback_data=f"start_chat_{user_id}"),
        InlineKeyboardButton(text="✅ Выдать подписку", callback_data=f"addsub_{user_id}_{level.value}")
    ]])
    
    await bot.send_message(
        OWNER_ID,
        f"🛒 Новый запрос на подписку!\n\n"
        f"👤 Пользователь: @{username} (ID: {user_id})\n"
        f"💎 Уровень: {subscription_info['name']}\n"
        f"💰 Цена: {subscription_info['price']}\n\n"
        f"Начните чат для обсуждения оплаты",
        reply_markup=keyboard
    )

# Улучшенное лицензионное соглашение
def get_license_agreement(level: SubscriptionLevel) -> str:
    sub_info = SUBSCRIPTION_INFO[level]
    return (
        f"📄 ЛИЦЕНЗИОННОЕ СОГЛАШЕНИЕ - {sub_info['name']}\n\n"
        f"Перед оформлением подписки ознакомьтесь с условиями:\n\n"
        f"🔒 ОГРАНИЧЕНИЯ:\n"
        f"• Запрещено распространение контента\n"
        f"• Запрещена перепродажа доступа\n"
        f"• Контент только для личного использования\n"
        f"• Запрещено создание копий материалов\n\n"
        f"⚖️ ПОСЛЕДСТВИЯ НАРУШЕНИЙ:\n"
        f"• Немедленное снятие подписки\n"
        f"• Безвозвратное блокирование доступа\n"
        f"• Запрет на повторное оформление\n"
        f"• Возможность юридического преследования\n\n"
        f"📋 УСЛОВИЯ ПОДПИСКИ:\n"
        f"• Автопродление не предусмотрено\n"
        f"• Возврат средств не осуществляется\n"
        f"• Владелец вправе изменять условия\n"
        f"• Подписка действует до указанной даты\n\n"
        f"💎 Выбранный уровень: {sub_info['name']}\n"
        f"💰 Стоимость: {sub_info['price']}\n\n"
        f"✅ Нажимая 'Принять', вы соглашаетесь со всеми условиями"
    )

# Команды для пользователей
@dp.message(CommandStart())
async def cmd_start(message: Message):
    users = load_users()
    user_id = str(message.from_user.id)
    
    if user_id not in users:
        users[user_id] = {
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "subscription_level": 0,
            "subscription_end": None,
            "agreement_accepted": False,
            "join_date": datetime.now().strftime("%d.%m.%Y %H:%M")
        }
        save_users(users)
    
    user_data = users[user_id]
    
    if not user_data["agreement_accepted"]:
        await show_main_agreement(message)
        return
    
    await show_main_menu(message)

async def show_main_agreement(message: Message):
    agreement_text = (
        "📄 ОБЩЕЕ ЛИЦЕНЗИОННОЕ СОГЛАШЕНИЕ\n\n"
        "Добро пожаловать! Перед использованием бота необходимо принять соглашение:\n\n"
        "1. Контент предназначен только для личного использования\n"
        "2. Запрещено распространение материалов\n"
        "3. Нарушение ведет к блокировке доступа\n"
        "4. Автоматическое продление не предусмотрено\n\n"
        "✅ Принимая соглашение, вы подтверждаете ознакомление с условиями"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Принять соглашение", callback_data="accept_main_agreement")
    ]])
    
    await message.answer(agreement_text, reply_markup=keyboard)

@dp.callback_query(F.data == "accept_main_agreement")
async def accept_main_agreement(callback: CallbackQuery):
    users = load_users()
    user_id = str(callback.from_user.id)
    
    users[user_id]["agreement_accepted"] = True
    save_users(users)
    
    await callback.message.delete()
    await show_main_menu(callback.message)

async def show_main_menu(message: Message):
    users = load_users()
    user_id = str(message.from_user.id)
    user_data = users[user_id]
    current_level = get_active_subscription_level(user_data)
    
    if current_level > 0:
        sub_info = SUBSCRIPTION_INFO[SubscriptionLevel(current_level)]
        status_text = f"✅ Активна: {sub_info['name']}\n📅 До: {user_data['subscription_end']}"
    else:
        status_text = "❌ Нет активной подписки"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Подписки", callback_data="show_subscriptions")],
        [InlineKeyboardButton(text="📊 Моя подписка", callback_data="my_subscription"),
         InlineKeyboardButton(text="🆔 Мой ID", callback_data="my_id")],
        [InlineKeyboardButton(text="📞 Связаться", callback_data="contact_owner")]
    ])
    
    await message.answer(
        f"👋 Добро пожаловать!\n\n"
        f"📊 Статус подписки:\n{status_text}\n\n"
        f"Выберите действие:",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "my_id")
async def show_my_id(callback: CallbackQuery):
    await callback.answer(f"Ваш ID: {callback.from_user.id}", show_alert=True)

@dp.callback_query(F.data == "contact_owner")
async def contact_owner(callback: CallbackQuery):
    users = load_users()
    user_id = str(callback.from_user.id)
    user_data = users[user_id]
    
    # Создаем клавиатуру для владельца
    owner_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Ответить пользователю", callback_data=f"start_chat_{user_id}")
    ]])
    
    # Отправляем уведомление владельцу
    await bot.send_message(
        OWNER_ID,
        f"📞 Пользователь хочет связаться!\n\n"
        f"👤 @{user_data['username']} (ID: {user_id})\n"
        f"💎 Текущая подписка: {SUBSCRIPTION_INFO[SubscriptionLevel(user_data['subscription_level'])]['name'] if user_data['subscription_level'] > 0 else 'Нет'}\n"
        f"📅 Активна: {'Да' if is_subscription_active(user_data) else 'Нет'}",
        reply_markup=owner_keyboard
    )
    
    # Сообщаем пользователю
    await callback.message.answer(
        "📞 Запрос на связь отправлен владельцу!\n\n"
        "Ожидайте ответа. Когда владелец начнет чат, вы сможете общаться с ним напрямую."
    )

@dp.callback_query(F.data == "show_subscriptions")
async def show_subscriptions(callback: CallbackQuery):
    keyboard = InlineKeyboardBuilder()
    
    for level in [SubscriptionLevel.SAYORI, SubscriptionLevel.NATSUKI, 
                  SubscriptionLevel.YURI, SubscriptionLevel.MONIKA]:
        info = SUBSCRIPTION_INFO[level]
        keyboard.add(InlineKeyboardButton(
            text=f"{info['name']} - {info['price']}", 
            callback_data=f"subscribe_{level.value}"
        ))
    
    keyboard.adjust(1)
    
    await callback.message.edit_text(
        "💎 Выберите уровень подписки:\n\n"
        "Каждый следующий уровень включает в себя все преимущества предыдущих!",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(F.data.startswith("subscribe_"))
async def subscribe_request(callback: CallbackQuery):
    level = int(callback.data.split("_")[1])
    subscription = SubscriptionLevel(level)
    info = SUBSCRIPTION_INFO[subscription]
    
    # Показываем лицензионное соглашение перед подтверждением
    agreement_text = get_license_agreement(subscription)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять и продолжить", callback_data=f"confirm_sub_{level}")],
        [InlineKeyboardButton(text="❌ Отказаться", callback_data="show_subscriptions")]
    ])
    
    await callback.message.edit_text(
        agreement_text,
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("confirm_sub_"))
async def confirm_subscription(callback: CallbackQuery):
    level = int(callback.data.split("_")[2])
    subscription = SubscriptionLevel(level)
    
    await notify_owner_about_purchase(
        callback.from_user.id,
        callback.from_user.username,
        subscription
    )
    
    await callback.message.edit_text(
        "✅ Запрос отправлен владельцу!\n\n"
        "Скоро с вами свяжутся для уточнения деталей оплаты."
    )

@dp.callback_query(F.data == "my_subscription")
async def show_my_subscription(callback: CallbackQuery):
    users = load_users()
    user_id = str(callback.from_user.id)
    user_data = users[user_id]
    current_level = get_active_subscription_level(user_data)
    
    if current_level > 0:
        sub_info = SUBSCRIPTION_INFO[SubscriptionLevel(current_level)]
        text = (f"💎 Ваша подписка: {sub_info['name']}\n"
                f"📅 Действует до: {user_data['subscription_end']}\n\n"
                f"📋 Доступные преимущества:\n{sub_info['description']}")
    else:
        text = "❌ У вас нет активной подписки\n\nИспользуйте меню 'Подписки' для оформления"
    
    await callback.message.answer(text)

# Команды для владельца
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ Доступ запрещен")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
         InlineKeyboardButton(text="📤 Отправить контент", callback_data="admin_send_content")],
        [InlineKeyboardButton(text="➕ Выдать подписку", callback_data="admin_add_sub"),
         InlineKeyboardButton(text="❌ Снять подписку", callback_data="admin_remove_sub")],
        [InlineKeyboardButton(text="👥 Список подписчиков", callback_data="admin_subscribers")]
    ])
    
    await message.answer("🛠️ Панель администратора", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("start_chat_"))
async def start_chat_with_user(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    
    # Сохраняем информацию о активном чате
    active_chats[OWNER_ID] = user_id
    active_chats[user_id] = OWNER_ID
    
    user_info = await bot.get_chat(user_id)
    
    # Уведомляем владельца
    await callback.message.answer(
        f"💬 Чат с пользователем @{user_info.username} начат!\n\n"
        f"Теперь все ваши сообщения будут пересылаться этому пользователю.\n"
        f"Для завершения чата отправьте /stopchat"
    )
    
    # Уведомляем пользователя
    await bot.send_message(
        user_id,
        "💬 Владелец начал с вами чат!\n\n"
        "Теперь вы можете общаться напрямую. Все ваши сообщения будут пересылаться владельцу.\n"
        "Для завершения чата отправьте /stopchat"
    )

# Обработка сообщений владельца
@dp.message(F.from_user.id == OWNER_ID)
async def handle_owner_message(message: Message):
    # Проверяем команду /stopchat ДО проверки активного чата
    if message.text and message.text == '/stopchat':
        await stop_chat_owner(message)
        return
    
    # Проверяем, есть ли активный чат
    if OWNER_ID in active_chats:
        chat_user_id = active_chats[OWNER_ID]
        
        try:
            # Пересылаем сообщение пользователю
            if message.text:
                await bot.send_message(chat_user_id, f"💬 Владелец:\n\n{message.text}")
            elif message.photo:
                await bot.send_photo(chat_user_id, message.photo[-1].file_id, caption=f"💬 Владелец:\n\n{message.caption}" if message.caption else "💬 Владелец:")
            elif message.video:
                await bot.send_video(chat_user_id, message.video.file_id, caption=f"💬 Владелец:\n\n{message.caption}" if message.caption else "💬 Владелец:")
            elif message.document:
                await bot.send_document(chat_user_id, message.document.file_id, caption=f"💬 Владелец:\n\n{message.caption}" if message.caption else "💬 Владелец:")
            
            await message.answer("✅ Сообщение доставлено")
        except Exception as e:
            await message.answer(f"❌ Ошибка отправки: {e}")
    else:
        # Если нет активного чата, показываем обычное меню
        if message.text and message.text.startswith('/admin'):
            await admin_panel(message)
        else:
            await message.answer("Используйте /admin для доступа к панели управления")

# Обработка сообщений пользователя
@dp.message()
async def handle_user_message(message: Message):
    # Проверяем команду /stopchat ДО проверки активного чата
    if message.text and message.text == '/stopchat':
        await stop_chat_user(message)
        return
    
    # Проверяем, есть ли активный чат с этим пользователем
    if message.from_user.id in active_chats and message.from_user.id != OWNER_ID:
        try:
            # Пересылаем сообщение владельцу
            if message.text:
                await bot.send_message(OWNER_ID, f"💬 Пользователь @{message.from_user.username}:\n\n{message.text}")
            elif message.photo:
                await bot.send_photo(OWNER_ID, message.photo[-1].file_id, caption=f"💬 Пользователь @{message.from_user.username}:\n\n{message.caption}" if message.caption else f"💬 Пользователь @{message.from_user.username}:")
            elif message.video:
                await bot.send_video(OWNER_ID, message.video.file_id, caption=f"💬 Пользователь @{message.from_user.username}:\n\n{message.caption}" if message.caption else f"💬 Пользователь @{message.from_user.username}:")
            elif message.document:
                await bot.send_document(OWNER_ID, message.document.file_id, caption=f"💬 Пользователь @{message.from_user.username}:\n\n{message.caption}" if message.caption else f"💬 Пользователь @{message.from_user.username}:")
            
            await message.answer("✅ Сообщение доставлено владельцу")
        except Exception as e:
            await message.answer(f"❌ Ошибка отправки: {e}")
    elif message.from_user.id != OWNER_ID:
        # Если нет активного чата, показываем главное меню
        if message.text and message.text.startswith('/start'):
            await cmd_start(message)
        else:
            await show_main_menu(message)

# Завершение чата со стороны владельца
async def stop_chat_owner(message: Message):
    if OWNER_ID in active_chats:
        user_id = active_chats[OWNER_ID]
        
        # Уведомляем пользователя
        await bot.send_message(user_id, "💬 Чат с владельцем завершен.")
        
        # Удаляем из активных чатов
        if user_id in active_chats:
            del active_chats[user_id]
        del active_chats[OWNER_ID]
        
        await message.answer("💬 Чат завершен")
    else:
        await message.answer("❌ Нет активного чата")

# Завершение чата со стороны пользователя
async def stop_chat_user(message: Message):
    user_id = message.from_user.id
    if user_id in active_chats:
        owner_id = active_chats[user_id]
        
        # Уведомляем владельца
        await bot.send_message(owner_id, f"💬 Пользователь @{message.from_user.username} завершил чат.")
        
        # Удаляем из активных чатов
        del active_chats[user_id]
        if owner_id in active_chats:
            del active_chats[owner_id]
        
        await message.answer("💬 Чат с владельцем завершен.")
    else:
        await message.answer("❌ Нет активного чата")

@dp.callback_query(F.data.startswith("addsub_"))
async def add_subscription_owner(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split("_")
    user_id = int(data[1])
    level = int(data[2])
    
    await state.update_data(target_user=user_id, sub_level=level)
    await callback.message.answer("Введите количество дней подписки:")
    await state.set_state(AdminStates.waiting_days)

@dp.message(AdminStates.waiting_days)
async def process_days_input(message: Message, state: FSMContext):
    try:
        days = int(message.text)
        data = await state.get_data()
        user_id = data['target_user']
        level = data['sub_level']
        
        await add_subscription_to_user(user_id, level, days)
        
        await message.answer(f"✅ Подписка выдана пользователю {user_id} на {days} дней")
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите корректное число дней")

async def add_subscription_to_user(user_id: int, level: int, days: int):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        # Создаем базовую запись
        user_info = await bot.get_chat(user_id)
        users[user_id_str] = {
            "username": user_info.username,
            "first_name": user_info.first_name,
            "subscription_level": level,
            "subscription_end": get_subscription_end_date(days),
            "agreement_accepted": True,
            "join_date": datetime.now().strftime("%d.%m.%Y %H:%M")
        }
    else:
        users[user_id_str]["subscription_level"] = level
        users[user_id_str]["subscription_end"] = get_subscription_end_date(days)
    
    save_users(users)
    
    # Уведомляем пользователя
    sub_info = SUBSCRIPTION_INFO[SubscriptionLevel(level)]
    await bot.send_message(
        user_id,
        f"🎉 Вам выдана подписка {sub_info['name']}!\n\n"
        f"📅 Действует до: {get_subscription_end_date(days)}\n\n"
        f"📋 Теперь вам доступно:\n{sub_info['description']}"
    )

# Отправка контента
@dp.callback_query(F.data == "admin_send_content")
async def admin_send_content(callback: CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💙 Сайори", callback_data="content_level_1")],
        [InlineKeyboardButton(text="💗 Нацуки", callback_data="content_level_2")],
        [InlineKeyboardButton(text="💜 Юри", callback_data="content_level_3")],
        [InlineKeyboardButton(text="💚 Моника", callback_data="content_level_4")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
    ])
    
    await callback.message.answer(
        "📤 Выберите уровень подписки для отправки контента:\n\n"
        "Контент получат все пользователи с выбранным уровнем и выше",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("content_level_"))
async def select_content_level(callback: CallbackQuery, state: FSMContext):
    level = int(callback.data.split("_")[2])
    await state.update_data(content_level=level)
    await state.set_state(AdminStates.waiting_content)
    
    await callback.message.answer(
        f"📝 Отправьте контент для уровня {SUBSCRIPTION_INFO[SubscriptionLevel(level)]['name']} и выше\n\n"
        f"Можно отправить:\n• Текст\n• Фото\n• Видео\n• Документы"
    )

# Функция для отправки контента пользователям
async def send_content_to_users(content_level: int, message: Message):
    users = load_users()
    sent_count = 0
    failed_count = 0
    
    for user_id_str, user_data in users.items():
        user_level = get_active_subscription_level(user_data)
        if user_level >= content_level:
            try:
                # Копируем сообщение пользователю
                await message.send_copy(chat_id=int(user_id_str))
                sent_count += 1
            except Exception as e:
                print(f"Ошибка отправки пользователю {user_id_str}: {e}")
                failed_count += 1
    
    return sent_count, failed_count

@dp.message(AdminStates.waiting_content)
async def process_content_sending(message: Message, state: FSMContext):
    data = await state.get_data()
    target_level = data['content_level']
    
    sent_count, failed_count = await send_content_to_users(target_level, message)
    
    await message.answer(
        f"✅ Контент отправлен!\n\n"
        f"📊 Статистика:\n"
        f"• Успешно: {sent_count}\n"
        f"• Не удалось: {failed_count}"
    )
    await state.clear()

# Статистика
@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    users = load_users()
    
    active_subs = {1: 0, 2: 0, 3: 0, 4: 0}
    total_active = 0
    
    for user_data in users.values():
        if is_subscription_active(user_data):
            level = user_data["subscription_level"]
            active_subs[level] += 1
            total_active += 1
    
    stats_text = (
        f"📊 Статистика подписок:\n\n"
        f"👥 Всего пользователей: {len(users)}\n"
        f"✅ Активных подписок: {total_active}\n\n"
        f"💙 Сайори: {active_subs[1]}\n"
        f"💗 Нацуки: {active_subs[2]}\n"
        f"💜 Юри: {active_subs[3]}\n"
        f"💚 Моника: {active_subs[4]}"
    )
    
    await callback.message.answer(stats_text)

@dp.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Действие отменено")

# Запуск бота
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
