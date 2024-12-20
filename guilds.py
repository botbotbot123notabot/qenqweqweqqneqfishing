import logging
from datetime import datetime, timedelta
from collections import defaultdict
import re

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

logger = logging.getLogger(__name__)

BUTTON_GUILDS = "🛡️ Гильдии"
BUTTON_MY_GUILD = "🛡️ Моя Гильдия"
BUTTON_CREATE_GUILD = "🛡️ Создать гильдию"
BUTTON_JOIN_GUILD = "🛡️ Вступить в гильдию"
BUTTON_GUILD_SHOP = "🛍️ Гильдейский Магазин"
BUTTON_GUILD_LEADERS = "🏆 Лидеры Гильдии"
BUTTON_LEAVE_GUILD = "🚪 Покинуть Гильдию"
BUTTON_GUILD_MEMBERS = "👥 Участники"
BUTTON_GUILD_BACK = "🔙 Назад в гильдию"

BUTTON_GUILD_LEADERS_GOLD = "💰 Всего заработано золота"
BUTTON_GUILD_LEADERS_KG = "🐟 Всего поймано КГ рыбы"
BUTTON_GUILD_LEADERS_EXP = "⭐ Всего опыта"
BUTTON_GUILD_LEADERS_BACK = "🔙 Назад"

BUTTON_GO_BACK = "🔙 Вернуться"

ASK_GUILD_NAME = 100
CONFIRM_CREATE_GUILD = 101
GUILD_MENU = 102
GUILD_LIST = 103
GUILD_CONFIRM_JOIN = 104
GUILD_SHOP_MENU = 105
GUILD_SHOP_CONFIRM = 106
GUILD_LEADERS_MENU = 107
GUILD_LEAVE_CONFIRM = 108
GUILD_MEMBERS_MENU = 109
GUILD_LEADERS_CATEGORY = 110

guilds_data = defaultdict(lambda: {
    "name": None,
    "level": 0,
    "experience": 0,
    "members": set(),
    "leader_id": None,
    "created_time": datetime.utcnow(),
})

GUILD_LEVELS = {
    1: 27000,
    2: 108000,
    3: 324000,
    4: 810000,
    5: 1890000,
    6: 4050000,
    7: 8100000,
}

GUILD_BONUSES = {
    0: (0,0),
    1: (5,5),
    2: (10,10),
    3: (15,15),
    4: (20,20),
    5: (25,25),
    6: (30,30),
    7: (33,33)
}

GUILD_RODS = [
    {"name": "Деревянная удочка", "price": 1000, "bonus_percent": 55, "required_level": 0},
    {"name": "Резная удочка", "price": 2000, "bonus_percent": 70, "required_level": 2},
    {"name": "Бесподобная удочка", "price": 5000, "bonus_percent": 80, "required_level": 5},
]

GUILD_BAITS = [
    {
        "name": "Майский жук",
        "price": 50,
        "duration": 60,
        "probabilities": {"common":40,"rare":57,"legendary":3},
        "required_level":1
    },
    {
        "name": "Вяленая рыба",
        "price":300,
        "duration":60,
        "probabilities":{"common":40,"rare":54,"legendary":6},
        "required_level":3
    },
    {
        "name":"Робо-наживка",
        "price":2000,
        "duration":60,
        "probabilities":{"common":30,"rare":73,"legendary":7},
        "required_level":5
    },
]

def get_guild_membership_rank(uid, gid, users_data):
    g=guilds_data[gid]
    if g["leader_id"]==uid:
        return "Глава гильдии"
    ud=users_data[uid]
    join_time=ud.get("guild_join_time")
    if not join_time:
        return "Новичок гильдии"
    delta=datetime.utcnow()-join_time
    hours=delta.total_seconds()/3600
    if hours<1:
        return "Новичок гильдии"
    elif hours<24:
        return "Член гильдии"
    elif 24<=hours<48:
        return "Хранитель крючков"
    elif 48<=hours<72:
        return "Сторож пруда"
    elif 72<=hours<96:
        return "Страж устья"
    days=delta.days
    if days>=30:
        return "Гильдейский ветеран"
    return "Член гильдии"

def calculate_guild_rating(gid, users_data):
    g = guilds_data[gid]
    total_gold=0
    total_kg=0
    total_exp=0
    for uid in g["members"]:
        ud=users_data[uid]
        total_gold+=ud["total_gold_earned"]
        total_kg+=ud["total_kg_caught"]
        total_exp+=ud["experience"]
    rating=(total_gold+total_kg+total_exp)*(1+(g["level"]*0.1))
    return int(rating)

def check_guild_level_up(g):
    current_level=g["level"]
    while current_level<7:
        required=GUILD_LEVELS[current_level+1]
        if g["experience"]>=required:
            g["level"]+=1
            current_level=g["level"]
            logger.info(f"Guild {g['name']} reached level {current_level}")
        else:
            break

def add_guild_exp(uid, player_exp, users_data):
    ud=users_data[uid]
    gid=ud.get("guild_id")
    if gid is None:
        return
    g=guilds_data[gid]
    n=len(g["members"])
    guild_exp_contribution = int(player_exp*100/(n+10))
    g["experience"]+=guild_exp_contribution
    check_guild_level_up(g)

def guild_main_menu_keyboard(user_id, users_data):
    ud = users_data[user_id]
    if ud.get("guild_id") is None:
        return ReplyKeyboardMarkup([
            [KeyboardButton(BUTTON_CREATE_GUILD)],
            [KeyboardButton(BUTTON_JOIN_GUILD)],
            [KeyboardButton(BUTTON_GO_BACK)]
        ], resize_keyboard=True)
    else:
        return ReplyKeyboardMarkup([
            [KeyboardButton(BUTTON_GUILD_SHOP), KeyboardButton(BUTTON_GUILD_LEADERS)],
            [KeyboardButton(BUTTON_GUILD_MEMBERS), KeyboardButton(BUTTON_LEAVE_GUILD)],
            [KeyboardButton(BUTTON_GO_BACK)]
        ], resize_keyboard=True)

def guild_info_text(gid, users_data):
    g=guilds_data[gid]
    guild_name=g["name"]
    lvl=g["level"]
    exp=g["experience"]
    rating=calculate_guild_rating(gid,users_data)
    if lvl<7:
        required=GUILD_LEVELS[lvl+1]
        left=required-exp
    else:
        left=0
    exp_bonus,gold_bonus=GUILD_BONUSES.get(lvl,(0,0))
    if exp_bonus==0 and gold_bonus==0:
        bonuses="нет"
    else:
        bonuses=f"Опыт: +{exp_bonus}%, Золото: +{gold_bonus}%"

    members_count=len(g["members"])
    leader_id=g["leader_id"]
    leader_name=users_data[leader_id]["nickname"] if leader_id else "нет"
    delta=datetime.utcnow()-g["created_time"]
    days=delta.days
    hours=(delta.seconds//3600)

    text=(
        f"🛡️ Добро пожаловать на поляну гильдии {guild_name}!\n\n"
        f"🏅 Уровень гильдии: {lvl}\n"
        f"⭐ Опыт гильдии: {exp} (осталось {left} до следующего уровня)\n"
        f"🎖 Рейтинг гильдии: {rating}\n"
        f"💫 Текущие бонусы гильдии: {bonuses}\n\n"
        f"👥 Количество участников гильдии: {members_count}\n"
        f"👑 Глава гильдии: {leader_name}\n"
        f"⏳ Возраст гильдии: {days} дней {hours} часов\n"
    )
    return text

async def guilds_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    global_users_data=context.application.bot_data["global_users_data"]
    ud=global_users_data[user.id]
    gid=ud.get("guild_id")
    if gid is None or guilds_data[gid]["name"] is None:
        await update.message.reply_text(
            "У вас нет гильдии. Создайте или вступите в существующую.",
            reply_markup=guild_main_menu_keyboard(user.id,global_users_data)
        )
    else:
        text=guild_info_text(gid, global_users_data)
        await update.message.reply_text(
            text,
            reply_markup=guild_main_menu_keyboard(user.id,global_users_data)
        )
    return GUILD_MENU

async def create_guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите название гильдии (до 25 символов):",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton(BUTTON_GO_BACK)]],resize_keyboard=True)
    )
    return ASK_GUILD_NAME

async def set_guild_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guild_name = update.message.text.strip()
    if len(guild_name)>25:
        await update.message.reply_text("Название слишком длинное.")
        return ASK_GUILD_NAME
    if not re.match(r'^[A-Za-zА-Яа-яЁё\s]+$', guild_name):
        await update.message.reply_text("Только буквы и пробелы!")
        return ASK_GUILD_NAME
    global_users_data=context.application.bot_data["global_users_data"]
    existing=[g["name"] for g in guilds_data.values() if g["name"]]
    if guild_name in existing:
        await update.message.reply_text("Гильдия с таким названием уже есть.")
        return ASK_GUILD_NAME
    context.user_data["new_guild_name"]=guild_name
    await update.message.reply_text(
        f"Создать гильдию '{guild_name}' за 1 золота?",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("✅ Да"),KeyboardButton("❌ Нет")]],resize_keyboard=True)
    )
    return CONFIRM_CREATE_GUILD

async def confirm_create_guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    global_users_data=context.application.bot_data["global_users_data"]
    ud=global_users_data[user.id]
    guild_name=context.user_data["new_guild_name"]
    if update.message.text=="✅ Да":
        if ud["gold"]<1:
            await update.message.reply_text("Недостаточно золота!",reply_markup=guild_main_menu_keyboard(user.id,global_users_data))
            return GUILD_MENU
        new_id=len(guilds_data)+1
        guilds_data[new_id]["name"]=guild_name
        guilds_data[new_id]["level"]=0
        guilds_data[new_id]["experience"]=0
        guilds_data[new_id]["members"]=set([user.id])
        guilds_data[new_id]["leader_id"]=user.id
        guilds_data[new_id]["created_time"]=datetime.utcnow()
        ud["guild_id"]=new_id
        ud["guild_join_time"]=datetime.utcnow()
        ud["gold"]-=1
        text=guild_info_text(new_id, global_users_data)
        await update.message.reply_text(
            text,
            reply_markup=guild_main_menu_keyboard(user.id,global_users_data)
        )
        return GUILD_MENU
    else:
        await update.message.reply_text("Создание отменено.",reply_markup=guild_main_menu_keyboard(user.id,global_users_data))
        return GUILD_MENU

async def join_guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_g=[(gid,g) for gid,g in guilds_data.items() if g["name"]]
    global_users_data=context.application.bot_data["global_users_data"]
    if not all_g:
        await update.message.reply_text("Нет доступных гильдий.",
                                        reply_markup=guild_main_menu_keyboard(update.effective_user.id,global_users_data))
        return GUILD_MENU
    text="Существующие гильдии:\n"
    for gid,g in all_g:
        text+=f"{g['name']} - {len(g['members'])} участников\n"
    text+="Выберите гильдию или вернитесь."
    keyboard=[[KeyboardButton(g["name"])] for gid,g in all_g]
    keyboard.append([KeyboardButton(BUTTON_GO_BACK)])
    await update.message.reply_text(text,reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True))
    return GUILD_LIST

async def select_guild_to_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guild_name=update.message.text.strip()
    user=update.effective_user
    global_users_data=context.application.bot_data["global_users_data"]
    ud=global_users_data[user.id]
    if guild_name==BUTTON_GO_BACK:
        # Возвращаемся - теперь по ТЗ при "Вернуться" с гильдии - главное меню.
        await update.message.reply_text("Возвращаемся...",
                                        reply_markup=ReplyKeyboardMarkup(
                                            [[KeyboardButton("🏞 Озеро"),KeyboardButton("📦 Инвентарь"),KeyboardButton("👤 О рыбаке")],
                                             [KeyboardButton("🏪 Магазин"),KeyboardButton("🏆 Таблица Лидеров"),KeyboardButton("🛡️ Гильдии")],
                                             [KeyboardButton("🔍 Помощь")]],
                                            resize_keyboard=True))
        return ConversationHandler.END
    for gid,g in guilds_data.items():
        if g["name"]==guild_name:
            context.user_data["join_guild_id"]=gid
            await update.message.reply_text(
                f"Вступить в '{guild_name}'?",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("✅ Да"),KeyboardButton("❌ Нет")]],resize_keyboard=True)
            )
            return GUILD_CONFIRM_JOIN
    await update.message.reply_text("Гильдия не найдена.")
    return GUILD_LIST

async def confirm_join_guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    global_users_data=context.application.bot_data["global_users_data"]
    ud=global_users_data[user.id]
    if update.message.text=="✅ Да":
        gid=context.user_data["join_guild_id"]
        g=guilds_data[gid]
        g["members"].add(user.id)
        ud["guild_id"]=gid
        ud["guild_join_time"]=datetime.utcnow()
        text=guild_info_text(gid, global_users_data)
        await update.message.reply_text(
            text,
            reply_markup=guild_main_menu_keyboard(user.id,global_users_data)
        )
        return GUILD_MENU
    else:
        await update.message.reply_text("Вступление отменено.",
                                        reply_markup=guild_main_menu_keyboard(user.id,global_users_data))
        return GUILD_MENU

async def leave_guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    global_users_data=context.application.bot_data["global_users_data"]
    ud=global_users_data[user.id]
    if ud.get("guild_id") is None:
        await update.message.reply_text("Вы не в гильдии.",
                                        reply_markup=guild_main_menu_keyboard(user.id,global_users_data))
        return GUILD_MENU
    gid=ud["guild_id"]
    g=guilds_data[gid]
    await update.message.reply_text(
        f"Покинуть гильдию '{g['name']}'?",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("✅ Да"),KeyboardButton("❌ Нет")]],resize_keyboard=True)
    )
    return GUILD_LEAVE_CONFIRM

async def confirm_leave_guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    global_users_data=context.application.bot_data["global_users_data"]
    ud=global_users_data[user.id]
    gid=ud.get("guild_id")
    if gid is None:
        await update.message.reply_text("Вы не в гильдии.",
                                        reply_markup=guild_main_menu_keyboard(user.id,global_users_data))
        return GUILD_MENU
    g=guilds_data[gid]
    if update.message.text=="✅ Да":
        g["members"].discard(user.id)
        if g["leader_id"]==user.id:
            if len(g["members"])>0:
                new_leader = next(iter(g["members"]))
                g["leader_id"]=new_leader
            else:
                g["name"]=None
        ud["guild_id"]=None
        ud.pop("guild_join_time",None)
        await update.message.reply_text("Вы покинули гильдию.",
                                        reply_markup=guild_main_menu_keyboard(user.id,global_users_data))
    else:
        await update.message.reply_text("Вы остались в гильдии.",
                                        reply_markup=guild_main_menu_keyboard(user.id,global_users_data))
    return GUILD_MENU

async def guild_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    global_users_data=context.application.bot_data["global_users_data"]
    ud=global_users_data[user.id]
    gid=ud.get("guild_id")
    if gid is None:
        await update.message.reply_text("У вас нет гильдии!",reply_markup=guild_main_menu_keyboard(user.id,global_users_data))
        return GUILD_MENU
    g=guilds_data[gid]
    guild_level=g["level"]
    guild_name=g["name"]

    text=f"🛍️ Гильдейский Магазин {guild_name}:\n\n"
    rods_available=[rod for rod in GUILD_RODS if guild_level>=rod["required_level"]]
    baits_available=[bait for bait in GUILD_BAITS if guild_level>=bait["required_level"]]

    if rods_available:
        text+="Удочки:\n"
        for rod in rods_available:
            text+=f"{rod['name']} {guild_name} - {rod['price']} золота (-{rod['bonus_percent']}% время)\n"
        text+="\n"
    if baits_available:
        text+="Наживки:\n"
        for bait in baits_available:
            text+=f"{bait['name']} - {bait['price']} золота (на {bait['duration']} мин.)\n"

    if not rods_available and not baits_available:
        text+="Здесь пока ничего нет для вашего уровня гильдии."

    text+="\nВыберите предмет или вернитесь."
    keyboard=[]
    for rod in rods_available:
        keyboard.append([KeyboardButton(f"{rod['name']} {guild_name}")])
    for bait in baits_available:
        keyboard.append([KeyboardButton(bait["name"])])

    keyboard.append([KeyboardButton(BUTTON_GUILD_BACK)])
    await update.message.reply_text(text,reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True))
    return GUILD_SHOP_MENU

async def guild_shop_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    item_name=update.message.text.strip()
    user=update.effective_user
    global_users_data=context.application.bot_data["global_users_data"]
    ud=global_users_data[user.id]
    gid=ud["guild_id"]
    g=guilds_data[gid]
    guild_name=g["name"]

    if item_name==BUTTON_GUILD_BACK:
        # Возвращает в меню гильдии
        # Но теперь при нажатии "Вернуться" с главной страницы гильдии уходим в главное меню
        # Мы реализуем это в другом месте, а здесь просто вернем к инфо о гильдии
        text=guild_info_text(gid, global_users_data)
        await update.message.reply_text(text,reply_markup=guild_main_menu_keyboard(user.id,global_users_data))
        return GUILD_MENU

    rods_available=[rod for rod in GUILD_RODS if g["level"]>=rod["required_level"]]
    baits_available=[bait for bait in GUILD_BAITS if g["level"]>=bait["required_level"]]

    chosen_item=None
    item_type=None
    for rod in rods_available:
        full_name=f"{rod['name']} {guild_name}"
        if full_name==item_name:
            chosen_item=rod
            item_type="rod"
            break
    if not chosen_item:
        for bait in baits_available:
            if bait["name"]==item_name:
                chosen_item=bait
                item_type="bait"
                break

    if not chosen_item:
        await update.message.reply_text("Неизвестный предмет.",
                                        reply_markup=ReplyKeyboardMarkup([[KeyboardButton(BUTTON_GUILD_BACK)]],resize_keyboard=True))
        return GUILD_SHOP_MENU

    if item_type=="rod":
        await update.message.reply_text(
            f"Купить {chosen_item['name']} {guild_name} за {chosen_item['price']} золота?",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("✅ Да"),KeyboardButton("❌ Нет")]],resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            f"Купить наживку {chosen_item['name']} за {chosen_item['price']} золота?",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("✅ Да"),KeyboardButton("❌ Нет")]],resize_keyboard=True)
        )
    context.user_data["guild_shop_item"]=chosen_item
    context.user_data["guild_shop_item_type"]=item_type
    return GUILD_SHOP_CONFIRM

async def guild_shop_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    global_users_data=context.application.bot_data["global_users_data"]
    ud=global_users_data[user.id]
    item=context.user_data["guild_shop_item"]
    item_type=context.user_data["guild_shop_item_type"]
    gid=ud["guild_id"]
    g=guilds_data[gid]
    guild_name=g["name"]

    if update.message.text=="✅ Да":
        if ud["gold"]>=item["price"]:
            ud["gold"]-=item["price"]
            if item_type=="rod":
                new_rod={
                    "name":f"{item['name']} {guild_name}",
                    "bonus_percent":item["bonus_percent"]
                }
                ud["current_rod"]=new_rod
                await update.message.reply_text(f"Вы купили {new_rod['name']}!",
                                                reply_markup=ReplyKeyboardMarkup([[KeyboardButton(BUTTON_GUILD_BACK)]],resize_keyboard=True))
            else:
                end_time = datetime.utcnow()+timedelta(minutes=item["duration"])
                ud["current_bait"]={
                    "name":item["name"],
                    "end_time":end_time,
                    "probabilities":item["probabilities"]
                }
                await update.message.reply_text(
                    f"Вы купили наживку {item['name']}!",
                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton(BUTTON_GUILD_BACK)]],resize_keyboard=True)
                )
        else:
            need=item["price"]-ud["gold"]
            await update.message.reply_text(f"Недостаточно золота! Не хватает {need}.",
                                            reply_markup=ReplyKeyboardMarkup([[KeyboardButton(BUTTON_GUILD_BACK)]],resize_keyboard=True))
    else:
        await update.message.reply_text("Покупка отменена.",
                                        reply_markup=ReplyKeyboardMarkup([[KeyboardButton(BUTTON_GUILD_BACK)]],resize_keyboard=True))
    context.user_data.pop("guild_shop_item",None)
    context.user_data.pop("guild_shop_item_type",None)
    return GUILD_SHOP_MENU

async def guild_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    global_users_data=context.application.bot_data["global_users_data"]
    ud=global_users_data[user.id]
    gid=ud.get("guild_id")
    if gid is None:
        await update.message.reply_text("Вы не в гильдии.",
                                        reply_markup=guild_main_menu_keyboard(user.id,global_users_data))
        return GUILD_MENU
    g=guilds_data[gid]
    members=list(g["members"])
    leader_id=g["leader_id"]
    members.remove(leader_id)
    members.sort(key=lambda x: global_users_data[x]["guild_join_time"] if global_users_data[x].get("guild_join_time") else datetime.utcnow())
    members=[leader_id]+members

    msg="Список участников гильдии:\n"
    for i,uid_ in enumerate(members,start=1):
        d=global_users_data[uid_]
        name=d["nickname"] if d["nickname"] else "Неизвестный"
        lvl=d["level"]
        guild_rank=get_guild_membership_rank(uid_,gid,global_users_data)
        msg+=f"{i}. {name} ({lvl} ур.) - {guild_rank}\n"
    keyboard=[[KeyboardButton(BUTTON_GUILD_BACK)]]
    await update.message.reply_text(msg,reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True))
    return GUILD_MEMBERS_MENU

async def not_implemented_leaders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    global_users_data=context.application.bot_data["global_users_data"]
    ud=global_users_data[user.id]
    gid=ud.get("guild_id")
    if gid is None:
        await update.message.reply_text("Вы не в гильдии.",
                                        reply_markup=guild_main_menu_keyboard(user.id,global_users_data))
        return GUILD_MENU
    keyboard=[
        [KeyboardButton(BUTTON_GUILD_LEADERS_GOLD),KeyboardButton(BUTTON_GUILD_LEADERS_KG)],
        [KeyboardButton(BUTTON_GUILD_LEADERS_EXP)],
        [KeyboardButton(BUTTON_GUILD_BACK)]
    ]
    await update.message.reply_text("Выберите категорию рейтинга внутри гильдии:",
                                    reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True))
    return GUILD_LEADERS_MENU

async def guild_leaders_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    global_users_data=context.application.bot_data["global_users_data"]
    ud=global_users_data[user.id]
    gid=ud["guild_id"]
    g=guilds_data[gid]

    text=update.message.text
    members=list(g["members"])
    if text==BUTTON_GUILD_LEADERS_GOLD:
        cat="золоту"
        members.sort(key=lambda x: global_users_data[x]["total_gold_earned"],reverse=True)
        get_val=lambda d: d["total_gold_earned"]
    elif text==BUTTON_GUILD_LEADERS_KG:
        cat="улову"
        members.sort(key=lambda x: global_users_data[x]["total_kg_caught"],reverse=True)
        get_val=lambda d: d["total_kg_caught"]
    elif text==BUTTON_GUILD_LEADERS_EXP:
        cat="опыту"
        members.sort(key=lambda x: global_users_data[x]["experience"],reverse=True)
        get_val=lambda d: d["experience"]
    elif text==BUTTON_GUILD_BACK:
        # Возвращаемся в главное меню гильдии
        text_=guild_info_text(gid,global_users_data)
        await update.message.reply_text(text_,reply_markup=guild_main_menu_keyboard(user.id,global_users_data))
        return GUILD_MENU
    else:
        text_=guild_info_text(gid,global_users_data)
        await update.message.reply_text(text_,reply_markup=guild_main_menu_keyboard(user.id,global_users_data))
        return GUILD_MENU

    msg=f"🏆 Топ по {cat} внутри гильдии:\n"
    for i,uid_ in enumerate(members[:10], start=1):
        d=global_users_data[uid_]
        name=d["nickname"] if d["nickname"] else "Неизвестный рыбак"
        lvl=d["level"]
        guild_rank=get_guild_membership_rank(uid_,gid,global_users_data)
        val=get_val(d)
        msg+=f"{i}. {name} ({lvl} ур.) - {guild_rank} - {val}\n"

    await update.message.reply_text(msg,reply_markup=ReplyKeyboardMarkup([[KeyboardButton(BUTTON_GUILD_BACK)]],resize_keyboard=True))
    return GUILD_LEADERS_MENU

async def go_back_guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # При нажатии "Вернуться" из гильдии - возвращаемся в главное меню.
    await update.message.reply_text("Возвращаемся...",
                                    reply_markup=ReplyKeyboardMarkup(
                                        [[KeyboardButton("🏞 Озеро"),KeyboardButton("📦 Инвентарь"),KeyboardButton("👤 О рыбаке")],
                                         [KeyboardButton("🏪 Магазин"),KeyboardButton("🏆 Таблица Лидеров"),KeyboardButton("🛡️ Гильдии")],
                                         [KeyboardButton("🔍 Помощь")]],
                                        resize_keyboard=True))
    return ConversationHandler.END

async def go_back_guild_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Аналогично, "Вернуться" возвращает в главное меню
    await update.message.reply_text("Возвращаемся...",
                                    reply_markup=ReplyKeyboardMarkup(
                                        [[KeyboardButton("🏞 Озеро"),KeyboardButton("📦 Инвентарь"),KeyboardButton("👤 О рыбаке")],
                                         [KeyboardButton("🏪 Магазин"),KeyboardButton("🏆 Таблица Лидеров"),KeyboardButton("🛡️ Гильдии")],
                                         [KeyboardButton("🔍 Помощь")]],
                                        resize_keyboard=True))
    return ConversationHandler.END

def guild_conversation_handler():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{BUTTON_GUILDS}$"), guilds_handler)],
        states={
            GUILD_MENU:[
                MessageHandler(filters.Regex("^"+re.escape(BUTTON_CREATE_GUILD)+"$"), create_guild),
                MessageHandler(filters.Regex("^"+re.escape(BUTTON_JOIN_GUILD)+"$"), join_guild),
                MessageHandler(filters.Regex("^"+re.escape(BUTTON_LEAVE_GUILD)+"$"), leave_guild),
                MessageHandler(filters.Regex("^"+re.escape(BUTTON_GUILD_SHOP)+"$"), guild_shop),
                MessageHandler(filters.Regex("^"+re.escape(BUTTON_GUILD_LEADERS)+"$"), not_implemented_leaders),
                MessageHandler(filters.Regex("^"+re.escape(BUTTON_GUILD_MEMBERS)+"$"), guild_members),
                MessageHandler(filters.Regex("^"+re.escape(BUTTON_GO_BACK)+"$"), go_back_guild),
            ],
            ASK_GUILD_NAME:[
                MessageHandler((filters.TEXT & ~filters.COMMAND), set_guild_name),
                MessageHandler(filters.Regex("^"+re.escape(BUTTON_GO_BACK)+"$"), go_back_guild)
            ],
            CONFIRM_CREATE_GUILD:[MessageHandler(filters.Regex("^✅ Да$|^❌ Нет$"), confirm_create_guild)],
            GUILD_LIST:[
                MessageHandler((filters.TEXT & ~filters.COMMAND), select_guild_to_join),
                MessageHandler(filters.Regex("^"+re.escape(BUTTON_GO_BACK)+"$"), go_back_guild)
            ],
            GUILD_CONFIRM_JOIN:[MessageHandler(filters.Regex("^✅ Да$|^❌ Нет$"), confirm_join_guild)],
            GUILD_LEAVE_CONFIRM:[MessageHandler(filters.Regex("^✅ Да$|^❌ Нет$"), confirm_leave_guild)],
            GUILD_SHOP_MENU:[
                MessageHandler(filters.Regex("^"+re.escape(BUTTON_GUILD_BACK)+"$"), go_back_guild),
                MessageHandler((filters.TEXT & ~filters.COMMAND), guild_shop_select)
            ],
            GUILD_SHOP_CONFIRM:[
                MessageHandler(filters.Regex("^✅ Да$|^❌ Нет$"), guild_shop_confirm)
            ],
            GUILD_MEMBERS_MENU:[
                MessageHandler(filters.Regex("^"+re.escape(BUTTON_GUILD_BACK)+"$"), go_back_guild_members)
            ],
            GUILD_LEADERS_MENU:[
                MessageHandler(filters.Regex("^"+re.escape(BUTTON_GUILD_LEADERS_GOLD)+"$|^"+re.escape(BUTTON_GUILD_LEADERS_KG)+"$|^"+re.escape(BUTTON_GUILD_LEADERS_EXP)+"$|^"+re.escape(BUTTON_GUILD_BACK)+"$"), guild_leaders_show),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^"+re.escape(BUTTON_GO_BACK)+"$"), go_back_guild)],
        allow_reentry=True
    )