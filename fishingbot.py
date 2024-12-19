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

# ЛОГИРОВАНИЕ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Кнопки
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

ASK_NICKNAME = 1
BUY_ROD = 2
CONFIRM_BUY_ROD = 3
BUY_BAIT = 4
CONFIRM_BUY_BAIT = 5
EXCHANGE = 6
LEADERBOARD_CATEGORY = 7

users_data = defaultdict(lambda: {
    "nickname": None,
    "inventory": defaultdict(int),  # {(fish_name, weight, rarity): qty}
    "gold": 0,
    "unidentified": {"common": 0, "rare": 0, "legendary": 0},
    "fishing": None,
    "shop_gold": 0,
    "total_gold_earned": 0,
    "total_kg_caught": 0,
    "current_rod": {
        "name": "Бамбуковая удочка 🎣",
        "bonus_percent": 0
    },
    "current_bait": None,
    "experience": 0,
    "level": 1,
    "rank": "Юный рыбак",
    "registration_time": datetime.utcnow(),
    "fish_caught_per_rod": defaultdict(int),
    "fish_caught_per_bait": defaultdict(int)
})

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
]

for lvl in range(11, 76):
    required_xp = int(LEVELS[-1]["required_xp"] * 1.5)
    if 11 <= lvl <= 15:
        rank = "Любитель клёва"
    elif 16 <= lvl <= 20:
        rank = "Знаток крючков"
    elif 21 <= lvl <= 25:
        rank = "Мастер наживки"
    elif 26 <= lvl <= 30:
        rank = "Искусный рыбак"
    elif 31 <= lvl <= 35:
        rank = "Охотник за уловом"
    elif 36 <= lvl <= 40:
        rank = "Настоящий рыболов"
    elif 41 <= lvl <= 45:
        rank = "Виртуоз рыбалки"
    elif 46 <= lvl <= 50:
        rank = "Укротитель рек"
    elif 51 <= lvl <= 55:
        rank = "Морской добытчик"
    elif 56 <= lvl <= 60:
        rank = "Легенда пруда"
    elif 61 <= lvl <= 65:
        rank = "Властелин озёр"
    elif 66 <= lvl <= 70:
        rank = "Мастер рыбалки"
    elif 71 <= lvl <= 75:
        rank = "Эпический рыболов"
    else:
        rank = "Рыболов"
    LEVELS.append({"level": lvl, "required_xp": required_xp, "rank": rank})

FISH_DATA = {
    "common": {
        "prefixes": ["Мелкий", "Хилый", "Молодой", "Вертлявый", "Большой", "Старый", "Обычный", "Косой"],
        "names": ["Карасик", "Окунек", "Бычок", "Ёрш", "Подлещик", "Голавль"],
        "weight_range": (1, 5)
    },
    "rare": {
        "prefixes": ["Средний", "Хороший", "Солидный", "Налитый", "Блестящий", "Взрослый", "Упитанный", "Почти Трофейный"],
        "names": ["Карась", "Окунь", "Лещ", "Ротан", "Угорь", "Судак"],
        "weight_range": (7, 16)
    },
    "legendary": {
        "prefixes": ["Мощный", "Огромный", "Трофейный", "Невероятный", "Переливающийся", "Здоровенный", "Колоссальный"],
        "names": ["Язь", "Сом", "Налим", "Тунец", "Угорь", "Лосось", "Осётр"],
        "weight_range": (22, 79)
    }
}

RODS = [
    {"name": "Удочка Новичка 🎣", "price": 10, "bonus_percent": 5},
    {"name": "Удочка Любителя 🎣", "price": 50, "bonus_percent": 10},
    {"name": "Удочка Классическая 🎣", "price": 200, "bonus_percent": 15},
    {"name": "Удочка ПРО 🎣", "price": 500, "bonus_percent": 25},
    {"name": "Золотая Удочка 🎣", "price": 5000, "bonus_percent": 50},
]

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

def main_menu_keyboard():
    keyboard = [
        [KeyboardButton(BUTTON_LAKE)],
        [KeyboardButton(BUTTON_INVENTORY), KeyboardButton(BUTTON_ABOUT_FISHERMAN)],
        [KeyboardButton(BUTTON_SHOP), KeyboardButton(BUTTON_LEADERBOARD)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def lake_menu_keyboard():
    keyboard = [
        [KeyboardButton(BUTTON_CATCH_FISH)],
        [KeyboardButton(BUTTON_UPDATE)],
        [KeyboardButton(BUTTON_GO_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def inventory_menu_keyboard():
    keyboard = [
        [KeyboardButton(BUTTON_IDENTIFY_FISH)],
        [KeyboardButton(BUTTON_GO_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def shop_menu_keyboard():
    keyboard = [
        [KeyboardButton(BUTTON_RODS), KeyboardButton(BUTTON_BAITS)],
        [KeyboardButton(BUTTON_SELL_ALL), KeyboardButton(BUTTON_EXCHANGE_GOLD)],
        [KeyboardButton(BUTTON_GO_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def leaderboard_menu_keyboard():
    keyboard = [
        [KeyboardButton(BUTTON_TOTAL_GOLD), KeyboardButton(BUTTON_TOTAL_KG)],
        [KeyboardButton(BUTTON_TOTAL_EXPERIENCE)],
        [KeyboardButton(BUTTON_GO_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def about_fisherman_keyboard():
    keyboard = [
        [KeyboardButton(BUTTON_GO_BACK)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_welcome_text():
    return (
        "🌅 Добро пожаловать на берега тихой реки!\n\n"
        "Здесь вы сможете поймать множество рыбы, опознать её и продать за настоящую криптовалюту.\n\n"
        "Сделайте первый шаг к большой рыбацкой славе!"
    )

def get_onboarding_text():
    return (
        "🎣 Добро пожаловать в удивительный мир рыбалки!\n\n"
        "Прежде чем начать, давайте придумаем вам имя.\n"
        "Введите имя (до 25 символов, только буквы и пробелы):"
    )

def get_lake_text(user_nickname):
    return (
        f"🌊 {user_nickname} подошёл к зеркальной глади озера. Лёгкий ветерок качает камыши, а над водой кружат стрекозы.\n"
        "Что вы хотите сделать?"
    )

def get_required_xp(level):
    for lvl in LEVELS:
        if lvl["level"] == level:
            return lvl["required_xp"]
    if level > LEVELS[-1]["level"]:
        last_required = LEVELS[-1]["required_xp"]
        additional_levels = level - LEVELS[-1]["level"]
        return int(last_required * (1.5 ** additional_levels))
    return 10

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

    if user_data["fish_caught_per_rod"]:
        favorite_rod = max(user_data["fish_caught_per_rod"], key=user_data["fish_caught_per_rod"].get)
    else:
        favorite_rod = "нет"

    if user_data["fish_caught_per_bait"]:
        favorite_bait = max(user_data["fish_caught_per_bait"], key=user_data["fish_caught_per_bait"].get)
    else:
        favorite_bait = "нет"

    text = (
        f"👤 О рыбаке:\n\n"
        f"Имя: {nickname}\n"
        f"Уровень: {level}\n"
        f"Ранг: {rank}\n"
        f"Опыт: {experience}/{required_xp}\n"
        f"Возраст вашего приключения: {age}\n"
        f"Любимая удочка: {favorite_rod}\n"
        f"Любимая наживка: {favorite_bait}\n\n"
        "Продолжайте ловить, опознавать и продавать рыбу, чтобы расти в мастерстве!"
    )
    return text

def generate_fish_catch_message(fish_type, xp_gained, level_up=False, new_level=None, gold_reward=0):
    message = (
        f"🎉 Вы выудили {fish_type} из глубин!\n"
        f"Опыт +{xp_gained} ⭐"
    )
    if level_up:
        message += f"\nВаш уровень повышен до {new_level}!"
        if gold_reward > 0:
            message += f"\nВы получили дополнительно {gold_reward} золота за достижение!"
    return message

def get_inventory_text(user_data):
    inventory = user_data["inventory"]
    unidentified = user_data["unidentified"]
    gold = user_data["gold"]
    rod = user_data["current_rod"]
    bait = user_data["current_bait"]
    text = "🎒 Ваш инвентарь:\n\n"
    text += f"🎣 Удочка: {rod['name']} (уменьшение времени на {rod['bonus_percent']}%)\n"
    if bait:
        remaining = int((bait["end_time"]-datetime.utcnow()).total_seconds()/60)
        if remaining>0:
            text += f"🪱 Наживка: {bait['name']} (ещё {remaining} мин)\n"
        else:
            text+="🪱 Наживка: нет\n"
    else:
        text+="🪱 Наживка: нет\n"

    text+="\n"
    # Неопознанная рыба
    common_count=unidentified['common']
    rare_count=unidentified['rare']
    legend_count=unidentified['legendary']
    if common_count>0:
        text+=f"• Неопознанные рыбы - {common_count}\n"
    if rare_count>0:
        text+=f"• Неопознанные редкие рыбы - {rare_count}\n"
    if legend_count>0:
        text+=f"• Неопознанные легендарные рыбы - {legend_count}\n"
    if common_count==0 and rare_count==0 and legend_count==0:
        text+="Нет неопознанной рыбы.\n"

    # Опознанная рыба
    identified_fish = [(k,v) for k,v in inventory.items() if v>0 and isinstance(k,tuple)]
    if identified_fish:
        text+="\nОпознанная рыба:\n"
        for (fname, w, r), qty in identified_fish:
            total_w = w*qty
            text+=f"• {fname} (редкость: {r}) - вес: {w} КГ - {qty} шт. (итого {total_w} КГ)\n"

    text += f"\n💰 Золото: {gold}"
    return text

def get_shop_text(user_data):
    inventory = user_data["inventory"]
    identified = [(k,v) for k,v in inventory.items() if v>0 and isinstance(k,tuple)]
    if not identified:
        return ("🏪 В магазине пусто для продажи. Сначала поймайте и опознайте рыбу!",0)
    text="🏪 Добро пожаловать в магазин!\n\nВаша опознанная рыба:\n"
    total_weight=0
    for (fname,w,r),qty in identified:
        tw=w*qty
        text+=f"{fname} (р. {r}) - {qty} шт. (Вес одного: {w} КГ, всего: {tw} КГ)\n"
        total_weight+=tw
    gold=int(total_weight*pi/4)
    text+=f"\nПродать всю рыбу за {gold} золота?"
    return (text,gold)

def check_level_up(user_data):
    level_up=False
    gold_reward=0
    new_level=None
    while user_data["level"]<=len(LEVELS) and user_data["experience"]>=get_required_xp(user_data["level"]):
        user_data["level"]+=1
        update_rank(user_data)
        gold_reward+=user_data["level"]*2
        user_data["gold"]+=user_data["level"]*2
        level_up=True
        new_level=user_data["level"]
    return level_up,new_level,gold_reward

def update_rank(user_data):
    level=user_data["level"]
    rank="Юный рыбак"
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
    elif 16 <= level <= 20:
        rank = "Знаток крючков"
    elif 21 <= level <= 25:
        rank = "Мастер наживки"
    elif 26 <= level <= 30:
        rank = "Искусный рыбак"
    elif 31 <= level <= 35:
        rank = "Охотник за уловом"
    elif 36 <= level <= 40:
        rank = "Настоящий рыболов"
    elif 41 <= level <= 45:
        rank = "Виртуоз рыбалки"
    elif 46 <= level <= 50:
        rank = "Укротитель рек"
    elif 51 <= level <= 55:
        rank = "Морской добытчик"
    elif 56 <= level <= 60:
        rank = "Легенда пруда"
    elif 61 <= level <= 65:
        rank = "Властелин озёр"
    elif 66 <= level <= 70:
        rank = "Мастер рыбалки"
    elif 71 <= level <= 75:
        rank = "Эпический рыболов"
    user_data["rank"]=rank

def generate_identified_fish(rarity):
    prefix=random.choice(FISH_DATA[rarity]["prefixes"])
    fname=random.choice(FISH_DATA[rarity]["names"])
    w=random.randint(*FISH_DATA[rarity]["weight_range"])
    return (f"{prefix} {fname}", w, rarity)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    ud=users_data[user.id]
    if ud["registration_time"] == datetime.utcnow():
        ud["gold"]=0
        ud["total_gold_earned"]=0
        ud["total_kg_caught"]=0
        ud["experience"]=0
        ud["level"]=1
        ud["rank"]="Юный рыбак"
        ud["registration_time"]=datetime.utcnow()
        ud["fish_caught_per_rod"]=defaultdict(int)
        ud["fish_caught_per_bait"]=defaultdict(int)
    logger.info(f"User {user.id} ({user.first_name}) started bot.")
    await update.message.reply_text(get_welcome_text(),reply_markup=ReplyKeyboardMarkup(
        [[KeyboardButton(BUTTON_START_FISHING)]], resize_keyboard=True
    ))

async def begin_fishing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    ud=users_data[user.id]
    if not ud["nickname"]:
        await update.message.reply_text(get_onboarding_text(),reply_markup=ReplyKeyboardRemove())
        return ASK_NICKNAME
    else:
        await update.message.reply_text("🌞 Отличная погода для рыбалки! Удачи!",
                                        reply_markup=main_menu_keyboard())
        return ConversationHandler.END

async def set_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    nickname=update.message.text.strip()
    if len(nickname)>25:
        await update.message.reply_text("❌ Имя слишком длинное.")
        return ASK_NICKNAME
    if not re.match(r'^[A-Za-zА-Яа-яЁё\s]+$', nickname):
        await update.message.reply_text("❌ Только буквы и пробелы!")
        return ASK_NICKNAME
    existing=[d["nickname"] for uid,d in users_data.items() if d["nickname"]]
    if nickname in existing:
        await update.message.reply_text("❌ Это имя уже занято.")
        return ASK_NICKNAME
    users_data[user.id]["nickname"]=nickname
    await update.message.reply_text(f"✅ Теперь вы - {nickname}!\nДобро пожаловать!",
                                    reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def cancel_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отмена.",reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def lake_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    ud=users_data[user.id]
    name=ud["nickname"] if ud["nickname"] else user.first_name
    txt=get_lake_text(name)
    await update.message.reply_text(txt,reply_markup=lake_menu_keyboard())

async def catch_fish_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    ud=users_data[user.id]
    if ud["fishing"]:
        await update.message.reply_text("Вы уже ждёте улова!")
        return
    rb=ud["current_rod"]["bonus_percent"]
    base_delay=random.randint(5,33)
    delay=int(base_delay*(1-rb/100))
    if delay<1: delay=1
    ud["fishing"]={"end_time":datetime.utcnow()+timedelta(seconds=delay),"status":"fishing"}
    await update.message.reply_text(
        f"🎣 Забросили удочку... Подождите {delay} секунд.",
        reply_markup=lake_menu_keyboard()
    )

async def update_fishing_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    ud=users_data[user.id]
    if not ud["fishing"]:
        await update.message.reply_text("Вы сейчас не ловите рыбу.",reply_markup=lake_menu_keyboard())
        return
    end=ud["fishing"]["end_time"]
    now=datetime.utcnow()
    rem=(end-now).total_seconds()
    if rem>0:
        await update.message.reply_text(f"Рыбка ещё не попалась, осталось ~{int(rem)} сек.")
    else:
        ud["fishing"]["status"]="ready_to_pull"
        await update.message.reply_text("Кажется, что-то клюнуло! Тяните!",
                                        reply_markup=ReplyKeyboardMarkup([
                                            [KeyboardButton(BUTTON_PULL)],
                                            [KeyboardButton(BUTTON_GO_BACK)]
                                        ],resize_keyboard=True))

async def pull_hook_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    ud=users_data[user.id]
    if not ud["fishing"]:
        await update.message.reply_text("Сначала начните ловить.",
                                        reply_markup=lake_menu_keyboard())
        return
    end=ud["fishing"]["end_time"]
    now=datetime.utcnow()
    if now>=end and ud["fishing"]["status"]=="ready_to_pull":
        r=random.randint(1,100)
        if r<=70:
            ftype="Неопознанная рыба"
            rarity="common"
            xp=random.randint(1,3)
        elif r<=95:
            ftype="Неопознанная редкая рыба"
            rarity="rare"
            xp=random.randint(4,9)
        else:
            ftype="Неопознанная легендарная рыба"
            rarity="legendary"
            xp=random.randint(10,30)
        ud["unidentified"][rarity]+=1
        ud["fishing"]=None
        ud["experience"]+=xp
        rod=ud["current_rod"]["name"]
        bait=ud["current_bait"]["name"] if ud["current_bait"] else "Нет наживки"
        ud["fish_caught_per_rod"][rod]+=1
        ud["fish_caught_per_bait"][bait]+=1
        lvl_up,n_lvl,g_reward=check_level_up(ud)
        update_rank(ud)
        msg=generate_fish_catch_message(ftype,xp,lvl_up,n_lvl,g_reward)
        await update.message.reply_text(msg,reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton(BUTTON_CATCH_FISH)],
            [KeyboardButton(BUTTON_GO_BACK)]
        ],resize_keyboard=True))
    else:
        await update.message.reply_text("Поторопились и сорвали рыбу!",
                                        reply_markup=ReplyKeyboardMarkup([
                                            [KeyboardButton(BUTTON_CATCH_FISH)],
                                            [KeyboardButton(BUTTON_GO_BACK)]
                                        ],resize_keyboard=True)
                                        )
        ud["fishing"]=None

async def identify_fish_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    ud=users_data[user.id]
    un=ud["unidentified"]
    if all(x==0 for x in un.values()):
        await update.message.reply_text("Нет неопознанной рыбы.",
                                        reply_markup=inventory_menu_keyboard())
        return
    results=[]
    # Опознаём всю рыбу
    for rarity,count in un.items():
        for _ in range(count):
            fname,w,r=generate_identified_fish(rarity)
            ud["inventory"][(fname,w,r)]+=1
            ud["total_kg_caught"]+=w
            results.append(f"{fname} ({r}) - {w} КГ")

    ud["unidentified"]={"common":0,"rare":0,"legendary":0}
    msg="🔍 Вы с любопытством рассматриваете свой улов...\n" \
        "Теперь вы знаете, кто скрывался в глубинах:\n"+"\n".join(results)
    await update.message.reply_text(msg,reply_markup=inventory_menu_keyboard())

async def inventory_handler_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    ud=users_data[user.id]
    txt=get_inventory_text(ud)
    await update.message.reply_text(txt,reply_markup=inventory_menu_keyboard())

async def shop_handler_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    ud=users_data[user.id]
    info,g= get_shop_text(ud)
    ud["shop_gold"]=g
    await update.message.reply_text(info,reply_markup=shop_menu_keyboard())

async def sell_fish_handler_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    ud=users_data[user.id]
    inv=ud["inventory"]
    identified = [(k,v) for k,v in inv.items() if v>0 and isinstance(k,tuple)]
    if not identified:
        await update.message.reply_text("Нет опознанной рыбы для продажи.",reply_markup=shop_menu_keyboard())
        return
    total_w=0
    for (fname,w,r),qty in identified:
        total_w+=w*qty
        inv[(fname,w,r)]=0
    gold_earned=int(total_w*pi/4)
    ud["gold"]+=gold_earned
    ud["total_gold_earned"]+=gold_earned
    await update.message.reply_text(
        f"Вы продали всю опознанную рыбу за {gold_earned} золота!",
        reply_markup=shop_menu_keyboard()
    )

async def exchange_gold_handler_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    ud=users_data[user.id]
    if ud["gold"]>=25000:
        keyboard=[[KeyboardButton(BUTTON_CONFIRM_YES),KeyboardButton(BUTTON_CONFIRM_NO)]]
        await update.message.reply_text("Хотите обменять 25000 золота на TON?",
                                        reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True))
        return EXCHANGE
    else:
        need=25000-ud["gold"]
        await update.message.reply_text(
            f"Не хватает {need} золота для обмена.",
            reply_markup=shop_menu_keyboard()
        )

async def confirm_exchange_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    ud=users_data[user.id]
    if update.message.text==BUTTON_CONFIRM_YES:
        if ud["gold"]>=25000:
            ud["gold"]-=25000
            await update.message.reply_text("Обмен совершен! Вы получили TON.",
                                            reply_markup=shop_menu_keyboard())
        else:
            need=25000-ud["gold"]
            await update.message.reply_text(
                f"Не хватает {need} золота!",
                reply_markup=shop_menu_keyboard()
            )
    else:
        await update.message.reply_text("Обмен отменен.",
                                        reply_markup=shop_menu_keyboard())
    return ConversationHandler.END

async def about_fisherman_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    ud=users_data[user.id]
    txt=get_about_fisherman_text(ud)
    await update.message.reply_text(txt,reply_markup=about_fisherman_keyboard())

async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Возвращаемся...",
                                    reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def leaderboard_handler_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выберите категорию рейтинга:",
                                    reply_markup=leaderboard_menu_keyboard())
    return LEADERBOARD_CATEGORY

async def leaderboard_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text=update.message.text
    all_users=list(users_data.items())
    if text==BUTTON_TOTAL_GOLD:
        all_users.sort(key=lambda x:x[1]["total_gold_earned"],reverse=True)
        cat="золоту"
        val=lambda d:d["total_gold_earned"]
    elif text==BUTTON_TOTAL_KG:
        all_users.sort(key=lambda x:x[1]["total_kg_caught"],reverse=True)
        cat="кг рыбы"
        val=lambda d:d["total_kg_caught"]
    elif text==BUTTON_TOTAL_EXPERIENCE:
        all_users.sort(key=lambda x:x[1]["experience"],reverse=True)
        cat="опыту"
        val=lambda d:d["experience"]
    else:
        await go_back(update, context)
        return ConversationHandler.END
    msg=f"🏆 Топ по {cat}:\n"
    top=all_users[:10]
    i=1
    for uid,data in top:
        name=data["nickname"] if data["nickname"] else "Неизвестный рыбак"
        msg+=f"{i}. {name} - {val(data)}\n"
        i+=1
    await update.message.reply_text(msg,reply_markup=leaderboard_menu_keyboard())
    return LEADERBOARD_CATEGORY

async def rods_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text="🎣 Удочки в продаже:\n"
    for rod in RODS:
        text+=f"{rod['name']} - {rod['price']} золота (уменьшение времени на {rod['bonus_percent']}%)\n"
    text+="Выберите удочку для покупки или вернитесь назад."
    keyboard=[[KeyboardButton(r["name"])] for r in RODS]
    keyboard.append([KeyboardButton(BUTTON_GO_BACK)])
    await update.message.reply_text(text,reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True))
    return BUY_ROD

async def buy_rod_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    rod_name=update.message.text.strip()
    if rod_name==BUTTON_GO_BACK:
        await update.message.reply_text("Возвращаемся в магазин.",
                                        reply_markup=shop_menu_keyboard())
        return ConversationHandler.END
    rod=next((r for r in RODS if r["name"]==rod_name),None)
    if rod:
        context.user_data["pending_rod"]=rod
        keyboard=[[KeyboardButton(BUTTON_CONFIRM_YES),KeyboardButton(BUTTON_CONFIRM_NO)]]
        await update.message.reply_text(
            f"Купить {rod['name']} за {rod['price']} золота?\nЭто улучшит скорость ловли на {rod['bonus_percent']}%.",
            reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True)
        )
        return CONFIRM_BUY_ROD
    else:
        await update.message.reply_text("Неизвестная удочка.",reply_markup=shop_menu_keyboard())
        return ConversationHandler.END

async def confirm_buy_rod_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    ud=users_data[user.id]
    rod=context.user_data.get("pending_rod")
    if not rod:
        await update.message.reply_text("Ошибка: нет выбранной удочки.",reply_markup=shop_menu_keyboard())
        return ConversationHandler.END
    if update.message.text==BUTTON_CONFIRM_YES:
        if ud["gold"]>=rod["price"]:
            ud["gold"]-=rod["price"]
            ud["current_rod"]=rod
            await update.message.reply_text(
                f"Поздравляем! Теперь у вас {rod['name']}!",
                reply_markup=shop_menu_keyboard())
        else:
            need=rod["price"]-ud["gold"]
            await update.message.reply_text(
                f"Недостаточно золота! Не хватает {need}.",
                reply_markup=shop_menu_keyboard())
    else:
        await update.message.reply_text("Покупка отменена.",
                                        reply_markup=shop_menu_keyboard())
    context.user_data.pop("pending_rod",None)
    return ConversationHandler.END

async def baits_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text="🪱 Наживки в продаже:\n"
    for b in BAITS:
        text+=f"{b['name']} - {b['price']} золота\n"
    text+="Выберите наживку или вернитесь назад."
    keyboard=[[KeyboardButton(b["name"])] for b in BAITS]
    keyboard.append([KeyboardButton(BUTTON_GO_BACK)])
    await update.message.reply_text(text,reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True))
    return BUY_BAIT

async def buy_bait_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    bait_name=update.message.text.strip()
    if bait_name==BUTTON_GO_BACK:
        await update.message.reply_text("Возвращаемся в магазин.",
                                        reply_markup=shop_menu_keyboard())
        return ConversationHandler.END
    bait=next((b for b in BAITS if b["name"]==bait_name),None)
    if bait:
        context.user_data["pending_bait"]=bait
        keyboard=[[KeyboardButton(BUTTON_CONFIRM_YES),KeyboardButton(BUTTON_CONFIRM_NO)]]
        await update.message.reply_text(
            f"Купить {bait['name']} за {bait['price']} золота?\nЭто может изменить ваши шансы поймать редкую или легендарную рыбу!",
            reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True)
        )
        return CONFIRM_BUY_BAIT
    else:
        await update.message.reply_text("Неизвестная наживка.",reply_markup=shop_menu_keyboard())
        return ConversationHandler.END

async def confirm_buy_bait_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    ud=users_data[user.id]
    bait=context.user_data.get("pending_bait")
    if not bait:
        await update.message.reply_text("Ошибка: нет выбранной наживки.",reply_markup=shop_menu_keyboard())
        return ConversationHandler.END
    if update.message.text==BUTTON_CONFIRM_YES:
        if ud["gold"]>=bait["price"]:
            ud["gold"]-=bait["price"]
            ud["current_bait"]={
                "name":bait["name"],
                "end_time":datetime.utcnow()+bait["duration"],
                "probabilities":bait["probabilities"]
            }
            await update.message.reply_text(
                f"Вы купили {bait['name']}! Теперь ваши шансы могут измениться!",
                reply_markup=shop_menu_keyboard())
        else:
            need=bait["price"]-ud["gold"]
            await update.message.reply_text(
                f"Недостаточно золота! Не хватает {need}.",
                reply_markup=shop_menu_keyboard())
    else:
        await update.message.reply_text("Покупка наживки отменена.",
                                        reply_markup=shop_menu_keyboard())
    context.user_data.pop("pending_bait",None)
    return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❗ Неизвестная команда. Используйте меню!",
                                    reply_markup=main_menu_keyboard())

def main():
    token = "8132081407:AAGSbjptd2JBrVUNOheyvvfC7nwIfMagD4o" # вставьте свой токен
    application = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(re.escape(BUTTON_START_FISHING)), begin_fishing),
            MessageHandler(filters.Regex(re.escape(BUTTON_RODS)), rods_section),
            MessageHandler(filters.Regex(re.escape(BUTTON_BAITS)), baits_section),
            MessageHandler(filters.Regex(re.escape(BUTTON_EXCHANGE_GOLD)), exchange_gold_handler_func),
            MessageHandler(filters.Regex(re.escape(BUTTON_LEADERBOARD)), leaderboard_handler_func)
        ],
        states={
            ASK_NICKNAME:[MessageHandler(filters.TEXT & ~filters.COMMAND,set_nickname)],
            BUY_ROD:[MessageHandler(filters.TEXT & ~filters.COMMAND,buy_rod_handler)],
            CONFIRM_BUY_ROD:[MessageHandler(filters.Regex(f"^{BUTTON_CONFIRM_YES}$|^{BUTTON_CONFIRM_NO}$"),confirm_buy_rod_handler)],
            BUY_BAIT:[MessageHandler(filters.TEXT & ~filters.COMMAND,buy_bait_handler)],
            CONFIRM_BUY_BAIT:[MessageHandler(filters.Regex(f"^{BUTTON_CONFIRM_YES}$|^{BUTTON_CONFIRM_NO}$"),confirm_buy_bait_handler)],
            EXCHANGE:[MessageHandler(filters.Regex(f"^{BUTTON_CONFIRM_YES}$|^{BUTTON_CONFIRM_NO}$"),confirm_exchange_handler)],
            LEADERBOARD_CATEGORY:[
                MessageHandler(filters.Regex(f"^{BUTTON_TOTAL_GOLD}$|^{BUTTON_TOTAL_KG}$|^{BUTTON_TOTAL_EXPERIENCE}$"),leaderboard_show),
                MessageHandler(filters.Regex(f"^{BUTTON_GO_BACK}$"), go_back)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(re.escape(BUTTON_GO_BACK)), go_back),
            CommandHandler("cancel", cancel_nickname)
        ],
        allow_reentry=True
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^"+re.escape(BUTTON_LAKE)+"$"), lake_handler))
    application.add_handler(MessageHandler(filters.Regex("^"+re.escape(BUTTON_INVENTORY)+"$"), inventory_handler_func))
    application.add_handler(MessageHandler(filters.Regex("^"+re.escape(BUTTON_SHOP)+"$"), shop_handler_func))
    application.add_handler(MessageHandler(filters.Regex("^"+re.escape(BUTTON_ABOUT_FISHERMAN)+"$"), about_fisherman_handler))
    application.add_handler(MessageHandler(filters.Regex("^"+re.escape(BUTTON_CATCH_FISH)+"$"), catch_fish_handler))
    application.add_handler(MessageHandler(filters.Regex("^"+re.escape(BUTTON_UPDATE)+"$"), update_fishing_status_handler))
    application.add_handler(MessageHandler(filters.Regex("^"+re.escape(BUTTON_PULL)+"$"), pull_hook_handler))
    application.add_handler(MessageHandler(filters.Regex("^"+re.escape(BUTTON_IDENTIFY_FISH)+"$"), identify_fish_handler))
    application.add_handler(MessageHandler(filters.Regex("^"+re.escape(BUTTON_SELL_ALL)+"$"), sell_fish_handler_func))

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__=="__main__":
    main()
