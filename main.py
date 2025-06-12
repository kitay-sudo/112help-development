import asyncio
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode
from data.emergency_data import EmergencyData
import os
from dotenv import load_dotenv
import re
import time
from typing import Dict

from database.models import Database, User, CommandLog
from utils.logger import get_logger, log_info, log_error, log_warning, log_user_action, log_security_event

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("BOT_TOKEN не найден! Добавьте токен в файл .env")
    exit(1)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.MARKDOWN
    )
)
dp = Dispatcher()

# Инициализация данных
emergency_data = EmergencyData()

# === АНТИСПАМ СИСТЕМА ===
user_requests = defaultdict(list)
MAX_REQUESTS_PER_MINUTE = 30
SPAM_BAN_DURATION = 300  # 5 минут бана
banned_users = {}

# Получение списка админов
ADMIN_IDS = []
admin_ids_str = os.getenv('ADMIN_IDS', '')
if admin_ids_str:
    ADMIN_IDS = [int(id_str.strip()) for id_str in admin_ids_str.split(',') if id_str.strip()]

def is_admin(user_id: int) -> bool:
    """Проверка является ли пользователь администратором"""
    return user_id in ADMIN_IDS

def is_user_banned(user_id: int) -> bool:
    """Проверка бана пользователя"""
    if user_id in banned_users:
        if datetime.now() < banned_users[user_id]:
            return True
        else:
            del banned_users[user_id]
    return False

def check_rate_limit(user_id: int) -> bool:
    """Проверка лимита запросов"""
    now = datetime.now()
    minute_ago = now - timedelta(minutes=1)
    
    # Очистка старых запросов
    user_requests[user_id] = [req_time for req_time in user_requests[user_id] if req_time > minute_ago]
    
    # Проверка лимита
    if len(user_requests[user_id]) >= MAX_REQUESTS_PER_MINUTE:
        # Бан пользователя
        banned_users[user_id] = now + timedelta(seconds=SPAM_BAN_DURATION)
        return False
    
    # Добавление нового запроса
    user_requests[user_id].append(now)
    return True

# Middleware для антиспама
@dp.message.middleware()
async def anti_spam_middleware(handler, event: Message, data):
    user_id = event.from_user.id
    
    # Регистрация пользователя (создание или обновление активности)
    try:
        user = await User.get_or_create_user(
            user_id=user_id,
            username=event.from_user.username,
            first_name=event.from_user.first_name,
            last_name=event.from_user.last_name
        )
        if user:
            await user.update_activity()
    except Exception as e:
        logger.error(f"Ошибка регистрации пользователя {user_id}: {e}")
    
    # Проверка на блокировку
    if is_user_banned(user_id):
        await event.answer("🚫 Вы заблокированы за нарушение правил использования бота.")
        return
    
    # Rate limiting
    if not check_rate_limit(user_id):
        await event.answer("⏳ Слишком много запросов. Подождите немного.")
        return
    
    # Логирование команды
    command = event.text.split()[0] if event.text else "unknown"
    log_user_action(user_id, command)
    
    # Продолжение обработки
    return await handler(event, data)

@dp.callback_query.middleware() 
async def callback_middleware(handler, event, data):
    user_id = event.from_user.id
    
    # Регистрация пользователя при нажатии кнопок
    try:
        user = await User.get_or_create_user(
            user_id=user_id,
            username=event.from_user.username,
            first_name=event.from_user.first_name,
            last_name=event.from_user.last_name
        )
        if user:
            await user.update_activity()
    except Exception as e:
        logger.error(f"Ошибка регистрации пользователя {user_id}: {e}")
    
    return await handler(event, data)

# Главное меню
def get_main_menu(user_id: int = None):
    keyboard = [
        [
            InlineKeyboardButton(text="🚑 Медицина", callback_data="med"),
            InlineKeyboardButton(text="🚒 Пожарные", callback_data="fire")
        ],
        [
            InlineKeyboardButton(text="👮 Полиция", callback_data="police"),
            InlineKeyboardButton(text="🆘 Спасатели", callback_data="rescue")
        ],
        [
            InlineKeyboardButton(text="📞 Контакты", callback_data="contacts"),
            InlineKeyboardButton(text="🤖 ИИ Помощник", callback_data="ai_menu")
        ]
    ]
    
    # Добавляем кнопку админки для администраторов
    if user_id and is_admin(user_id):
        keyboard.append([InlineKeyboardButton(text="🔧 Админка", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Стартовая команда
@dp.message(Command("start"))
async def start_command(message: types.Message):
    welcome_text = """
🚨 **Помощник экстренных служб**

Профессиональный бот для сотрудников экстренных служб РФ.
Быстрый доступ к важной информации в критических ситуациях.

📖 **Подробности миссии:** [Посмотреть](https://telegra.ph/Cifrovoj-pomoshchnik-ehkstrennyh-sluzhb-06-12)

🚑 **Медицина**: расчет дозировок препаратов, противоядия при отравлениях, алгоритмы реанимации
🚒 **Пожарные**: классификация пожаров, выбор огнетушащих веществ, опасные материалы  
👮 **Полиция**: статьи УК РФ и КоАП, процедуры задержания, права граждан
🆘 **Спасатели**: методы поиска людей, время выживания, влияние погоды на операции

**Основные команды:**
├ `/poison [название]` - противоядие при отравлении
├ `/dose [лекарство] [вес]` - расчет дозировки препарата  
├ `/fire [класс]` - способы тушения пожара
└ `/law [статья]` - текст статьи закона

💡 **Совет:** Нажмите на команду чтобы скопировать её

Полный справочник команд
└`/help`

**Разработчик:** @kitay9
**Версия:** 2.0 | **Статус:** Активная разработка
    """
    
    await message.answer(
        welcome_text, 
        reply_markup=get_main_menu(message.from_user.id),
        parse_mode="Markdown"
    )

# Команда помощи
@dp.message(Command("help"))
async def help_command(message: types.Message):
    help_text = """
📚 **Список всех команд:**

**🚑 МЕДИЦИНА:**
• `/dose [лекарство] [вес]` - расчет дозировки
• `/poison [вещество]` - информация о противоядии
• `/drug [название]` - информация о лекарстве
• `/resus` - алгоритм реанимации

**🚒 ПОЖАРНЫЕ:**
• `/fire [класс]` - способы тушения (A, B, C, D, E)
• `/hazmat [вещество]` - опасные вещества
• `/evacuation` - алгоритм эвакуации

**👮 ПОЛИЦИЯ:**
• `/law [номер статьи]` - текст статьи УК РФ
• `/admin [номер]` - статьи КоАП
• `/protocol [тип]` - шаблон протокола
• `/rights` - права человека при задержании

**🆘 СПАСАТЕЛИ:**
• `/search [метод]` - методы поиска
• `/survival [условия]` - время выживания
• `/weather` - влияние погоды на операции

**🌍 ОБЩИЕ:**
• `/contacts [служба]` - экстренные контакты
• `/checklist [тип ЧС]` - алгоритм действий

💡 **Совет:** Нажмите на любую команду чтобы скопировать её
    """
    
    help_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Главное меню", callback_data="back")]
    ])
    
    await message.answer(help_text, reply_markup=help_keyboard, parse_mode="Markdown")

# Расчет дозировки лекарств
@dp.message(Command("dose"))
async def dose_command(message: types.Message):
    try:
        args = message.text.split()[1:]
        if len(args) < 2:
            error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💊 К лекарствам", callback_data="med_dose")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ])
            await message.answer("ℹ️ Используйте: `/dose [лекарство] [вес в кг]`\nПример: `/dose адреналин 70`\n\n💡 **Совет:** Нажмите на команду чтобы скопировать её", reply_markup=error_keyboard, parse_mode="Markdown")
            return
        
        drug = args[0].lower()
        weight = float(args[1])
        
        dose_info = emergency_data.calculate_dose(drug, weight)
        if dose_info.startswith("ℹ️"):
            # Если препарат не найден, выводим ошибку
            error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💊 К лекарствам", callback_data="med_dose")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ])
            await message.answer(dose_info, reply_markup=error_keyboard, parse_mode="Markdown")
        else:
            # Препарат найден, показываем дозировку
            dose_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💊 К лекарствам", callback_data="med_dose")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ])
            await message.answer(f"💊 **Дозировка для {drug.title()}:**\n\n{dose_info}", reply_markup=dose_keyboard, parse_mode="Markdown")
    except (ValueError, IndexError):
        error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💊 К лекарствам", callback_data="med_dose")],
            [InlineKeyboardButton(text="Главное меню", callback_data="back")]
        ])
        await message.answer("ℹ️ Неверный формат. Используйте: `/dose [лекарство] [вес в кг]`\n\n💡 **Совет:** Нажмите на команду чтобы скопировать её", reply_markup=error_keyboard, parse_mode="Markdown")

# Информация о ядах и противоядиях
@dp.message(Command("poison"))
async def poison_command(message: types.Message):
    try:
        args = message.text.split()[1:]
        if not args:
            error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="☠️ К противоядиям", callback_data="med_poison")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ])
            await message.answer("ℹ️ Используйте: `/poison [название вещества]`\nПример: `/poison мышьяк`\n\n💡 **Совет:** Нажмите на команду чтобы скопировать её", reply_markup=error_keyboard, parse_mode="Markdown")
            return
        
        poison = " ".join(args).lower()
        poison_info = emergency_data.get_poison_info(poison)
        
        if poison_info.startswith("ℹ️"):
            # Если яд не найден
            error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="☠️ К ядам", callback_data="med_poison")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ])
            await message.answer(poison_info, reply_markup=error_keyboard, parse_mode="Markdown")
        else:
            # Яд найден, показываем информацию
            poison_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="☠️ К ядам", callback_data="med_poison")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ])
            await message.answer(f"☠️ **{poison.title()}**\n\n{poison_info}", reply_markup=poison_keyboard, parse_mode="Markdown")
            
    except Exception as e:
        error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="☠️ К противоядиям", callback_data="med_poison")],
            [InlineKeyboardButton(text="Главное меню", callback_data="back")]
        ])
        await message.answer("ℹ️ Произошла ошибка при поиске информации", reply_markup=error_keyboard, parse_mode="Markdown")

# Информация о классах пожаров
@dp.message(Command("fire"))
async def fire_command(message: types.Message):
    try:
        args = message.text.split()[1:]
        if not args:
            error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔥 К классам пожаров", callback_data="fire_classes")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ])
            await message.answer("ℹ️ Используйте: `/fire [класс]`\nПример: `/fire A` или `/fire электро`\n\n💡 **Совет:** Нажмите на команду чтобы скопировать её", reply_markup=error_keyboard, parse_mode="Markdown")
            return
        
        fire_class = args[0].upper()
        fire_info = emergency_data.get_fire_class_info(fire_class)
        
        if fire_info.startswith("ℹ️"):
            # Если класс не найден
            error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔥 К пожарам", callback_data="fire_classes")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ])
            await message.answer(fire_info, reply_markup=error_keyboard, parse_mode="Markdown")
        else:
            # Класс найден
            fire_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔥 К пожарам", callback_data="fire_classes")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ])
            await message.answer(f"🔥 **Класс {fire_class.upper()}**\n\n{fire_info}", reply_markup=fire_keyboard, parse_mode="Markdown")
            
    except Exception as e:
        error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔥 К классам пожаров", callback_data="fire_classes")],
            [InlineKeyboardButton(text="Главное меню", callback_data="back")]
        ])
        await message.answer("ℹ️ Произошла ошибка при поиске информации", reply_markup=error_keyboard, parse_mode="Markdown")

# Статьи УК РФ
@dp.message(Command("law"))
async def law_command(message: types.Message):
    try:
        args = message.text.split()[1:]
        if not args:
            error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚖️ К УК РФ", callback_data="police_criminal")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ])
            await message.answer("ℹ️ Используйте: `/law [номер статьи]`\nПример: `/law 228`\n\n💡 **Совет:** Нажмите на команду чтобы скопировать её", reply_markup=error_keyboard, parse_mode="Markdown")
            return
        
        article = args[0]
        law_info = emergency_data.get_criminal_article(article)
        
        if law_info.startswith("ℹ️"):
            # Если статья не найдена
            error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚖️ К УК РФ", callback_data="police_criminal")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ])
            await message.answer(law_info, reply_markup=error_keyboard, parse_mode="Markdown")
        else:
            # Статья найдена
            law_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚖️ К УК РФ", callback_data="police_criminal")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ])
            await message.answer(law_info, reply_markup=law_keyboard, parse_mode="Markdown")
            
    except Exception as e:
        error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚖️ К УК РФ", callback_data="police_criminal")],
            [InlineKeyboardButton(text="Главное меню", callback_data="back")]
        ])
        await message.answer("ℹ️ Произошла ошибка при поиске статьи", reply_markup=error_keyboard, parse_mode="Markdown")

# Статьи КоАП РФ
@dp.message(Command("admin"))
async def admin_command(message: types.Message):
    try:
        args = message.text.split()[1:]
        if not args:
            error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К КоАП", callback_data="police_admin")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ])
            await message.answer("ℹ️ Используйте: `/admin [номер статьи]`\nПример: `/admin 20.1`\n\n💡 **Совет:** Нажмите на команду чтобы скопировать её", reply_markup=error_keyboard, parse_mode="Markdown")
            return
        
        article = args[0]
        admin_info = emergency_data.get_admin_article(article)
        
        if admin_info.startswith("ℹ️"):
            # Если статья не найдена
            error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К КоАП", callback_data="police_admin")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ])
            await message.answer(admin_info, reply_markup=error_keyboard, parse_mode="Markdown")
        else:
            # Статья найдена
            admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К КоАП", callback_data="police_admin")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ])
            await message.answer(admin_info, reply_markup=admin_keyboard, parse_mode="Markdown")
            
    except Exception as e:
        error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="К КоАП", callback_data="police_admin")],
            [InlineKeyboardButton(text="Главное меню", callback_data="back")]
        ])
        await message.answer("ℹ️ Произошла ошибка при поиске статьи", reply_markup=error_keyboard, parse_mode="Markdown")



# === ИИ КОМАНДЫ ===
@dp.message(Command("ai_symptoms"))
async def ai_symptoms_command(message: types.Message):
    ai_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🩺 К ИИ меню", callback_data="ai_menu")],
        [InlineKeyboardButton(text="Главное меню", callback_data="back")]
    ])
    
    await message.answer(
        "🚧 **Функция в разработке**\n\nИИ анализ симптомов будет доступен в следующем обновлении.\n\nПока используйте стандартные медицинские алгоритмы в разделе 'Медицина'.",
        reply_markup=ai_keyboard,
        parse_mode="Markdown"
    )

@dp.message(Command("ai_protocol"))
async def ai_protocol_command(message: types.Message):
    ai_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 К ИИ меню", callback_data="ai_menu")],
        [InlineKeyboardButton(text="Главное меню", callback_data="back")]
    ])
    
    await message.answer(
        "🚧 **Функция в разработке**\n\nИИ генерация протоколов будет доступна в следующем обновлении.\n\nПока используйте шаблоны в разделе 'Полиция'.",
        reply_markup=ai_keyboard,
        parse_mode="Markdown"
    )

@dp.message(Command("ai_legal"))
async def ai_legal_command(message: types.Message):
    ai_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚖️ К ИИ меню", callback_data="ai_menu")],
        [InlineKeyboardButton(text="Главное меню", callback_data="back")]
    ])
    
    await message.answer(
        "🚧 **Функция в разработке**\n\nИИ правовые консультации будут доступны в следующем обновлении.\n\nПока используйте базу статей в разделе 'Полиция'.",
        reply_markup=ai_keyboard,
        parse_mode="Markdown"
    )

@dp.message(Command("ai_checklist"))
async def ai_checklist_command(message: types.Message):
    ai_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="К ИИ меню", callback_data="ai_menu")],
        [InlineKeyboardButton(text="Главное меню", callback_data="back")]
    ])
    
    await message.answer(
        "🚧 **Функция в разработке**\n\nИИ чек-листы для ЧС будут доступны в следующем обновлении.\n\nПока используйте алгоритмы в соответствующих разделах.",
        reply_markup=ai_keyboard,
        parse_mode="Markdown"
    )

# Обработка кнопок меню
@dp.callback_query()
async def handle_callbacks(callback: types.CallbackQuery):
    # === ГЛАВНЫЕ РАЗДЕЛЫ ===
    if callback.data == "med":
        med_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💊 Дозировки", callback_data="med_dose"),
                InlineKeyboardButton(text="☠️ Противоядия", callback_data="med_poison")
            ],
            [
                InlineKeyboardButton(text="🫀 Реанимация", callback_data="med_resus"),
                InlineKeyboardButton(text="🩺 Алгоритмы", callback_data="med_algo")
            ],
            [InlineKeyboardButton(text="Назад", callback_data="back")]
        ])
        
        await callback.message.edit_text(
            "🚑 **Медицинский раздел**\n\nВыберите нужную категорию:",
            reply_markup=med_keyboard,
            parse_mode="Markdown"
        )
    
    elif callback.data == "fire":
        fire_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔥 Классы пожаров", callback_data="fire_classes"),
                InlineKeyboardButton(text="🧯 Огнетушители", callback_data="fire_extinguish")
            ],
            [
                InlineKeyboardButton(text="☣️ Опасные вещества", callback_data="fire_hazmat"),
                InlineKeyboardButton(text="🚪 Эвакуация", callback_data="fire_evac")
            ],
            [InlineKeyboardButton(text="Назад", callback_data="back")]
        ])
        
        await callback.message.edit_text(
            "🚒 **Пожарная служба**\n\nВыберите нужную категорию:",
            reply_markup=fire_keyboard,
            parse_mode="Markdown"
        )
    
    elif callback.data == "police":
        police_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⚖️ УК РФ", callback_data="police_criminal"),
                InlineKeyboardButton(text="КоАП", callback_data="police_admin")
            ],
            [
                InlineKeyboardButton(text="🛡️ Права граждан", callback_data="police_rights"),
                InlineKeyboardButton(text="📝 Протоколы", callback_data="police_protocols")
            ],
            [InlineKeyboardButton(text="Назад", callback_data="back")]
        ])
        
        await callback.message.edit_text(
            "👮 **Полиция**\n\nВыберите нужную категорию:",
            reply_markup=police_keyboard,
            parse_mode="Markdown"
        )
    
    elif callback.data == "rescue":
        rescue_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔍 Методы поиска", callback_data="rescue_search"),
                InlineKeyboardButton(text="🏔️ Выживание", callback_data="rescue_survival")
            ],
            [
                InlineKeyboardButton(text="🌦️ Погодные условия", callback_data="rescue_weather"),
                InlineKeyboardButton(text="📡 Связь", callback_data="rescue_comms")
            ],
            [InlineKeyboardButton(text="Назад", callback_data="back")]
        ])
        
        await callback.message.edit_text(
            "🆘 **Спасательная служба**\n\nВыберите нужную категорию:",
            reply_markup=rescue_keyboard,
            parse_mode="Markdown"
        )
    

    
    elif callback.data == "contacts":
        contact_info = emergency_data.get_emergency_contacts()
        await callback.message.edit_text(
            contact_info,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    # === МЕДИЦИНСКИЕ ПОДРАЗДЕЛЫ ===
    elif callback.data == "med_dose":
        dose_text = emergency_data.get_all_drugs()
        await callback.message.edit_text(
            dose_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К медицине", callback_data="med")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "med_poison":
        poison_text = emergency_data.get_all_poisons()
        await callback.message.edit_text(
            poison_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К медицине", callback_data="med")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "med_resus":
        resus_info = emergency_data.get_resuscitation_algorithm()
        await callback.message.edit_text(
            resus_info,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К медицине", callback_data="med")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "med_algo":
        algo_text = """
🩺 **Медицинские алгоритмы**

**Основные протоколы:**
• 🫀 СЛР - нажмите "Реанимация" выше
• 🤕 Травмы - оценка по шкале ABC
• 🔥 Ожоги - правило девяток
• 💔 Инфаркт - алгоритм МОНА
• 🧠 Инсульт - шкала FAST

**Шкала ABC (травмы):**
• **A** - Airway (дыхательные пути)
• **B** - Breathing (дыхание) 
• **C** - Circulation (кровообращение)

**Шкала FAST (инсульт):**
• **F** - Face (лицо) - перекос
• **A** - Arms (руки) - слабость
• **S** - Speech (речь) - нарушения
• **T** - Time (время) - вызов 103
        """
        await callback.message.edit_text(
            algo_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К медицине", callback_data="med")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    # === ПОЖАРНЫЕ ПОДРАЗДЕЛЫ ===
    elif callback.data == "fire_classes":
        fire_classes_info = emergency_data.get_all_fire_classes()
        await callback.message.edit_text(
            fire_classes_info,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К пожарным", callback_data="fire")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "fire_extinguish":
        extinguish_text = """
🧯 **Огнетушащие вещества**

**Типы огнетушителей:**
• **Водные** - класс A (твердые вещества)
• **Пенные** - класс A, B (жидкости) 
• **Порошковые** - универсальные ABC
• **Углекислотные** - класс B, C, E
• **Хладоновые** - электроника, музеи

**⚠️ ЗАПРЕЩЕНО:**
• Вода на класс B, D, E
• Пена на электроустановки
• Любые средства на активные металлы без спецпорошков

**Правило выбора:**
1. Определить класс пожара
2. Выбрать подходящее средство
3. Проверить безопасность применения
        """
        await callback.message.edit_text(
            extinguish_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К пожарным", callback_data="fire")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "fire_hazmat":
        hazmat_text = """
☣️ **Опасные вещества**

**Классы опасности:**
• **Класс 1** - Взрывчатые вещества
• **Класс 2** - Газы (воспламеняющиеся, токсичные)
• **Класс 3** - Легковоспламеняющиеся жидкости
• **Класс 4** - Твердые вещества, самовозгорающиеся
• **Класс 5** - Окисляющие вещества
• **Класс 6** - Токсичные вещества
• **Класс 7** - Радиоактивные материалы
• **Класс 8** - Едкие и коррозионные вещества
• **Класс 9** - Прочие опасные вещества

**🚨 При работе с HAZMAT:**
1. Определить класс опасности
2. Использовать СИЗ
3. Обеспечить вентиляцию
4. Подготовить нейтрализующие средства
        """
        await callback.message.edit_text(
            hazmat_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К пожарным", callback_data="fire")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "fire_evac":
        evac_text = """
🚪 **Алгоритм эвакуации**

**Порядок действий:**

**1. Оповещение (1-2 мин):**
• Включить сигнализацию
• Объявить по громкой связи
• Сообщить в службы: 101, 112

**2. Эвакуация людей (5-10 мин):**
• Открыть все эвакуационные выходы
• Отключить лифты (кроме пожарных)
• Проверить все помещения
• Помочь маломобильным

**3. Встреча служб:**
• Встретить пожарных у въезда
• Передать планы здания
• Сообщить о людях внутри
• Указать места отключения коммуникаций

**⚠️ Запрещено:**
• Использовать лифты
• Открывать горячие двери
• Возвращаться за вещами
• Прятаться в дальних помещениях
        """
        await callback.message.edit_text(
            evac_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К пожарным", callback_data="fire")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    # === ПОЛИЦЕЙСКИЕ ПОДРАЗДЕЛЫ ===
    elif callback.data == "police_criminal":
        criminal_text = emergency_data.get_all_criminal_articles()
        await callback.message.edit_text(
            criminal_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К полиции", callback_data="police")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "police_rights":
        rights_text = """
🛡️ **Права граждан при задержании**

**При задержании гражданин имеет право:**
• Знать основание и причину задержания
• Уведомить близких о задержании
• Пользоваться услугами переводчика
• Обращаться за медпомощью
• Требовать адвоката (с момента задержания)
• Не свидетельствовать против себя (ст. 51 Конституции)

**Сроки задержания:**
• **Административное** - до 3 часов (48 часов по отдельным статьям)
• **Уголовное** - до 48 часов (до 72 часов с санкции суда)

**⚠️ Важно:**
• Задержанный не обязан отвечать на вопросы до прибытия адвоката
• Протокол задержания составляется немедленно
• При нарушении прав - жалоба прокурору/в суд
        """
        await callback.message.edit_text(
            rights_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К полиции", callback_data="police")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "police_admin":
        admin_text = emergency_data.get_all_admin_articles()
        await callback.message.edit_text(
            admin_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К полиции", callback_data="police")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "police_protocols":
        protocols_text = """
📝 **Шаблоны протоколов**

**Протокол об административном правонарушении:**

**Обязательные сведения:**
• Дата, время, место составления
• ФИО, должность, звание составителя
• Сведения о лице, привлекаемом к ответственности
• Место, время совершения правонарушения
• Описание события правонарушения
• Статья КоАП РФ
• Объяснение лица (отказ от объяснения)
• Свидетели, потерпевшие (если есть)

**Образец записи события:**
"[Дата] в [время] по адресу [адрес] гр. [ФИО], [год рождения], [документы], совершил административное правонарушение, выразившееся в [описание действий], что предусмотрено статьей [номер] КоАП РФ."

**Протокол задержания:**
• Основания задержания
• Дата, время начала и окончания
• Место задержания
• Результаты личного досмотра
• Уведомление близких/работодателя

**⚠️ Важно:**
• Протокол составляется немедленно
• Копия вручается нарушителю
• При отказе от подписи - отметка в протоколе
        """
        await callback.message.edit_text(
            protocols_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К полиции", callback_data="police")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "ai_menu":
        ai_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🩺 Анализ симптомов", callback_data="ai_symptoms_menu"),
                InlineKeyboardButton(text="📝 Генерация протокола", callback_data="ai_protocol_menu")
            ],
            [
                InlineKeyboardButton(text="⚖️ Правовая консультация", callback_data="ai_legal_menu"),
                InlineKeyboardButton(text="Чек-лист ЧС", callback_data="ai_checklist_menu")
            ],
            [InlineKeyboardButton(text="Назад", callback_data="back")]
        ])
        
        await callback.message.edit_text(
            f"**ИИ Помощник** - в разработке\n\nИскусственный интеллект для экстренных служб находится в стадии разработки.\n\nФункции будут доступны в следующих версиях:\n• Анализ симптомов\n• Генерация протоколов\n• Правовые консультации\n• Чек-листы для ЧС",
            reply_markup=ai_keyboard,
            parse_mode="Markdown"
        )
    
    elif callback.data == "ai_symptoms_menu":
        await callback.message.edit_text(
            "🚧 **ИИ Анализ симптомов - в разработке**\n\nДанная функция будет доступна в следующем обновлении.\n\nВ разработке:\n• Анализ описания симптомов\n• Предварительная диагностика\n• Оценка степени срочности\n• Рекомендации по первой помощи\n\nПока используйте стандартные медицинские алгоритмы.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К ИИ меню", callback_data="ai_menu")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "ai_protocol_menu":
        await callback.message.edit_text(
            "🚧 **ИИ Генерация протокола - в разработке**\n\nДанная функция будет доступна в следующем обновлении.\n\nВ разработке:\n• Автоматическое создание протоколов\n• Соответствие требованиям законодательства\n• Шаблоны для разных типов происшествий\n• Проверка правильности оформления\n\nПока используйте стандартные шаблоны.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К ИИ меню", callback_data="ai_menu")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "ai_legal_menu":
        await callback.message.edit_text(
            "🚧 **ИИ Правовая консультация - в разработке**\n\nДанная функция будет доступна в следующем обновлении.\n\nВ разработке:\n• Консультации по законодательству\n• Ссылки на актуальные статьи\n• Разъяснение процедур\n• Помощь в сложных случаях\n\nПока используйте базу статей УК РФ и КоАП.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К ИИ меню", callback_data="ai_menu")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "ai_checklist_menu":
        await callback.message.edit_text(
            "🚧 **ИИ Чек-лист ЧС - в разработке**\n\nДанная функция будет доступна в следующем обновлении.\n\nВ разработке:\n• Персонализированные чек-листы\n• Адаптация под тип ЧС\n• Пошаговые инструкции\n• Контроль выполнения действий\n\nПока используйте алгоритмы в разделах служб.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К ИИ меню", callback_data="ai_menu")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "rescue_search":
        search_text = """
🔍 **Методы поиска пропавших людей**

**Основные методы:**

**1. Звуковой поиск:**
• Голосовые вызовы каждые 3-5 минут
• Свистки, рупоры, мегафоны
• Прослушка в тишине 1-2 минуты

**2. Визуальный поиск:**
• Осмотр местности "зигзагом"
• Использование биноклей, прожекторов
• Поиск следов, меток, предметов

**3. Технический поиск:**
• Радиосвязь, мобильная связь
• GPS-трекеры, радиомаяки
• Тепловизоры (ночью/в холод)
• Дроны с камерами

**4. Кинологический поиск:**
• Поисковые собаки по запаху
• Работа по следу
• Поиск в завалах

**⏰ Временные рамки:**
• **Первые 3 часа** - максимальная активность
• **До 24 часов** - критический период
• **72 часа** - предел выживания без воды
        """
        await callback.message.edit_text(
            search_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К спасателям", callback_data="rescue")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "rescue_survival":
        survival_text = """
🏔️ **Время выживания в экстремальных условиях**

**Правило "3-х":**
• **3 минуты** без воздуха (утопление, завал)
• **3 часа** без тепла (гипотермия)  
• **3 дня** без воды
• **3 недели** без еды

**Конкретные условия:**

**Температурные:**
• **-40°C** - 30 минут без защиты
• **-20°C** - 1-2 часа
• **0°C и ветер** - 3-6 часов  
• **+50°C без воды** - 6-12 часов

**В воде:**
• **0°C** - 15-30 минут
• **10°C** - 1-3 часа
• **20°C** - 12-20 часов

**Без воды:**
• **Жара +40°C** - 24-48 часов
• **Умеренный климат** - 3-5 дней
• **Холод** - 7-10 дней

**⚠️ Факторы, сокращающие время:**
• Паника, стресс
• Ранения, болезни
• Физическая активность
• Алкоголь, наркотики
        """
        await callback.message.edit_text(
            survival_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К спасателям", callback_data="rescue")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "rescue_weather":
        weather_text = """
🌦️ **Влияние погоды на спасательные операции**

**Дождь/снег:**
• Ухудшение видимости (до 10-50 м)
• Размытие следов
• Риск переохлаждения
• Проблемы с радиосвязью

**Ветер:**
• **До 10 м/с** - допустимо
• **10-15 м/с** - осложнения с авиацией
• **Свыше 15 м/с** - запрет полетов
• Снос звука, затруднение поиска

**Туман:**
• Видимость менее 50 м
• Дезориентация спасателей
• Запрет авиационного поиска
• Использование GPS обязательно

**Температура:**
• **Ниже -20°C** - ограничение времени работы
• **Выше +35°C** - риск теплового удара
• Необходимость смены команд каждые 2-4 часа

**⚠️ Критические условия (прекращение поиска):**
• Гроза с молниями
• Метель с видимостью <10 м
• Лавинная опасность 4-5 баллов
• Сели, наводнения
        """
        await callback.message.edit_text(
            weather_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К спасателям", callback_data="rescue")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "rescue_comms":
        comms_text = """
📡 **Связь в спасательных операциях**

**Частоты связи:**
• **МЧС России**: 149.200 - 149.800 МГц
• **Авиационная**: 121.5 МГц (аварийная)
• **Морская**: 156.800 МГц (16 канал)
• **Любительская**: 145.500 МГц (R5)

**Протокол радиосвязи:**
1. **"[Позывной] - [Позывной], прием!"**
2. Ждать ответа 3-5 секунд
3. Повторить 3 раза, затем пауза
4. Говорить четко, медленно
5. Заканчивать: **"Конец связи"**

**Сигналы бедствия:**
• **SOS** - ... --- ... (3 коротких, 3 длинных, 3 коротких)
• **MAYDAY** - голосом по радио (3 раза)
• **PAN-PAN** - срочность (не смертельная опасность)

**Мобильная связь:**
• **112** - работает без SIM-карты
• SMS при слабом сигнале
• Экономия батареи (режим полета с периодическим включением)
• Запасные аккумуляторы, power bank

**⚠️ При отсутствии связи:**
• Подъем на возвышенность
• Использование отражателей, зеркал
• Дымовые сигналы (3 столба дыма)
• Сигнальные ракеты
        """
        await callback.message.edit_text(
            comms_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="К спасателям", callback_data="rescue")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ]),
            parse_mode="Markdown"
        )
    
    elif callback.data == "admin_panel":
        # Проверка прав администратора
        if not is_admin(callback.from_user.id):
            await callback.answer("❌ У вас нет прав доступа к админ панели", show_alert=True)
            return
        
        try:
            stats = await User.get_user_stats()
            storage_type = stats.get('storage_type', 'unknown')
            
            # Определяем тип хранилища для отображения
            if storage_type == 'mongodb':
                storage_info = "💾 **MongoDB подключена**"
                additional_info = "⚙️ **Система работает стабильно**"
            elif storage_type == 'json_backup':
                storage_info = "📂 **JSON резерв (MongoDB недоступна)**"
                additional_info = "💡 **Проверьте подключение к MongoDB**"
            elif storage_type == 'text_file':
                storage_info = "📄 **Текстовое хранилище (users.txt)**"
                additional_info = """💡 **Для переключения на MongoDB:**
• Установите: `USE_MONGODB=true` в .env
• Настройте: `MONGODB_URL=mongodb://localhost:27017`"""
            else:
                storage_info = "❌ **Ошибка хранилища**"
                additional_info = "Попробуйте перезапустить бота"
            
            if stats.get('error'):
                admin_text = f"""
🔧 **Админ панель 112help**

❌ **Ошибка получения статистики**

Попробуйте позже или проверьте подключение к базе данных.
                """
            else:
                admin_text = f"""
🔧 **Админ панель 112help**

{storage_info}

📊 **Статистика пользователей:**
• **Всего пользователей:** {stats['total']}
• **Активных сегодня:** {stats['active_today']}
• **Активных за неделю:** {stats['active_week']}
• **Новых сегодня:** {stats['new_today']}
• **Заблокированных:** {stats['blocked']}

📈 **Активность:**
• **Сегодня:** {stats['active_today']} из {stats['total']} ({(stats['active_today']/stats['total']*100) if stats['total'] > 0 else 0:.1f}%)
• **За неделю:** {stats['active_week']} из {stats['total']} ({(stats['active_week']/stats['total']*100) if stats['total'] > 0 else 0:.1f}%)

{additional_info}
                """
            
            admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_panel")],
                [InlineKeyboardButton(text="Главное меню", callback_data="back")]
            ])
            
            await callback.message.edit_text(
                admin_text,
                reply_markup=admin_keyboard,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            await callback.message.edit_text(
                "❌ **Ошибка получения статистики**\n\nПопробуйте позже или обратитесь к разработчику.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Главное меню", callback_data="back")]
                ]),
                parse_mode="Markdown"
            )
    
    elif callback.data == "back":
        welcome_text = """
🚨 **112help - Помощник экстренных служб** 🚨

Профессиональный бот для сотрудников экстренных служб РФ.
Быстрый доступ к важной информации в критических ситуациях.

📖 **Подробности миссии:** [Посмотреть](https://telegra.ph/Cifrovoj-pomoshchnik-ehkstrennyh-sluzhb-06-12)

🚑 **Медицина**: расчет дозировок препаратов, противоядия при отравлениях, алгоритмы реанимации
🚒 **Пожарные**: классификация пожаров, выбор огнетушащих веществ, опасные материалы  
👮 **Полиция**: статьи УК РФ и КоАП, процедуры задержания, права граждан
🆘 **Спасатели**: методы поиска людей, время выживания, влияние погоды на операции

**Основные команды:**
├ `/poison [название]` - противоядие при отравлении
├ `/dose [лекарство] [вес]` - расчет дозировки препарата  
├ `/fire [класс]` - способы тушения пожара
└ `/law [статья]` - текст статьи закона

💡 **Совет:** Нажмите на команду чтобы скопировать её

Полный справочник команд
└`/help`

**Разработчик:** @kitay9
**Версия:** 2.0 | **Статус:** Активная разработка
        """
        
        await callback.message.edit_text(
            welcome_text,
            reply_markup=get_main_menu(callback.from_user.id),
            parse_mode="Markdown"
        )
    
    await callback.answer()

# Установка команд бота
async def set_bot_commands():
    commands = [
        BotCommand(command="start", description="🚨 Запуск бота"),
        BotCommand(command="help", description="📚 Помощь и список команд"),
        BotCommand(command="dose", description="💊 Расчет дозировки лекарств"),
        BotCommand(command="poison", description="☠️ Информация о ядах"),
        BotCommand(command="fire", description="🔥 Классы пожаров"),
        BotCommand(command="law", description="⚖️ Статьи УК РФ"),

        BotCommand(command="ai_symptoms", description="🤖 ИИ анализ симптомов"),
        BotCommand(command="ai_protocol", description="📝 ИИ генерация протокола"),
        BotCommand(command="ai_legal", description="⚖️ ИИ правовая консультация"),
        BotCommand(command="ai_checklist", description="ИИ чек-лист ЧС"),
        BotCommand(command="admin", description="Статьи КоАП РФ"),
    ]
    
    await bot.set_my_commands(commands)

# Основная функция
async def main():
    logger.info("Запуск 112help...")
    
    # Инициализация базы данных
    await Database.connect()
    
    # Установка команд
    await set_bot_commands()
    
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 