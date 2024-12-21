import logging
import random
import re
from math import pi
from datetime import datetime, timedelta
import math

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)

from guilds import guild_conversation_handler, add_guild_exp, get_guild_membership_rank, GUILD_BONUSES, GUILD_LEVELS
from db import Database
from quests import quests_conversation_handler, BUTTON_TASKS

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = None

BUTTON_START_FISHING = "🎣 Начать рыбалку"
BUTTON_LAKE = "🏞 Озеро"
BUTTON_INVENTORY = "📦 Инвентарь"
BUTTON_SHOP = "🏪 Магазин"
BUTTON_CATCH_FISH = "🎣 Ловить рыбку"
BUTTON_UPDATE = "🔄 Обновить"
BUTTON_GO_BACK = "🔙 Вернуться"
BUTTON_IDENTIFY_FISH = "🔍 Опознать рыбу"
BUTTON_SELL_ALL = "🐟 Продать всю рыбу"
BUTTON_EXCHANGE_GOLD = "Обмен золото на TON"
BUTTON_PULL = "🐟 Тянуть"
BUTTON_CONFIRM_YES = "✅ Да"
BUTTON_CONFIRM_NO = "❌ Нет"
BUTTON_LEADERBOARD = "🏆 Таблица Лидеров"
BUTTON_TOTAL_GOLD = "Лидеры по золоту"
BUTTON_TOTAL_KG = "Лидеры по улову"
BUTTON_TOTAL_EXPERIENCE = "Лидеры по опыту"
BUTTON_RODS = "🎣 Удочки"
BUTTON_BAITS = "🪱 Наживки"
BUTTON_ABOUT_FISHERMAN = "👤 О рыбаке"
BUTTON_GUILDS = "🛡️ Гильдии"
BUTTON_MY_GUILD = "🛡️ Моя Гильдия"
BUTTON_HELP = "🔍 Помощь"

BUTTON_HELP_FISHING = "Рыбалка 🎣"
BUTTON_HELP_RODS = "Удочки 🎣"
BUTTON_HELP_BAITS = "Наживка 🪱"
BUTTON_HELP_SHOP = "Магазин 🏪"
BUTTON_HELP_GUILDS = "Гильдии 🛡️"
BUTTON_HELP_ABOUT = "О рыбаке 👤"

ASK_NICKNAME = 1
BUY_ROD = 2
CONFIRM_BUY_ROD = 3
BUY_BAIT = 4
CONFIRM_BUY_BAIT = 5
EXCHANGE = 6
LEADERBOARD_CATEGORY = 7

HELP_MENU = 900
HELP_SUBTOPIC = 901

FISH_DATA = {
    "common": {
        "prefixes": ["Мелкий", "Хилый", "Молодой", "Вертлявый", "Большой", "Старый", "Обычный", "Косой"],
        "names": ["Карасик", "Окунек", "Бычок", "Ёрш", "Подлещик", "Голавль"],
        "weight_range": (1, 5)
    },
    "rare": {
        "prefixes": ["Средний", "Хороший", "Солидный", "Налитый", "Блестящий", "Взрослый", "Упитанный", "Почти Трофейный"],
        "names": ["Карась", "Окунь", "Лещ", "Ротан", "Угорёк", "Судак"],  # <-- БЫЛО “Угорь”, теперь “Угорёк”
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

def main_menu_keyboard(user_id):
    u=db.get_user(user_id)
    guild_id=u[14]
    guild_button = BUTTON_MY_GUILD if guild_id is not None else BUTTON_GUILDS
    keyboard = [
        [KeyboardButton(BUTTON_LAKE), KeyboardButton(BUTTON_INVENTORY), KeyboardButton(BUTTON_ABOUT_FISHERMAN)],
        [KeyboardButton(BUTTON_SHOP), KeyboardButton(BUTTON_LEADERBOARD), KeyboardButton(guild_button)],
        [KeyboardButton(BUTTON_TASKS), KeyboardButton(BUTTON_HELP)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_required_xp(level):
    LEVELS = [
        {"level": 1, "required_xp": 10},
        {"level": 2, "required_xp": 38},
        {"level": 3, "required_xp": 89},
        {"level": 4, "required_xp": 169},
        {"level": 5, "required_xp": 477},
        {"level": 6, "required_xp": 1008},
        {"level": 7, "required_xp": 1809},
        {"level": 8, "required_xp": 2940},
        {"level": 9, "required_xp": 4470},
        {"level": 10, "required_xp": 6471},
    ]
    for lvl in range(11,76):
        required_xp = int(LEVELS[-1]["required_xp"] * 1.5)
        LEVELS.append({"level": lvl,"required_xp": required_xp})
    for lvl_data in LEVELS:
        if lvl_data["level"]==level:
            return lvl_data["required_xp"]
    if level>LEVELS[-1]["level"]:
        last_required=LEVELS[-1]["required_xp"]
        additional_levels=level-LEVELS[-1]["level"]
        return int(last_required*(1.5**additional_levels))
    return 10

def update_rank(user_id):
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
    for lvl in range(11,76):
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

    u=db.get_user(user_id)
    level = u[4]
    for lvl_data in LEVELS:
        if lvl_data["level"]==level:
            db.update_user(user_id, rank=lvl_data["rank"])
            return

def check_level_up(user_id):
    u=db.get_user(user_id)
    experience = u[3]
    level = u[4]
    gold = u[2]

    level_up=False
    gold_reward=0
    new_level=None
    while level<=75 and experience>=get_required_xp(level):
        level+=1
        reward = level*2
        gold+=reward
        gold_reward+=reward
        level_up=True
        new_level=level
    db.update_user(user_id, level=level, gold=gold)
    update_rank(user_id)
    return level_up,new_level,gold_reward

def get_about_fisherman_text(user_id):
    u=db.get_user(user_id)
    nickname = u[1]
    gold = u[2]
    experience = u[3]
    level = u[4]
    rank = u[5]
    registration_time = datetime.fromisoformat(u[6])
    age_delta = datetime.utcnow() - registration_time
    hours, remainder = divmod(int(age_delta.total_seconds()), 3600)
    minutes, _ = divmod(remainder, 60)
    age = f"{hours} часов и {minutes} минут"
    total_gold_earned = u[12]
    total_kg_caught = u[13]
    guild_id = u[14]

    rods_stats,baits_stats = db.get_stats(user_id)
    if rods_stats:
        favorite_rod = max(rods_stats, key=rods_stats.get)
    else:
        favorite_rod = "нет"
    if baits_stats:
        favorite_bait = max(baits_stats, key=baits_stats.get)
    else:
        favorite_bait = "нет"

    guild_str = "нет"
    guild_rank_str=""
    if guild_id is not None:
        g = db.get_guild(guild_id)
        if g and g["name"]:
            guild_str = g["name"]
            guild_rank_str = get_guild_membership_rank(user_id, guild_id, db)

    text = (
      "👤 О рыбаке:\n\n"
        f"📛 Имя: {nickname}\n"
        f"🏅 Уровень: {level}\n"
        f"🎖 Ранг: {rank}\n"
        f"⭐ Опыт: {experience}/{get_required_xp(level)}\n"
        f"⏳ Возраст вашего приключения: {age}\n"
        f"🎣 Любимая удочка: {favorite_rod}\n"
        f"🪱 Любимая наживка: {favorite_bait}\n"
    )

    bonus = db.get_bonus(user_id)
    if bonus:
        end_time = datetime.fromisoformat(bonus["bonus_end"])
        now = datetime.utcnow()
        diff = (end_time - now).total_seconds()
        if diff>0:
            remain = int(diff//60)
            b_name=bonus["bonus_name"]
            b_fs=bonus["bonus_fishing_speed"]
            b_gold=bonus["bonus_gold_percent"]
            b_xp=bonus["bonus_xp_percent"]
            text += f"\n🐾 Бонус: {b_name} ({remain} мин) (+{b_fs}% к скорости, +{b_xp}% к опыту, +{b_gold}% к золоту)"

    text += f"\n\n🛡️ Гильдия: {guild_str}"
    if guild_id is not None and guild_str!="нет":
        text += f"\n🔰 Ранг в гильдии: {guild_rank_str}"

    text += (
        f"\n\n💰 Всего золота заработано: {total_gold_earned}"
        f"\n🐟 Всего КГ рыбы поймано: {total_kg_caught}"
        "\n\nПродолжайте ловить, опознавать и продавать рыбу, чтобы расти в мастерстве!"
    )
    return text

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
        f"🌊 {user_nickname} подошёл к зеркальной глади озера. Лёгкий ветерок качает камыши, "
        "а над водой кружат стрекозы.\nЧто вы хотите сделать?"
    )

def get_inventory_text(user_id):
    u = db.get_user(user_id)
    inv = db.get_inventory(user_id)
    un = db.get_unidentified(user_id)
    gold = u[2]
    rod = u[7] if u[7] else "Бамбуковая удочка 🎣"
    rod_bonus = u[8] if u[8] else 0
    bait_name = u[9]
    bait_end = u[10]

    text = "🎒 Ваш инвентарь:\n\n"
    text += f"🎣 Удочка: {rod} (уменьшение времени на {rod_bonus}%)\n"
    if bait_name and bait_end:
        end_time = datetime.fromisoformat(bait_end)
        remaining = int((end_time - datetime.utcnow()).total_seconds()/60)
        if remaining > 0:
            text+=f"🪱 Наживка: {bait_name} (ещё {remaining} мин)\n"
        else:
            text+="🪱 Наживка: нет\n"
    else:
        text+="🪱 Наживка: нет\n"

    text+="\n"
    # Неопознанная рыба
    c=un['common']
    r=un['rare']
    l=un['legendary']
    if c>0:
        text+=f"• Неопознанные рыбы - {c}\n"
    if r>0:
        text+=f"• Неопознанные редкие рыбы - {r}\n"
    if l>0:
        text+=f"• Неопознанные легендарные рыбы - {l}\n"
    if c==0 and r==0 and l==0:
        text+="Нет неопознанной рыбы.\n"

    identified_fish = [(k,v) for k,v in inv.items() if v>0 and isinstance(k,tuple)]
    total_identified_weight = 0
    if identified_fish:
        text+="\nОпознанная рыба:\n"
        for (fname, w, rar), qty in identified_fish:
            total_w = w*qty
            text += f"• {fname} - вес: {w} КГ - {qty} шт. (итого {total_w} КГ)\n"
            total_identified_weight += total_w

        # После перечисления — показываем общий вес
        text += f"\nОбщий вес рыбы: {total_identified_weight} КГ"

    text += f"\n\n💰 Золото: {gold}"
    return text

async def set_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    nickname=update.message.text.strip()
    if len(nickname)>25:
        await update.message.reply_text("❌ Имя слишком длинное.")
        return ASK_NICKNAME
    if not re.match(r'^[A-Za-zА-Яа-яЁё\s]+$', nickname):
        await update.message.reply_text("❌ Только буквы и пробелы!")
        return ASK_NICKNAME
    db.update_user(user.id, nickname=nickname)
    await update.message.reply_text(f"✅ Теперь вы - {nickname}!\nДобро пожаловать!",
                                    reply_markup=main_menu_keyboard(user.id))
    return ConversationHandler.END

async def cancel_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    await update.message.reply_text("Отмена.",reply_markup=main_menu_keyboard(user.id))
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    db.get_user(user.id)
    logger.info(f"User {user.id} ({user.first_name}) started bot.")
    await update.message.reply_text(get_welcome_text(),
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton(BUTTON_START_FISHING)]], resize_keyboard=True)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.warning(f"Unknown command from user {update.effective_user.id}: {update.message.text}")

async def begin_fishing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    u=db.get_user(user.id)
    nickname = u[1]
    if not nickname:
        await update.message.reply_text(get_onboarding_text(),reply_markup=ReplyKeyboardRemove())
        return ASK_NICKNAME
    else:
        await update.message.reply_text("🌞 Отличная погода для рыбалки! Удачи!",
                                        reply_markup=main_menu_keyboard(user.id))
        return ConversationHandler.END

async def lake_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    u=db.get_user(user.id)
    name = u[1] if u[1] else user.first_name
    txt=get_lake_text(name)
    await update.message.reply_text(txt,reply_markup=ReplyKeyboardMarkup([
        [KeyboardButton(BUTTON_CATCH_FISH)],
        [KeyboardButton(BUTTON_UPDATE)],
        [KeyboardButton(BUTTON_GO_BACK)],
    ], resize_keyboard=True))

async def catch_fish_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    if "fishing" in context.user_data and context.user_data["fishing"]:
        await update.message.reply_text("Вы уже ждёте улова!")
        return
    u=db.get_user(user.id)
    current_rod_bonus = u[8] if u[8] else 0
    base_delay=random.randint(5,33)

    def apply_bonus_to_fishing_time(user_id, base_sec, db_):
        bonus = db_.get_bonus(user_id)
        delay=int(base_sec*(1-current_rod_bonus/100))
        if delay<1:
            delay=1
        if bonus:
            speed=bonus["bonus_fishing_speed"]
            if speed>0:
                dec=math.ceil(delay*(speed/100.0))
                delay=delay-dec
                if delay<1:
                    delay=1
        return delay

    delay=apply_bonus_to_fishing_time(user.id, base_delay, db)
    context.user_data["fishing"]={
        "end_time":datetime.utcnow()+timedelta(seconds=delay),
        "status":"fishing"
    }
    await update.message.reply_text(
        f"🎣 Забросили удочку... Подождите {delay} секунд.",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton(BUTTON_CATCH_FISH)],
            [KeyboardButton(BUTTON_UPDATE)],
            [KeyboardButton(BUTTON_GO_BACK)],
        ], resize_keyboard=True)
    )

async def update_fishing_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "fishing" not in context.user_data or not context.user_data["fishing"]:
        await update.message.reply_text("Вы сейчас не ловите рыбу.",reply_markup=main_menu_keyboard(update.effective_user.id))
        return
    fishing=context.user_data["fishing"]
    end=fishing["end_time"]
    now=datetime.utcnow()
    rem=(end-now).total_seconds()
    if rem>0:
        await update.message.reply_text(f"Рыбка ещё не попалась, осталось ~{int(rem)} сек.")
    else:
        fishing["status"]="ready_to_pull"
        await update.message.reply_text(
            "Кажется, что-то клюнуло! Тяните!",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton(BUTTON_PULL)],
                [KeyboardButton(BUTTON_GO_BACK)]
            ],resize_keyboard=True)
        )

async def pull_hook_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "fishing" not in context.user_data or not context.user_data["fishing"]:
        await update.message.reply_text("Сначала начните ловить.",
                                        reply_markup=main_menu_keyboard(update.effective_user.id))
        return
    fishing=context.user_data["fishing"]
    end=fishing["end_time"]
    now=datetime.utcnow()
    user=update.effective_user

    if now>=end and fishing["status"]=="ready_to_pull":
        u=db.get_user(user.id)
        bait_name=u[9]
        bait_end=u[10]
        if bait_name and bait_end:
            end_time=datetime.fromisoformat(bait_end)
            if end_time>datetime.utcnow():
                probs_str=u[11]
                import json
                if probs_str:
                    probs=json.loads(probs_str)
                else:
                    probs={"common":70,"rare":25,"legendary":5}
            else:
                probs={"common":70,"rare":25,"legendary":5}
        else:
            probs={"common":70,"rare":25,"legendary":5}

        r=random.randint(1,100)
        cumulative=0
        rarity_chosen=None
        for rarity in ["common","rare","legendary"]:
            cumulative+=probs[rarity]
            if r<=cumulative:
                rarity_chosen=rarity
                break

        if rarity_chosen=="common":
            ftype="Неопознанная рыба"
            xp=random.randint(1,3)
        elif rarity_chosen=="rare":
            ftype="Неопознанная редкая рыба"
            xp=random.randint(4,9)
        else:
            ftype="Неопознанная легендарная рыба"
            xp=random.randint(10,30)
        un=db.get_unidentified(user.id)
        un[rarity_chosen]+=1
        db.update_unidentified(user.id, common=un["common"],rare=un["rare"],legendary=un["legendary"])
        new_exp = u[3]+xp
        db.update_user(user.id, experience=new_exp)
        add_guild_exp(user.id, xp, db)

        rods_stats,baits_stats = db.get_stats(user.id)
        rod=u[7] if u[7] else "Бамбуковая удочка 🎣"
        bait=u[9] if u[9] else "Нет наживки"
        rods_stats[rod]=rods_stats.get(rod,0)+1
        baits_stats[bait]=baits_stats.get(bait,0)+1
        db.update_stats(user.id, rods_stats=rods_stats, baits_stats=baits_stats)

        lvl_up,n_lvl,g_reward=check_level_up(user.id)
        update_rank(user.id)
        msg=(f"🎉 Вы выудили {ftype} из глубин!\nОпыт +{xp} ⭐")
        if lvl_up:
            msg+=f"\nВаш уровень повышен до {n_lvl}!"
            if g_reward>0:
                msg+=f"\nВы получили дополнительно {g_reward} золота!"
        await update.message.reply_text(
            msg,
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton(BUTTON_CATCH_FISH)],
                [KeyboardButton(BUTTON_GO_BACK)]
            ],resize_keyboard=True)
        )
        context.user_data["fishing"]=None
    else:
        await update.message.reply_text(
            "Поторопились и сорвали рыбу!",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton(BUTTON_CATCH_FISH)],
                [KeyboardButton(BUTTON_GO_BACK)]
            ],resize_keyboard=True)
        )
        context.user_data["fishing"]=None

async def identify_fish_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    un=db.get_unidentified(user.id)
    if all(x==0 for x in un.values()):
        await update.message.reply_text(
            "Нет неопознанной рыбы.",
            reply_markup=ReplyKeyboardMarkup([
                [BUTTON_GO_BACK],
            ], resize_keyboard=True)
        )
        return
    inv=db.get_inventory(user.id)
    results=[]
    for rarity,count in un.items():
        for _ in range(count):
            prefix=random.choice(FISH_DATA[rarity]["prefixes"])
            fname=random.choice(FISH_DATA[rarity]["names"])
            w=random.randint(*FISH_DATA[rarity]["weight_range"])
            inv[(f"{prefix} {fname}",w,rarity)] = inv.get((f"{prefix} {fname}",w,rarity),0)+1
            u=db.get_user(user.id)
            db.update_user(user.id, total_kg_caught=u[13]+w)
            results.append(f"{prefix} {fname} - вес {w} КГ")

    db.update_inventory(user.id, inv)
    db.update_unidentified(user.id,0,0,0)
    msg="🔍 Вы с любопытством рассматриваете свой улов...\n" \
        "Теперь вы знаете, кто скрывался в глубинах:\n"+ "\n".join(results)
    await update.message.reply_text(
        msg,
        reply_markup=ReplyKeyboardMarkup([
            [BUTTON_GO_BACK]
        ],resize_keyboard=True)
    )

async def inventory_handler_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    txt=get_inventory_text(user.id)
    await update.message.reply_text(
        txt,
        reply_markup=ReplyKeyboardMarkup([
            [BUTTON_IDENTIFY_FISH],
            [BUTTON_GO_BACK],
        ], resize_keyboard=True)
    )

def get_shop_text(user_id):
    inv=db.get_inventory(user_id)
    identified = [(k,v) for k,v in inv.items() if v>0 and isinstance(k,tuple)]
    if not identified:
        return ("Кажется у вас закончилась рыба. Скорее идите поймайте и опознайте еще!",0)
    text="🏪 Добро пожаловать в магазин!\n\nВаша опознанная рыба:\n"
    total_weight=0
    for (fname,w,r),qty in identified:
        tw=w*qty
        text+=f"{fname} - {qty} шт. (Вес одного: {w} КГ, всего: {tw} КГ)\n"
        total_weight+=tw
    gold=int(total_weight*pi/4)
    text+=f"\nОбщий вес: {total_weight} КГ\n"
    text+=f"\nПродать всю рыбу за {gold} золота?"
    return (text,gold)

async def shop_handler_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    info,g=get_shop_text(user.id)
    context.user_data["shop_gold"]=g
    await update.message.reply_text(
        info,
        reply_markup=ReplyKeyboardMarkup([
            [BUTTON_RODS, BUTTON_BAITS],
            [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
            [BUTTON_GO_BACK],
        ], resize_keyboard=True)
    )

async def sell_fish_handler_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    inv=db.get_inventory(user.id)
    identified=[(k,v) for k,v in inv.items() if v>0 and isinstance(k,tuple)]
    if not identified:
        await update.message.reply_text(
            "Нет опознанной рыбы для продажи.",
            reply_markup=ReplyKeyboardMarkup([
                [BUTTON_RODS, BUTTON_BAITS],
                [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                [BUTTON_GO_BACK],
            ], resize_keyboard=True)
        )
        return
    total_w=0
    for (fname,w,r),qty in identified:
        total_w+=w*qty
        inv[(fname,w,r)]=0
    db.update_inventory(user.id, inv)
    gold_earned=int(total_w*pi/4)
    u=db.get_user(user.id)
    db.update_user(user.id, gold=u[2]+gold_earned, total_gold_earned=u[12]+gold_earned)
    await update.message.reply_text(
        f"Вы продали всю опознанную рыбу за {gold_earned} золота!",
        reply_markup=ReplyKeyboardMarkup([
            [BUTTON_RODS, BUTTON_BAITS],
            [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
            [BUTTON_GO_BACK],
        ], resize_keyboard=True)
    )

async def exchange_gold_handler_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    u=db.get_user(user.id)
    gold=u[2]
    if gold>=25000:
        keyboard=[[BUTTON_CONFIRM_YES,BUTTON_CONFIRM_NO]]
        await update.message.reply_text(
            "Хотите обменять 25000 золота на TON?",
            reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True)
        )
        return EXCHANGE
    else:
        need=25000-gold
        await update.message.reply_text(
            f"Не хватает {need} золота для обмена.",
            reply_markup=ReplyKeyboardMarkup([
                [BUTTON_RODS, BUTTON_BAITS],
                [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                [BUTTON_GO_BACK],
            ], resize_keyboard=True)
        )

async def confirm_exchange_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    u=db.get_user(user.id)
    if update.message.text==BUTTON_CONFIRM_YES:
        if u[2]>=25000:
            db.update_user(user.id, gold=u[2]-25000)
            await update.message.reply_text(
                "Обмен совершен! Вы получили TON.",
                reply_markup=ReplyKeyboardMarkup([
                    [BUTTON_RODS, BUTTON_BAITS],
                    [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                    [BUTTON_GO_BACK],
                ], resize_keyboard=True)
            )
        else:
            need=25000-u[2]
            await update.message.reply_text(
                f"Не хватает {need} золота!",
                reply_markup=ReplyKeyboardMarkup([
                    [BUTTON_RODS, BUTTON_BAITS],
                    [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                    [BUTTON_GO_BACK],
                ], resize_keyboard=True)
            )
    else:
        await update.message.reply_text(
            "Обмен отменен.",
            reply_markup=ReplyKeyboardMarkup([
                [BUTTON_RODS, BUTTON_BAITS],
                [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                [BUTTON_GO_BACK],
            ], resize_keyboard=True)
        )
    return ConversationHandler.END

async def about_fisherman_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    txt=get_about_fisherman_text(user.id)
    await update.message.reply_text(
        txt,
        reply_markup=ReplyKeyboardMarkup([[BUTTON_GO_BACK]], resize_keyboard=True)
    )

async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    await update.message.reply_text(
        "Возвращаемся...",
        reply_markup=main_menu_keyboard(user.id)
    )
    return ConversationHandler.END

async def leaderboard_handler_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выберите категорию рейтинга:",
        reply_markup=ReplyKeyboardMarkup([
            [BUTTON_TOTAL_GOLD, BUTTON_TOTAL_KG],
            [BUTTON_TOTAL_EXPERIENCE],
            [BUTTON_GO_BACK],
        ], resize_keyboard=True)
    )
    return LEADERBOARD_CATEGORY

async def leaderboard_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text=update.message.text
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    c=conn.cursor()
    c.execute("SELECT user_id,nickname,gold,experience,total_gold_earned,total_kg_caught FROM users")
    rows=c.fetchall()
    conn.close()
    all_users=rows

    if text==BUTTON_TOTAL_GOLD:
        all_users.sort(key=lambda x:x[4],reverse=True)
        cat="золоту"
        val=lambda d:d[4]
    elif text==BUTTON_TOTAL_KG:
        all_users.sort(key=lambda x:x[5],reverse=True)
        cat="улову"
        val=lambda d:d[5]
    elif text==BUTTON_TOTAL_EXPERIENCE:
        all_users.sort(key=lambda x:x[3],reverse=True)
        cat="опыту"
        val=lambda d:d[3]
    else:
        await go_back(update, context)
        return ConversationHandler.END

    msg=f"🏆 Топ по {cat}:\n"
    top=all_users[:10]
    i=1
    for data in top:
        name=data[1] if data[1] else "Неизвестный рыбак"
        msg+=f"{i}. {name} - {val(data)}\n"
        i+=1
    await update.message.reply_text(
        msg,
        reply_markup=ReplyKeyboardMarkup([
            [BUTTON_TOTAL_GOLD, BUTTON_TOTAL_KG],
            [BUTTON_TOTAL_EXPERIENCE],
            [BUTTON_GO_BACK],
        ], resize_keyboard=True)
    )
    return LEADERBOARD_CATEGORY

async def rods_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text="🎣 Удочки в продаже:\n"
    for rod in RODS:
        text+=f"{rod['name']} - {rod['price']} золота (уменьшение времени на {rod['bonus_percent']}%)\n"
    text+="Выберите удочку для покупки или вернитесь назад."
    keyboard=[[KeyboardButton(r["name"])] for r in RODS]
    keyboard.append([BUTTON_GO_BACK])
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True)
    )
    return BUY_ROD

async def buy_rod_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    rod_name=update.message.text.strip()
    if rod_name==BUTTON_GO_BACK:
        await update.message.reply_text(
            "Возвращаемся в магазин.",
            reply_markup=ReplyKeyboardMarkup([
                [BUTTON_RODS, BUTTON_BAITS],
                [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                [BUTTON_GO_BACK],
            ], resize_keyboard=True)
        )
        return ConversationHandler.END
    rod=next((r for r in RODS if r["name"]==rod_name),None)
    if rod:
        context.user_data["pending_rod"]=rod
        keyboard=[[BUTTON_CONFIRM_YES,BUTTON_CONFIRM_NO]]
        await update.message.reply_text(
            f"Купить {rod['name']} за {rod['price']} золота?\nЭто улучшит скорость ловли на {rod['bonus_percent']}%.",
            reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True)
        )
        return CONFIRM_BUY_ROD
    else:
        await update.message.reply_text(
            "Неизвестная удочка.",
            reply_markup=ReplyKeyboardMarkup([
                [BUTTON_RODS, BUTTON_BAITS],
                [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                [BUTTON_GO_BACK],
            ], resize_keyboard=True)
        )
        return ConversationHandler.END

async def confirm_buy_rod_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    u=db.get_user(user.id)
    rod=context.user_data.get("pending_rod")
    if not rod:
        await update.message.reply_text(
            "Ошибка: нет выбранной удочки.",
            reply_markup=ReplyKeyboardMarkup([
                [BUTTON_RODS, BUTTON_BAITS],
                [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                [BUTTON_GO_BACK],
            ], resize_keyboard=True)
        )
        return ConversationHandler.END
    if update.message.text==BUTTON_CONFIRM_YES:
        gold=u[2]
        if gold>=rod["price"]:
            gold-=rod["price"]
            db.update_user(user.id, gold=gold, current_rod_name=rod["name"], current_rod_bonus=rod["bonus_percent"])
            await update.message.reply_text(
                f"Поздравляем! Теперь у вас {rod['name']}!",
                reply_markup=ReplyKeyboardMarkup([
                    [BUTTON_RODS, BUTTON_BAITS],
                    [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                    [BUTTON_GO_BACK],
                ], resize_keyboard=True)
            )
        else:
            need=rod["price"]-gold
            await update.message.reply_text(
                f"Недостаточно золота! Не хватает {need}.",
                reply_markup=ReplyKeyboardMarkup([
                    [BUTTON_RODS, BUTTON_BAITS],
                    [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                    [BUTTON_GO_BACK],
                ], resize_keyboard=True)
            )
    else:
        await update.message.reply_text(
            "Покупка отменена.",
            reply_markup=ReplyKeyboardMarkup([
                [BUTTON_RODS, BUTTON_BAITS],
                [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                [BUTTON_GO_BACK],
            ], resize_keyboard=True)
        )
    context.user_data.pop("pending_rod",None)
    return ConversationHandler.END

async def baits_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text="🪱 Наживки в продаже:\n"
    for b in BAITS:
        text+=f"{b['name']} - {b['price']} золота\n"
    text+="Выберите наживку или вернитесь назад."
    keyboard=[[KeyboardButton(b["name"])] for b in BAITS]
    keyboard.append([BUTTON_GO_BACK])
    await update.message.reply_text(text,reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True))
    return BUY_BAIT

async def buy_bait_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    bait_name=update.message.text.strip()
    if bait_name==BUTTON_GO_BACK:
        await update.message.reply_text(
            "Возвращаемся в магазин.",
            reply_markup=ReplyKeyboardMarkup([
                [BUTTON_RODS, BUTTON_BAITS],
                [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                [BUTTON_GO_BACK],
            ], resize_keyboard=True)
        )
        return ConversationHandler.END
    bait=next((x for x in BAITS if x["name"]==bait_name),None)
    if bait:
        context.user_data["pending_bait"]=bait
        keyboard=[[BUTTON_CONFIRM_YES,BUTTON_CONFIRM_NO]]
        await update.message.reply_text(
            f"Купить {bait['name']} за {bait['price']} золота?\nЭто может изменить ваши шансы поймать редкую или легендарную рыбу!",
            reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True)
        )
        return CONFIRM_BUY_BAIT
    else:
        await update.message.reply_text(
            "Неизвестная наживка.",
            reply_markup=ReplyKeyboardMarkup([
                [BUTTON_RODS, BUTTON_BAITS],
                [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                [BUTTON_GO_BACK],
            ], resize_keyboard=True)
        )
        return ConversationHandler.END

async def confirm_buy_bait_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    bait=context.user_data.get("pending_bait")
    if not bait:
        await update.message.reply_text(
            "Ошибка: нет выбранной наживки.",
            reply_markup=ReplyKeyboardMarkup([
                [BUTTON_RODS, BUTTON_BAITS],
                [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                [BUTTON_GO_BACK],
            ], resize_keyboard=True)
        )
        return ConversationHandler.END
    u=db.get_user(user.id)
    gold=u[2]
    if update.message.text==BUTTON_CONFIRM_YES:
        if gold>=bait["price"]:
            gold-=bait["price"]
            end_time = datetime.utcnow()+bait["duration"]
            import json
            db.update_user(user.id, gold=gold, current_bait_name=bait["name"],
                           current_bait_end=end_time.isoformat(),
                           current_bait_probs=json.dumps(bait["probabilities"]))
            await update.message.reply_text(
                f"Вы купили {bait['name']}! Теперь ваши шансы могут измениться!",
                reply_markup=ReplyKeyboardMarkup([
                    [BUTTON_RODS, BUTTON_BAITS],
                    [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                    [BUTTON_GO_BACK],
                ], resize_keyboard=True)
            )
        else:
            need=bait["price"]-gold
            await update.message.reply_text(
                f"Недостаточно золота! Не хватает {need}.",
                reply_markup=ReplyKeyboardMarkup([
                    [BUTTON_RODS, BUTTON_BAITS],
                    [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                    [BUTTON_GO_BACK],
                ], resize_keyboard=True)
            )
    else:
        await update.message.reply_text(
            "Покупка наживки отменена.",
            reply_markup=ReplyKeyboardMarkup([
                [BUTTON_RODS, BUTTON_BAITS],
                [BUTTON_SELL_ALL, BUTTON_EXCHANGE_GOLD],
                [BUTTON_GO_BACK],
            ], resize_keyboard=True)
        )
    context.user_data.pop("pending_bait",None)
    return ConversationHandler.END

async def universal_go_back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    await update.message.reply_text("Возвращаемся...",reply_markup=main_menu_keyboard(user.id))

def help_text(topic):
    if topic == BUTTON_HELP_FISHING:
        return (
            "Рыбалка - ваш путь к улову. Нажмите «Ловить рыбку», подождите, пока клюнет, и тяните рыбу! "
            "Неопознанную рыбу опознавайте в инвентаре, затем продавайте в магазине."
        )
    elif topic == BUTTON_HELP_RODS:
        return (
            "Удочки влияют на скорость ловли. Чем лучше удочка, тем меньше ждать. "
            "Покупайте удочки в магазине!"
        )
    elif topic == BUTTON_HELP_BAITS:
        return (
            "Наживка увеличивает шансы поймать редкую или легендарную рыбу. Купите и активируйте!"
        )
    elif topic == BUTTON_HELP_SHOP:
        return (
            "В магазине продавайте опознанную рыбу за золото, покупайте удочки, наживки "
            "и меняйте золото на TON."
        )
    elif topic == BUTTON_HELP_GUILDS:
        return (
            "Гильдии — объединения рыбаков. Вступайте, повышайте уровень гильдии, "
            "получайте бонусы и особые товары!"
        )
    elif topic == BUTTON_HELP_ABOUT:
        return (
            "'О рыбаке' показывает вашу статистику, уровень, опыт, любимые инструменты и гильдию."
        )
    return "Нет информации."

async def help_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton(BUTTON_HELP_FISHING), KeyboardButton(BUTTON_HELP_RODS)],
        [KeyboardButton(BUTTON_HELP_BAITS), KeyboardButton(BUTTON_HELP_SHOP)],
        [KeyboardButton(BUTTON_HELP_GUILDS), KeyboardButton(BUTTON_HELP_ABOUT)],
        [KeyboardButton(BUTTON_GO_BACK)]
    ]
    await update.message.reply_text("Что хотите узнать?",reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return HELP_MENU

async def help_subtopic_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic=update.message.text
    if topic==BUTTON_GO_BACK:
        await update.message.reply_text("Возвращаемся в меню помощи...",reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton(BUTTON_HELP_FISHING), KeyboardButton(BUTTON_HELP_RODS)],
            [KeyboardButton(BUTTON_HELP_BAITS), KeyboardButton(BUTTON_HELP_SHOP)],
            [KeyboardButton(BUTTON_HELP_GUILDS), KeyboardButton(BUTTON_HELP_ABOUT)],
            [KeyboardButton(BUTTON_GO_BACK)]
        ], resize_keyboard=True))
        return HELP_MENU
    txt=help_text(topic)
    await update.message.reply_text(
        txt,
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton(BUTTON_GO_BACK)]],resize_keyboard=True)
    )
    return HELP_SUBTOPIC

async def help_go_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    await update.message.reply_text("Возвращаемся в главное меню...",reply_markup=main_menu_keyboard(user.id))
    return ConversationHandler.END

def main():
    global db
    db = Database()

    token = "7646871331:AAHmQunhNsmblkFQsAzYLee3ko5-nOo62iA"
    application = ApplicationBuilder().token(token).build()

    application.bot_data["db"] = db
    application.bot_data["FISH_DATA"] = FISH_DATA

    help_conv_handler=ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{re.escape(BUTTON_HELP)}$"), help_main_menu)],
        states={
            HELP_MENU:[
                MessageHandler(filters.Regex(f"^{re.escape(BUTTON_HELP_FISHING)}$|^{re.escape(BUTTON_HELP_RODS)}$|^{re.escape(BUTTON_HELP_BAITS)}$|^{re.escape(BUTTON_HELP_SHOP)}$|^{re.escape(BUTTON_HELP_GUILDS)}$|^{re.escape(BUTTON_HELP_ABOUT)}$"), help_subtopic_handler),
                MessageHandler(filters.Regex(f"^{re.escape(BUTTON_GO_BACK)}$"), help_go_back_to_main),
            ],
            HELP_SUBTOPIC:[
                MessageHandler(filters.Regex(f"^{re.escape(BUTTON_GO_BACK)}$"), help_main_menu)
            ]
        },
        fallbacks=[MessageHandler(filters.Regex(f"^{re.escape(BUTTON_GO_BACK)}$"), help_go_back_to_main)],
        allow_reentry=True
    )

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{re.escape(BUTTON_START_FISHING)}$"), begin_fishing),
            MessageHandler(filters.Regex(f"^{re.escape(BUTTON_RODS)}$"), rods_section),
            MessageHandler(filters.Regex(f"^{re.escape(BUTTON_BAITS)}$"), baits_section),
            MessageHandler(filters.Regex(f"^{re.escape(BUTTON_EXCHANGE_GOLD)}$"), exchange_gold_handler_func),
            MessageHandler(filters.Regex(f"^{re.escape(BUTTON_LEADERBOARD)}$"), leaderboard_handler_func)
        ],
        states={
            ASK_NICKNAME:[MessageHandler((filters.TEXT & ~filters.COMMAND),set_nickname)],
            BUY_ROD:[MessageHandler((filters.TEXT & ~filters.COMMAND),buy_rod_handler)],
            CONFIRM_BUY_ROD:[MessageHandler(filters.Regex(f"^{BUTTON_CONFIRM_YES}$|^{BUTTON_CONFIRM_NO}$"),confirm_buy_rod_handler)],
            BUY_BAIT:[MessageHandler((filters.TEXT & ~filters.COMMAND),buy_bait_handler)],
            CONFIRM_BUY_BAIT:[MessageHandler(filters.Regex(f"^{BUTTON_CONFIRM_YES}$|^{BUTTON_CONFIRM_NO}$"),confirm_buy_bait_handler)],
            EXCHANGE:[MessageHandler(filters.Regex(f"^{BUTTON_CONFIRM_YES}$|^{BUTTON_CONFIRM_NO}$"),confirm_exchange_handler)],
            LEADERBOARD_CATEGORY:[
                MessageHandler(filters.Regex(f"^{re.escape(BUTTON_TOTAL_GOLD)}$|^{re.escape(BUTTON_TOTAL_KG)}$|^{re.escape(BUTTON_TOTAL_EXPERIENCE)}$"),leaderboard_show),
                MessageHandler(filters.Regex(f"^{re.escape(BUTTON_GO_BACK)}$"), go_back)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(f"^{re.escape(BUTTON_GO_BACK)}$"), go_back),
            CommandHandler("cancel", cancel_nickname)
        ],
        allow_reentry=True
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(guild_conversation_handler())
    application.add_handler(conv_handler)
    application.add_handler(help_conv_handler)
    application.add_handler(quests_conversation_handler())

    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BUTTON_LAKE)}$"), lake_handler))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BUTTON_INVENTORY)}$"), inventory_handler_func))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BUTTON_SHOP)}$"), shop_handler_func))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BUTTON_ABOUT_FISHERMAN)}$"), about_fisherman_handler))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BUTTON_CATCH_FISH)}$"), catch_fish_handler))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BUTTON_UPDATE)}$"), update_fishing_status_handler))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BUTTON_PULL)}$"), pull_hook_handler))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BUTTON_IDENTIFY_FISH)}$"), identify_fish_handler))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BUTTON_SELL_ALL)}$"), sell_fish_handler_func))

    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BUTTON_GO_BACK)}$"), universal_go_back_handler))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__=="__main__":
    main()
