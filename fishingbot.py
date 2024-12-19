import logging
import random
import re
from math import pi
from collections import defaultdict
from datetime import datetime, timedelta

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Определение констант для кнопок
BUTTON_START_FISHING = "🎣 Начать рыбалку"
BUTTON_LAKE = "🏞 Озеро"
BUTTON_INVENTORY = "📦 Инвентарь"
BUTTON_SHOP = "🏪 Магазин"
BUTTON_CATCH_FISH = "🎣 Ловить рыбку"
BUTTON_UPDATE = "🔄 Обновить"
BUTTON_GO_BACK = "🔙 Вернуться"
BUTTON_IDENTIFY_FISH = "🔍 Опознать рыбу"
BUTTON_SELL_ALL = "💰 Продать все за золото"
BUTTON_EXCHANGE_GOLD = "🔄 Обменять золото"
BUTTON_PULL = "🐟 Тянуть"
BUTTON_CONFIRM_YES = "✅ Да"
BUTTON_CONFIRM_NO = "❌ Нет"
BUTTON_CONFIRM_NOT_ENOUGH = "❌ Нехватает золота! Нужно 25000+"
BUTTON_LEADERBOARD = "🏆 Таблица Лидеров"
BUTTON_TOTAL_GOLD = "💰 Всего заработано золота"
BUTTON_TOTAL_KG = "🐟 Всего поймано КГ рыбы"
BUTTON_TOTAL_EXPERIENCE = "⭐ Самые опытные"
BUTTON_RODS = "🎣 Удочки"
BUTTON_BAITS = "🪱 Наживки"
BUTTON_ABOUT_FISHERMAN = "👤 О рыбаке"

# Состояния для ConversationHandler
ASK_NICKNAME = 1
BUY_ROD = 2
CONFIRM_BUY_ROD = 3
CONFIRM_REPLACE_ROD = 4
BUY_BAIT = 5
CONFIRM_BUY_BAIT = 6
CONFIRM_REPLACE_BAIT = 7

# Хранилище данных пользователей (используется defaultdict для простоты)
users_data = defaultdict(lambda: {
    "nickname": None,
    "inventory": defaultdict(int),
    "gold": 0,  # Начальное золото
    "unidentified": {"common": 0, "rare": 0, "legendary": 0},
    "fishing": None,  # Для отслеживания состояния ловли
    "shop_gold": 0,    # Для хранения расчёта продажи
    "total_gold_earned": 0,  # Накопленное золото
    "total_kg_caught": 0,     # Накопленный вес рыбы
    "current_rod": {
        "name": "Бамбуковая удочка 🎣",
        "bonus_percent": 0
    },
    "current_bait": None,  # {"name": str, "end_time": datetime, "probabilities": dict}
    "experience": 0,
    "level": 1,
    "rank": "Юный рыбак",
    "registration_time": datetime.utcnow(),
    "fish_caught_per_rod": defaultdict(int),
    "fish_caught_per_bait": defaultdict(int)
})

# Таблица уровней до 75 уровня
LEVELS = [
    {"level": 1, "required_xp": 10, "rank": "Юный рыбак"},
    {"level": 2, "required_xp": 38, "rank": "Юный рыбак"},
    {"level": 3, "required_xp": 89, "rank": "Юный рыбак"},
    {"level": 4, "required_xp": 169, "rank": "Начинающий ловец"},
    {"level": 5, "required_xp": 477, "rank": "Начинающий ловец"},
    {"level": 6, "required_xp": 1008, "rank": "Начинающий ловец"},
    {"level": 7, "required_xp": 1809, "rank": "Ловец мелкой рыбёшки"},
    {"level": 8, "required_xp": 2940, "rank": "Ловец мелкой рыбёшки"},
    {"level": 9, "required_xp": 4470, "rank": "Ловец мелкой рыбёшки"},
    {"level": 10, "required_xp": 6471, "rank": "Опытный удильщик"},
    # Добавление уровней 11-75 с постепенным увеличением опыта и соответствующими рангами
]
# Автоматическое заполнение уровней до 75
for lvl in range(11, 76):
    required_xp = int(LEVELS[-1]["required_xp"] * 1.5)
    rank = f"Ранг {lvl}"
    LEVELS.append({"level": lvl, "required_xp": required_xp, "rank": rank})

# Рыбы
COMMON_FISH = [
    ("Мелкий карась", 2),
    ("Хилый окунь", 3),
    ("Мелкий щука", 4),
    ("Хилый лещ", 2),
    ("Мелкий плотва", 1),
    ("Хилый судак", 3),
    ("Мелкий линь", 1),
    ("Хилый угорь", 4),
    ("Мелкий сом", 5),
    ("Хилый трещотка", 2),
    ("Мелкий налим", 4),
    ("Хилый уклейка", 2),
    ("Мелкий ерш", 1),
    ("Хилый ротан", 3),
    ("Мелкий минтай", 3),
    ("Мелкий пескарь", 2),
    ("Хилый голавлик", 3),
    ("Молодой карась", 2),
    ("Юркий ерш", 1),
    ("Серенький окунь", 3),
    ("Молодой налим", 4),
    ("Юркий подлещик", 2),
    ("Серенькая плотвичка", 1),
    ("Молодой верховод", 1),
    ("Юркий ротан", 3),
]

RARE_FISH = [
    ("Красивый осётр", 14),
    ("Переливающаяся камбала", 11),
    ("Средний лосось", 13),
    ("Красивый белоголовик", 8),
    ("Переливающаяся форель", 12),
    ("Средний голавль", 9),
    ("Красивый треска", 10),
    ("Переливающийся сазан", 15),
    ("Средний сом", 14),
    ("Красивый щипун", 7),
    ("Красивый амур", 10),
    ("Переливающаяся белорыбица", 12),
    ("Средний сомик", 9),
    ("Необычный толстолобик", 13),
    ("Редкая стерлядь", 15),
    ("Хороший судак", 11),
    ("Красивый голавль", 9),
    ("Переливающаяся кефаль", 12),
    ("Средний сиг", 8),
    ("Необычная треска", 10),
]

LEGENDARY_FISH = [
    ("Колоссальный осётр", 70),
    ("Переливающийся лосось", 60),
    ("Светящийся сом", 55),
    ("Колоссальная щука", 65),
    ("Переливающийся тунец", 50),
    ("Светящийся судак", 45),
    ("Колоссальный угорь", 75),
    ("Переливающийся морской карась", 40),
    ("Светящийся треска", 35),
    ("Колоссальная форель", 55),
    ("Трофейный осётр", 70),
    ("Великолепная форель", 60),
    ("Непревзойдённый угорь", 75),
    ("Трофейный сазан", 65),
    ("Великолепная кета", 50),
    ("Непревзойдённый сом", 55),
    ("Трофейная щука", 45),
    ("Великолепный лосось", 72),
    ("Непревзойдённый судак", 40),
    ("Переливающийся амур", 50),
]

IDENTIFIED_FISH = {
    # Common
    "Мелкий карась": 2,
    "Хилый окунь": 3,
    "Мелкий щука": 4,
    "Хилый лещ": 2,
    "Мелкий плотва": 1,
    "Хилый судак": 3,
    "Мелкий линь": 1,
    "Хилый угорь": 4,
    "Мелкий сом": 5,
    "Хилый трещотка": 2,
    "Мелкий налим": 4,
    "Хилый уклейка": 2,
    "Мелкий ерш": 1,
    "Хилый ротан": 3,
    "Мелкий минтай": 3,
    "Мелкий пескарь": 2,
    "Хилый голавлик": 3,
    "Молодой карась": 2,
    "Юркий ерш": 1,
    "Серенький окунь": 3,
    "Молодой налим": 4,
    "Юркий подлещик": 2,
    "Серенькая плотвичка": 1,
    "Молодой верховод": 1,
    "Юркий ротан": 3,
    # Rare
    "Красивый осётр": 14,
    "Переливающаяся камбала": 11,
    "Средний лосось": 13,
    "Красивый белоголовик": 8,
    "Переливающаяся форель": 12,
    "Средний голавль": 9,
    "Красивый треска": 10,
    "Переливающийся сазан": 15,
    "Средний сом": 14,
    "Красивый щипун": 7,
    "Красивый амур": 10,
    "Переливающаяся белорыбица": 12,
    "Средний сомик": 9,
    "Необычный толстолобик": 13,
    "Редкая стерлядь": 15,
    "Хороший судак": 11,
    "Красивый голавль": 9,
    "Переливающаяся кефаль": 12,
    "Средний сиг": 8,
    "Необычная треска": 10,
    # Legendary
    "Колоссальный осётр": 70,
    "Переливающийся лосось": 60,
    "Светящийся сом": 55,
    "Колоссальная щука": 65,
    "Переливающийся тунец": 50,
    "Светящийся судак": 45,
    "Колоссальный угорь": 75,
    "Переливающийся морской карась": 40,
    "Светящийся треска": 35,
    "Колоссальная форель": 55,
    "Трофейный осётр": 70,
    "Великолепная форель": 60,
    "Непревзойдённый угорь": 75,
    "Трофейный сазан": 65,
    "Великолепная кета": 50,
    "Непревзойдённый сом": 55,
    "Трофейная щука": 45,
    "Великолепный лосось": 72,
    "Непревзойдённый судак": 40,
    "Переливающийся амур": 50,
}

# Удочки
RODS = [
    {"name": "Удочка Новичка 🎣", "price": 10, "bonus_percent": 5},
    {"name": "Удочка Любителя 🎣", "price": 50, "bonus_percent": 10},
    {"name": "Удочка Классическая 🎣", "price": 200, "bonus_percent": 15},
    {"name": "Удочка ПРО 🎣", "price": 500, "bonus_percent": 25},
    {"name": "Золотая Удочка 🎣", "price": 5000, "bonus_percent": 50},
]

# Наживки
BAITS = [
    {
        "name": "Червяк 🪱",
        "price": 5,
        "duration": timedelta(hours=1),
        "probabilities": {"common": 60, "rare": 35, "legendary": 5}
    },
    {
        "name": "Пиявка 🪱",
        "price": 20,
        "duration": timedelta(hours=1),
        "probabilities": {"common": 55, "rare": 60, "legendary": 5}
    },
    {
        "name": "Мясо краба 🪱",
        "price": 100,
        "duration": timedelta(hours=1),
        "probabilities": {"common": 55, "rare": 54, "legendary": 6}
    },
    {
        "name": "Осьминог 🪱",
        "price": 250,
        "duration": timedelta(hours=1),
        "probabilities": {"common": 50, "rare": 50, "legendary": 10}
    },
]

# Функция для генерации приветственного сообщения
def get_welcome_text():
    return (
        "🌅 Добро пожаловать на настоящую (почти) рыбалку!\n\n"
        "Здесь вы сможете поймать кучу рыбы и насладиться процессом рыбалки в объятиях природы. "
        "После успешного улова вы сможете продать рыбу за настоящую криптовалюту. "
        "Погрузитесь в мир рыбалки и испытайте свою удачу! 🎣🐟"
    )

# Функция для онбординга
def get_onboarding_text():
    return (
        "🎣 Добро пожаловать в увлекательный мир рыбалки!\n\n"
        "У вас есть прекрасное озеро, где можно ловить разнообразную рыбу. В вашем распоряжении инвентарь для хранения улова и магазин, "
        "где вы можете продавать рыбу за настоящую криптовалюту.\n\n"
        "Прежде чем начать, нам нужно придумать вам имя. Как нам тебя называть, рыбак? Придумай себе имя до 25 символов. 🐠"
    )

# Главное меню
def main_menu_keyboard():
    keyboard = [
        [KeyboardButton(BUTTON_LAKE)],
        [KeyboardButton(BUTTON_INVENTORY), KeyboardButton(BUTTON_ABOUT_FISHERMAN)],
        [KeyboardButton(BUTTON_SHOP), KeyboardButton(BUTTON_LEADERBOARD)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Озеро меню
def lake_menu_keyboard():
    keyboard = [
        [KeyboardButton(BUTTON_CATCH_FISH)],
        [KeyboardButton(BUTTON_UPDATE)],
        [KeyboardButton(BUTTON_GO_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Инвентарь меню
def inventory_menu_keyboard():
    keyboard = [
        [KeyboardButton(BUTTON_IDENTIFY_FISH)],
        [KeyboardButton(BUTTON_GO_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Магазин меню
def shop_menu_keyboard():
    keyboard = [
        [KeyboardButton(BUTTON_RODS), KeyboardButton(BUTTON_BAITS)],
        [KeyboardButton(BUTTON_SELL_ALL), KeyboardButton(BUTTON_EXCHANGE_GOLD)],
        [KeyboardButton(BUTTON_GO_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Таблица лидеров меню
def leaderboard_menu_keyboard():
    keyboard = [
        [KeyboardButton(BUTTON_TOTAL_GOLD), KeyboardButton(BUTTON_TOTAL_KG)],
        [KeyboardButton(BUTTON_TOTAL_EXPERIENCE)],
        [KeyboardButton(BUTTON_GO_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Меню "О рыбаке"
def about_fisherman_keyboard():
    keyboard = [
        [KeyboardButton(BUTTON_GO_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Функция для генерации текста озера
def get_lake_text(user_nickname):
    return (
        f"🌊 {user_nickname} пришёл на озеро. Вода спокойная, утки плавают, и вы решаете закинуть удочку.\n"
        "Что будем делать дальше?"
    )

# Функция для генерации инвентаря
def get_inventory_text(user_data):
    inventory = user_data["inventory"]
    unidentified = user_data["unidentified"]
    gold = user_data["gold"]
    current_rod = user_data["current_rod"]
    current_bait = user_data["current_bait"]
    text = "🎒 Ваш инвентарь:\n\n"

    # Удочка
    text += f"🎣 Удочка: {current_rod['name']} 🎣 (уменьшение времени рыбалки на {current_rod['bonus_percent']}%)\n"

    # Наживка
    if current_bait:
        remaining = int((current_bait["end_time"] - datetime.utcnow()).total_seconds() / 60)
        if remaining > 0:
            text += f"🪱 Наживка: {current_bait['name']} 🪱 (осталось ещё {remaining} минут)\n"
        else:
            text += "🪱 Наживка: нет 🪱\n"
    else:
        text += "🪱 Наживка: нет 🪱\n"

    text += "\n"  # Пустая строка

    # Неопознанная рыба
    if any(count > 0 for count in unidentified.values()):
        if unidentified["common"] > 0:
            text += f"• Неопознанные рыбы - {unidentified['common']}\n"
        if unidentified["rare"] > 0:
            text += f"• Неопознанные редкие рыбы - {unidentified['rare']}\n"
        if unidentified["legendary"] > 0:
            text += f"• Неопознанные легендарные рыбы - {unidentified['legendary']}\n"
    else:
        text += "У вас нет неопознанной рыбы.\n"

    # Опознанная рыба
    identified = {fish: qty for fish, qty in inventory.items() if fish in IDENTIFIED_FISH and qty > 0}
    if identified:
        for fish, qty in identified.items():
            total_kg = IDENTIFIED_FISH[fish] * qty
            text += f"• {fish} - {qty} шт. - {total_kg} КГ\n"

    text += f"\n💰 Золото: {gold}"
    return text

# Функция для генерации текста магазина
def get_shop_text(user_data):
    inventory = user_data["inventory"]
    identified_fish = {fish: qty for fish, qty in inventory.items() if fish in IDENTIFIED_FISH}

    if not identified_fish:
        return "🏪 Добро пожаловать в магазин рыбака!\n\nУ вас нет опознаной рыбы для продажи. Идите ловите! 🎣", 0

    text = "🏪 Добро пожаловать в магазин рыбака!\n\nВаш инвентарь:\n"
    total_weight = 0
    for fish, qty in identified_fish.items():
        weight = IDENTIFIED_FISH[fish]
        text += f"{fish} - {qty} шт. (Вес: {weight} КГ)\n"
        total_weight += weight * qty

    gold = int(total_weight * pi / 4)
    text += f"\n💰 Вы можете продать всю рыбу за {gold} золота."
    return text, gold

# Функция для генерации информации о рыбаке
def get_about_fisherman_text(user_data):
    nickname = user_data["nickname"]
    level = user_data["level"]
    rank = user_data["rank"]
    experience = user_data["experience"]
    required_xp = get_required_xp(level)
    age_delta = datetime.utcnow() - user_data["registration_time"]
    hours, remainder = divmod(int(age_delta.total_seconds()), 3600)
    minutes, _ = divmod(remainder, 60)
    age = f"{hours} часов и {minutes} минут"

    # Определение любимой удочки
    if user_data["fish_caught_per_rod"]:
        favorite_rod = max(user_data["fish_caught_per_rod"], key=user_data["fish_caught_per_rod"].get)
    else:
        favorite_rod = "Нет данных"

    # Определение любимой наживки
    if user_data["fish_caught_per_bait"]:
        favorite_bait = max(user_data["fish_caught_per_bait"], key=user_data["fish_caught_per_bait"].get)
    else:
        favorite_bait = "Нет данных"

    text = (
        f"👤 **О рыбаке** 👤\n\n"
        f"**Имя:** {nickname}\n"
        f"**Уровень:** {level}\n"
        f"**Ранг:** {rank}\n"
        f"**Опыт:** {experience} / {required_xp}\n"
        f"**Возраст игры:** {age}\n"
        f"**Любимая удочка:** {favorite_rod}\n"
        f"**Любимая наживка:** {favorite_bait}"
    )
    return text

# Функция для генерации сообщений при ловле рыбы
def generate_fish_catch_message(fish_type, xp_gained, level_up=False, new_level=None, gold_reward=0):
    message = (
        f"🎉 Поздравляем! Вы поймали {fish_type} 🐠\n"
        f"Получено {xp_gained} единиц опыта ⭐"
    )
    if level_up:
        message += f"\n\nВаш уровень повышен до {new_level}! Поздравляем!"
        if gold_reward > 0:
            message += f"\nВы получили {gold_reward} золота. 💰"
    return message

# Функция для обновления уровня и ранга
def check_level_up(user_data):
    level_up = False
    gold_reward = 0
    new_level = None
    while user_data["level"] <= len(LEVELS) and user_data["experience"] >= get_required_xp(user_data["level"]):
        user_data["level"] +=1
        update_rank(user_data)
        gold_reward += user_data["level"] * 2  # Награда за уровень
        user_data["gold"] += user_data["level"] * 2
        level_up = True
        new_level = user_data["level"]
    return level_up, new_level, gold_reward

# Функция для получения требуемого опыта для уровня
def get_required_xp(level):
    for lvl in LEVELS:
        if lvl["level"] == level:
            return lvl["required_xp"]
    # Для уровней выше, используем формулу
    # Примерная формула: требуемый опыт увеличивается на 1.5 раза с каждым уровнем
    if level > LEVELS[-1]["level"]:
        last_required = LEVELS[-1]["required_xp"]
        additional_levels = level - LEVELS[-1]["level"]
        return int(last_required * (1.5 ** additional_levels))
    return 10  # Базовый опыт для уровней ниже 1

# Функция для обновления ранга
def update_rank(user_data):
    level = user_data["level"]
    rank = "Юный рыбак"
    if 1 <= level <= 3:
        rank = "Юный рыбак"
    elif 4 <= level <= 6:
        rank = "Начинающий ловец"
    elif 7 <= level <= 9:
        rank = "Ловец мелкой рыбёшки"
    elif 10 <= level <= 12:
        rank = "Опытный удильщик"
    elif 13 <= level <= 15:
        rank = "Любитель клёва"
    elif 16 <= level <= 18:
        rank = "Знаток крючков"
    elif 19 <= level <= 21:
        rank = "Мастер наживки"
    elif 22 <= level <= 24:
        rank = "Искусный рыбак"
    elif 25 <= level <= 27:
        rank = "Охотник за уловом"
    elif 28 <= level <= 30:
        rank = "Настоящий рыболов"
    elif 31 <= level <= 40:
        rank = "Виртуоз рыбалки"
    elif 41 <= level <= 50:
        rank = "Укротитель рек"
    elif 51 <= level <= 60:
        rank = "Морской добытчик"
    elif 61 <= level <= 70:
        rank = "Легенда пруда"
    elif 71 <= level <= 75:
        rank = "Властелин озёр"
    # Добавьте дополнительные ранги по необходимости
    user_data["rank"] = rank

# Хендлер для команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = users_data[user.id]
    # Инициализация данных, если пользователь новый
    if user_data["registration_time"] == datetime.utcnow():
        user_data["gold"] = 0
        user_data["total_gold_earned"] = 0
        user_data["total_kg_caught"] = 0
        user_data["experience"] = 0
        user_data["level"] = 1
        user_data["rank"] = "Юный рыбак"
        user_data["registration_time"] = datetime.utcnow()
        user_data["fish_caught_per_rod"] = defaultdict(int)
        user_data["fish_caught_per_bait"] = defaultdict(int)
    logger.info(f"User {user.id} ({user.first_name}) started the bot.")
    await update.message.reply_text(
        get_welcome_text(),
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton(BUTTON_START_FISHING)]], resize_keyboard=True
        )
    )

# Хендлер для обработки начальной кнопки "Начать рыбалку"
async def begin_fishing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = users_data[user.id]
    if not user_data["nickname"]:
        # Начало процесса запроса ника
        await update.message.reply_text(
            get_onboarding_text(),
            reply_markup=ReplyKeyboardRemove()
        )
        logger.info(f"User {user.id} ({user.first_name}) is prompted to set a nickname.")
        return ASK_NICKNAME
    else:
        logger.info(f"User {user.id} ({user_data['nickname']}) started fishing.")
        await update.message.reply_text(
            "🌞 Кажется, сегодня отличная погода для рыбалки! Рыба вас ждет! 🎣🐟",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

# Хендлер для получения ника
async def set_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    nickname = update.message.text.strip()

    # Проверка длины
    if len(nickname) > 25:
        await update.message.reply_text(
            "❌ Имя слишком длинное. Пожалуйста, используйте до 25 символов.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ASK_NICKNAME

    # Проверка на допустимые символы (только буквы и пробелы)
    if not re.match(r'^[A-Za-zА-Яа-яЁё\s]+$', nickname):
        await update.message.reply_text(
            "❌ Имя содержит недопустимые символы. Пожалуйста, используйте только буквы и пробелы.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ASK_NICKNAME

    # Проверка на уникальность ника
    existing_nicknames = [data["nickname"] for uid, data in users_data.items() if data["nickname"]]
    if nickname in existing_nicknames:
        await update.message.reply_text(
            "❌ Это имя уже занято. Пожалуйста, выберите другое.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ASK_NICKNAME

    # Установка ника
    users_data[user.id]["nickname"] = nickname
    await update.message.reply_text(
        f"✅ Отлично, теперь мы будем называть тебя {nickname}!\n\n"
        "🌞 Кажется, сегодня отличная погода для рыбалки! Рыба вас ждет! 🎣🐟",
        reply_markup=main_menu_keyboard()
    )
    logger.info(f"User {user.id} set nickname to '{nickname}'.")
    return ConversationHandler.END

# Отмена установки ника
async def cancel_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        "❌ Вы отменили установку ника.",
        reply_markup=ReplyKeyboardRemove()
    )
    logger.info(f"User {user.id} ({user.first_name}) cancelled nickname setting.")
    return ConversationHandler.END

# Хендлер для Озера
async def lake(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = users_data[user.id]
    nickname = user_data["nickname"] if user_data["nickname"] else user.first_name
    welcome_lake_text = get_lake_text(nickname)
    logger.info(f"User {user.id} ({nickname}) arrived at the lake.")
    await update.message.reply_text(
        welcome_lake_text,
        reply_markup=lake_menu_keyboard()
    )

# Хендлер для ловли рыбы
async def catch_fish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = users_data[user.id]
    nickname = user_data["nickname"] if user_data["nickname"] else user.first_name
    logger.info(f"User {user.id} ({nickname}) started catching fish.")

    if user_data["fishing"]:
        await update.message.reply_text(
            "❗ Вы уже ловите рыбу! Используйте кнопку 🔄 Обновить, чтобы проверить статус."
        )
        logger.warning(f"User {user.id} ({nickname}) is already fishing.")
        return

    # Применение бонуса удочки
    rod_bonus = user_data["current_rod"]["bonus_percent"]
    base_delay = random.randint(5, 33)  # Максимум 33 секунды
    adjusted_delay = int(base_delay * (1 - rod_bonus / 100))
    if adjusted_delay < 1:
        adjusted_delay = 1  # Минимальная задержка 1 секунда

    end_time = datetime.utcnow() + timedelta(seconds=adjusted_delay)
    user_data["fishing"] = {
        "end_time": end_time,
        "status": "fishing"
    }

    await update.message.reply_text(
        f"🎣 Рыбка ловится... Подожди ещё {adjusted_delay} секунд ⏳",
        reply_markup=lake_menu_keyboard()
    )
    logger.info(f"User {user.id} fishing will end at {end_time} UTC.")

# Хендлер для обновления статуса ловли
async def update_fishing_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = users_data[user.id]
    nickname = user_data["nickname"] if user_data["nickname"] else user.first_name
    logger.info(f"User {user.id} ({nickname}) requested fishing status update.")

    # Проверка истечения времени действия наживки
    current_bait = user_data["current_bait"]
    if current_bait:
        if datetime.utcnow() >= current_bait["end_time"]:
            user_data["current_bait"] = None
            await update.message.reply_text(
                "🪱 Ваша наживка истекла.",
                reply_markup=lake_menu_keyboard()
            )
            logger.info(f"User {user.id} ({nickname})'s bait has expired.")

    if not user_data["fishing"]:
        await update.message.reply_text(
            "❗ Вы сейчас не ловите рыбу.",
            reply_markup=lake_menu_keyboard()
        )
        logger.warning(f"User {user.id} ({nickname}) is not fishing.")
        return

    end_time = user_data["fishing"]["end_time"]
    now = datetime.utcnow()
    remaining = (end_time - now).total_seconds()

    if remaining > 0:
        remaining = int(remaining)
        await update.message.reply_text(
            f"🎣 Рыбка всё ещё ловится... Осталось ещё {remaining} секунд ⏳"
        )
        logger.info(f"User {user.id} fishing has {remaining} seconds left.")
    else:
        user_data["fishing"]["status"] = "ready_to_pull"
        await update.message.reply_text(
            "🎣 Кажется, кто-то попался! Лови скорее! 🐟",
            reply_markup=ReplyKeyboardMarkup(
                [
                    [KeyboardButton(BUTTON_PULL)],
                    [KeyboardButton(BUTTON_GO_BACK)]
                ], resize_keyboard=True
            )
        )
        logger.info(f"User {user.id} fishing is ready to pull.")

# Хендлер для тягивания удочки
async def pull_hook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = users_data[user.id]
    nickname = user_data["nickname"] if user_data["nickname"] else user.first_name
    logger.info(f"User {user.id} ({nickname}) attempted to pull the hook.")

    if not user_data["fishing"]:
        await update.message.reply_text(
            "❗ Сначала начните ловить рыбу.",
            reply_markup=lake_menu_keyboard()
        )
        logger.warning(f"User {user.id} ({nickname}) tried to pull hook without fishing.")
        return

    end_time = user_data["fishing"]["end_time"]
    now = datetime.utcnow()

    # Проверка истечения времени действия наживки
    current_bait = user_data["current_bait"]
    if current_bait and now >= current_bait["end_time"]:
        user_data["current_bait"] = None
        await update.message.reply_text(
            "🪱 Ваша наживка истекла.",
            reply_markup=lake_menu_keyboard()
        )
        logger.info(f"User {user.id} ({nickname})'s bait has expired.")

    if now >= end_time and user_data["fishing"]["status"] == "ready_to_pull":
        # Определение типа рыбы с учётом наживки
        if user_data["current_bait"]:
            probabilities = user_data["current_bait"]["probabilities"]
        else:
            probabilities = {"common": 70, "rare": 25, "legendary": 5}  # Стандартные вероятности

        rand = random.randint(1, 100)
        if rand <= probabilities["common"]:
            fish_type = "Неопознанная рыба"
            xp_gained = random.randint(1, 3)
        elif rand <= probabilities["common"] + probabilities["rare"]:
            fish_type = "Неопознанная редкая рыба"
            xp_gained = random.randint(2, 9)
        else:
            fish_type = "Неопознанная легендарная рыба"
            xp_gained = random.randint(15, 30)

        # Определение редкости пойманной рыбы
        rarity = "common"
        if fish_type == "Неопознанная редкая рыба":
            rarity = "rare"
        elif fish_type == "Неопознанная легендарная рыба":
            rarity = "legendary"

        if fish_type not in IDENTIFIED_FISH:
            logger.error(f"Identified fish '{fish_type}' not found in IDENTIFIED_FISH.")
            await update.message.reply_text(
                "❌ Ошибка при опознании рыбы. Попробуйте ещё раз позже.",
                reply_markup=ReplyKeyboardMarkup(
                    [
                        [KeyboardButton(BUTTON_CATCH_FISH)],
                        [KeyboardButton(BUTTON_GO_BACK)]
                    ], resize_keyboard=True
                )
            )
            user_data["fishing"] = None
            return

        # Добавление в инвентарь
        inventory = user_data["inventory"]
        inventory[fish_type] += 1
        weight = IDENTIFIED_FISH[fish_type]
        identification_results = [f"{fish_type} - {weight} КГ"]
        logger.info(f"User {user.id} ({nickname}) caught {fish_type} and gained {xp_gained} XP.")

        # Обновление накопленных показателей на основе фактического веса рыбы
        user_data["total_kg_caught"] += weight

        # Сброс состояния ловли
        user_data["fishing"] = None

        # Добавление опыта
        user_data["experience"] += xp_gained

        # Увеличение счётчиков для любимых удочек и наживок
        current_rod = user_data["current_rod"]["name"]
        current_bait_name = user_data["current_bait"]["name"] if user_data["current_bait"] else "Нет наживки"
        user_data["fish_caught_per_rod"][current_rod] += 1
        user_data["fish_caught_per_bait"][current_bait_name] += 1

        # Проверка уровня
        level_up, new_level, gold_reward = check_level_up(user_data)

        # Обновление ранга
        update_rank(user_data)

        # Генерация сообщения
        if level_up:
            message = generate_fish_catch_message(fish_type, xp_gained, True, new_level, gold_reward)
        else:
            message = generate_fish_catch_message(fish_type, xp_gained)

        await update.message.reply_text(
            message,
            reply_markup=ReplyKeyboardMarkup(
                [
                    [KeyboardButton(BUTTON_CATCH_FISH)],
                    [KeyboardButton(BUTTON_GO_BACK)]
                ], resize_keyboard=True
            )
        )
        logger.info(f"User {user.id} ({nickname}) leveled up to {new_level} and received {gold_reward} gold." if level_up else f"User {user.id} ({nickname}) did not level up.")

    # Хендлер для Опознания рыбы
    async def identify_fish(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_data = users_data[user.id]
        unidentified = user_data["unidentified"]
        nickname = user_data["nickname"] if user_data["nickname"] else user.first_name

        logger.info(f"User {user.id} ({nickname}) is attempting to identify fish.")

        if all(count == 0 for count in unidentified.values()):
            await update.message.reply_text(
                "❗ У вас нет неопознанной рыбы для опознания. Идите ловите! 🎣",
                reply_markup=inventory_menu_keyboard()
            )
            logger.warning(f"User {user.id} ({nickname}) has no unidentified fish.")
            return

        inventory = user_data["inventory"]
        identification_results = []
        for rarity, count in unidentified.items():
            for _ in range(count):
                if rarity == "common":
                    identified_fish = random.choice(COMMON_FISH)[0]
                elif rarity == "rare":
                    identified_fish = random.choice(RARE_FISH)[0]
                elif rarity == "legendary":
                    identified_fish = random.choice(LEGENDARY_FISH)[0]
                else:
                    identified_fish = "Неизвестная рыба"  # На случай неизвестной редкости

                # Проверяем, что рыба есть в IDENTIFIED_FISH
                if identified_fish not in IDENTIFIED_FISH:
                    logger.error(f"Identified fish '{identified_fish}' not found in IDENTIFIED_FISH.")
                    continue

                # Добавляем рыбу в инвентарь безопасным способом
                inventory[identified_fish] = inventory.get(identified_fish, 0) + 1

                weight = IDENTIFIED_FISH.get(identified_fish, 0)
                identification_results.append(f"{identified_fish} - {weight} КГ")
                logger.info(f"User {user.id} ({nickname}) identified {identified_fish} with weight {weight} КГ.")

                # Обновление накопленных показателей на основе фактического веса рыбы
                user_data["total_kg_caught"] += weight

        # Сброс неопознанных рыб
        user_data["unidentified"] = {"common": 0, "rare": 0, "legendary": 0}
        await update.message.reply_text(
            "✅ Все неопознанные рыбы успешно опознаны! 🐟\n\nВы получили:\n" + "\n".join(identification_results),
            reply_markup=inventory_menu_keyboard()
        )

    # Хендлер для Инвентаря
    async def inventory_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_data = users_data[user.id]
        inventory_text = get_inventory_text(user_data)
        nickname = user_data["nickname"] if user_data["nickname"] else user.first_name
        logger.info(f"User {user.id} ({nickname}) viewed inventory.")
        await update.message.reply_text(
            inventory_text,
            reply_markup=inventory_menu_keyboard()
        )

    # Хендлер для Магазина
    async def shop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_data = users_data[user.id]
        shop_info = get_shop_text(user_data)

        if isinstance(shop_info, tuple):
            text, gold = shop_info
        else:
            text = shop_info
            gold = 0

        await update.message.reply_text(
            text,
            reply_markup=shop_menu_keyboard()
        )

        # Сохраняем сумму золота для продажи
        if gold > 0:
            user_data["shop_gold"] = gold
        else:
            user_data["shop_gold"] = 0
        nickname = user_data["nickname"] if user_data["nickname"] else user.first_name
        logger.info(f"User {user.id} ({nickname}) viewed shop. Potential gold: {gold}.")

    # Хендлер для продажи рыбы
    async def sell_fish_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_data = users_data[user.id]
        inventory = user_data["inventory"]
        identified_fish = {fish: qty for fish, qty in inventory.items() if fish in IDENTIFIED_FISH}
        nickname = user_data["nickname"] if user_data["nickname"] else user.first_name

        if not identified_fish:
            await update.message.reply_text(
                "❗ У вас нет опознаной рыбы для продажи. Идите ловите! 🎣",
                reply_markup=shop_menu_keyboard()
            )
            logger.warning(f"User {user.id} ({nickname}) has no identified fish to sell.")
            return

        # Расчёт суммы золота
        total_weight = sum(IDENTIFIED_FISH[fish] * qty for fish, qty in identified_fish.items())
        gold_earned = int(total_weight * pi / 4)

        # Продажа рыбы
        for fish, qty in identified_fish.items():
            inventory[fish] = 0
        # Обновление инвентаря без конвертации в обычный dict
        # Чтобы избежать KeyError, просто оставляем только те рыбы, которые ещё есть
        for fish in list(inventory.keys()):
            if inventory[fish] <= 0:
                del inventory[fish]
        user_data["gold"] += gold_earned
        user_data["total_gold_earned"] += gold_earned

        await update.message.reply_text(
            f"💰 Вы продали всю рыбу за {gold_earned} золота! 🎉",
            reply_markup=shop_menu_keyboard()
        )
        logger.info(f"User {user.id} ({nickname}) sold fish for {gold_earned} gold.")

    # Хендлер для Обменять золото
    async def exchange_gold_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_data = users_data[user.id]
        gold = user_data["gold"]
        exchange_rate = 700  # 1 TON = 700 золота
        minimum_gold = 25000  # Изменено с 5000 на 25000
        nickname = user_data["nickname"] if user_data["nickname"] else user.first_name

        logger.info(f"User {user.id} ({nickname}) requested gold exchange.")

        if gold >= minimum_gold:
            keyboard = [
                [KeyboardButton(BUTTON_CONFIRM_YES), KeyboardButton(BUTTON_CONFIRM_NO)]
            ]
            await update.message.reply_text(
                f"💱 Текущий курс обмена золота на TON составляет 1 TON = {exchange_rate} золота.\n"
                "Совершить обмен? 🔄",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
        else:
            needed = minimum_gold - gold
            keyboard = [
                [KeyboardButton(BUTTON_CONFIRM_NOT_ENOUGH)],
                [KeyboardButton(BUTTON_CONFIRM_NO)]
            ]
            await update.message.reply_text(
                f"💱 Текущий курс обмена золота на TON составляет 1 TON = {exchange_rate} золота.\n"
                f"Нехватает ещё {needed} золота для обмена.",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            logger.warning(f"User {user.id} ({nickname}) does not have enough gold for exchange. Needs {needed} more gold.")

    # Хендлер для подтверждения обмена
    async def confirm_exchange_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_data = users_data[user.id]
        gold = user_data["gold"]
        exchange_rate = 700
        minimum_gold = 25000  # Изменено с 5000 на 25000
        nickname = user_data["nickname"] if user_data["nickname"] else user.first_name

        logger.info(f"User {user.id} ({nickname}) is confirming exchange: {update.message.text}")

        if update.message.text == BUTTON_CONFIRM_YES:
            if gold >= minimum_gold:
                user_data["gold"] -= minimum_gold
                ton = minimum_gold / exchange_rate
                ton = round(ton, 2)
                await update.message.reply_text(
                    f"🔄 Обмен произведён успешно! Вы получили {ton} TON. Пока тестируем! 🛠️",
                    reply_markup=shop_menu_keyboard()
                )
                logger.info(f"User {user.id} ({nickname}) exchanged {minimum_gold} gold for {ton} TON.")
            else:
                needed = minimum_gold - gold
                await update.message.reply_text(
                    f"❗ Нехватает ещё {needed} золота для обмена.",
                    reply_markup=shop_menu_keyboard()
                )
                logger.warning(f"User {user.id} ({nickname}) tried to exchange but lacks {needed} gold.")
        elif update.message.text == BUTTON_CONFIRM_NOT_ENOUGH:
            needed = minimum_gold - gold
            await update.message.reply_text(
                f"❗ Нехватает ещё {needed} золота для обмена.",
                reply_markup=shop_menu_keyboard()
            )
            logger.warning(f"User {user.id} ({nickname}) lacks {needed} gold for exchange.")
        elif update.message.text == BUTTON_CONFIRM_NO:
            await update.message.reply_text(
                "❌ Обмен отменён.",
                reply_markup=shop_menu_keyboard()
            )
            logger.info(f"User {user.id} ({nickname}) cancelled the exchange.")
        else:
            await update.message.reply_text(
                "❗ Неизвестная команда. Пожалуйста, используйте кнопки ниже.",
                reply_markup=shop_menu_keyboard()
            )
            logger.error(f"User {user.id} ({nickname}) sent an unknown response for exchange: '{update.message.text}'")

    # Хендлер для "Вернуться"
    async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_data = users_data[user.id]
        nickname = user_data["nickname"] if user_data["nickname"] else user.first_name
        logger.info(f"User {user.id} ({nickname}) is returning to main menu.")
        await update.message.reply_text(
            "🔙 Возвращение в главное меню.",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    # Хендлер для Таблицы Лидеров
    async def leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        if text == BUTTON_LEADERBOARD:
            await leaderboard(update, context)
        elif text == BUTTON_TOTAL_GOLD:
            await leaderboard_total_gold(update, context)
        elif text == BUTTON_TOTAL_KG:
            await leaderboard_total_kg(update, context)
        elif text == BUTTON_TOTAL_EXPERIENCE:
            await leaderboard_total_experience(update, context)
        else:
            await update.message.reply_text(
                "❗ Неизвестная команда.",
                reply_markup=main_menu_keyboard()
            )
            logger.warning(f"User {update.effective_user.id} sent unknown leaderboard command: '{text}'")

    ###############################################################
    # ОБРАБОТЧИКИ ГИЛЬДИЙ
    ###############################################################

    # (Ваши функции для работы с гильдиями должны быть здесь, если они есть)

    ###############################################################
    # ОБРАБОТЧИКИ КОМАНД И МЕНЮ
    ###############################################################

    # Обработчик текстовых сообщений
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        user = update.effective_user
        user_data = users_data[user.id]
        nickname = user_data["nickname"] if user_data["nickname"] else user.first_name

        # Проверка истечения времени действия наживки при каждом взаимодействии
        current_bait = user_data["current_bait"]
        if current_bait:
            if datetime.utcnow() >= current_bait["end_time"]:
                user_data["current_bait"] = None
                await update.message.reply_text(
                    "🪱 Ваша наживка истекла.",
                    reply_markup=inventory_menu_keyboard()
                )
                logger.info(f"User {user.id} ({nickname})'s bait has expired.")

        logger.info(f"Received message from user {user.id} ({nickname}): {update.message.text}")

        if text == BUTTON_START_FISHING:
            await begin_fishing(update, context)
        elif text == BUTTON_LAKE:
            await lake(update, context)
        elif text == BUTTON_INVENTORY:
            await inventory_handler(update, context)
        elif text == BUTTON_SHOP:
            await shop_handler(update, context)
        elif text == BUTTON_IDENTIFY_FISH:
            await identify_fish(update, context)
        elif text == BUTTON_SELL_ALL:
            await sell_fish_handler(update, context)
        elif text == BUTTON_EXCHANGE_GOLD:
            await exchange_gold_handler(update, context)
        elif text == BUTTON_UPDATE:
            await update_fishing_status(update, context)
        elif text == BUTTON_CATCH_FISH:
            await catch_fish(update, context)
        elif text == BUTTON_PULL:
            await pull_hook(update, context)
        elif text == BUTTON_ABOUT_FISHERMAN:
            await about_fisherman(update, context)
        elif text == BUTTON_GO_BACK:
            await go_back(update, context)
        elif text == BUTTON_LEADERBOARD or text in [BUTTON_TOTAL_GOLD, BUTTON_TOTAL_KG, BUTTON_TOTAL_EXPERIENCE]:
            await leaderboard_handler(update, context)
        else:
            await update.message.reply_text(
                "❗ Неизвестная команда. Пожалуйста, используйте кнопки ниже.",
                reply_markup=main_menu_keyboard()
            )
            logger.warning(f"Unknown command from user {user.id} ({nickname}): {update.message.text}")

    ###############################################################
    # MAIN FUNCTION
    ###############################################################

    def main():
        # Замените "YOUR_TELEGRAM_BOT_TOKEN" на ваш действительный токен
        application = ApplicationBuilder().token("8132081407:AAGSbjptd2JBrVUNOheyvvfC7nwIfMagD4o").build()

        # Создание ConversationHandler для установки ника и покупки
        conv_handler = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Regex(re.escape(BUTTON_START_FISHING)), begin_fishing),
                MessageHandler(filters.Regex(re.escape(BUTTON_RODS)), rods_section),
                MessageHandler(filters.Regex(re.escape(BUTTON_BAITS)), baits_section)
            ],
            states={
                ASK_NICKNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_nickname)],
                BUY_ROD: [
                    MessageHandler(filters.Regex(f"^{re.escape(BUTTON_CONFIRM_YES)}$"), confirm_buy_rod),
                    MessageHandler(filters.Regex(f"^{re.escape(BUTTON_CONFIRM_NO)}$"), cancel_buy_rod),
                    MessageHandler(filters.Regex(f"^{re.escape(BUTTON_GO_BACK)}$"), go_back)
                ],
                CONFIRM_BUY_ROD: [
                    MessageHandler(filters.Regex(f"^{re.escape(BUTTON_CONFIRM_YES)}$"), confirm_buy_rod),
                    MessageHandler(filters.Regex(f"^{re.escape(BUTTON_CONFIRM_NO)}$"), cancel_buy_rod)
                ],
                CONFIRM_REPLACE_ROD: [
                    MessageHandler(filters.Regex(f"^{re.escape(BUTTON_CONFIRM_YES)}$"), confirm_replace_rod),
                    MessageHandler(filters.Regex(f"^{re.escape(BUTTON_CONFIRM_NO)}$"), cancel_replace_rod)
                ],
                BUY_BAIT: [
                    MessageHandler(filters.Regex(f"^{re.escape(BUTTON_CONFIRM_YES)}$"), confirm_buy_bait),
                    MessageHandler(filters.Regex(f"^{re.escape(BUTTON_CONFIRM_NO)}$"), cancel_buy_bait),
                    MessageHandler(filters.Regex(f"^{re.escape(BUTTON_GO_BACK)}$"), go_back)
                ],
                CONFIRM_BUY_BAIT: [
                    MessageHandler(filters.Regex(f"^{re.escape(BUTTON_CONFIRM_YES)}$"), confirm_buy_bait),
                    MessageHandler(filters.Regex(f"^{re.escape(BUTTON_CONFIRM_NO)}$"), cancel_buy_bait)
                ],
                CONFIRM_REPLACE_BAIT: [
                    MessageHandler(filters.Regex(f"^{re.escape(BUTTON_CONFIRM_YES)}$"), confirm_replace_bait),
                    MessageHandler(filters.Regex(f"^{re.escape(BUTTON_CONFIRM_NO)}$"), cancel_replace_bait)
                ],
            },
            fallbacks=[
                CommandHandler("cancel", cancel_nickname),
                MessageHandler(filters.Regex(re.escape(BUTTON_GO_BACK)), go_back)
            ],
            allow_reentry=True
        )

        # Добавление обработчиков команд
        application.add_handler(CommandHandler("start", start))

        # Добавление обработчиков ConversationHandler
        application.add_handler(conv_handler)

        # Добавление обработчиков сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Запуск бота
        application.run_polling()

    if __name__ == '__main__':
        main()
