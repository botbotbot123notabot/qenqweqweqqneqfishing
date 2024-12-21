import logging
import re
import sqlite3
from datetime import datetime
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
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
BUTTON_LEAVE_GUILD = "🚪 Покинуть Гильдию"
BUTTON_GUILD_SHOP = "🛍️ Гильдейский Магазин"
BUTTON_GUILD_LEADERS = "🏆 Лидеры Гильдии"
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

# Гильдейские предметы
GUILD_RODS = [
    {"name": "Деревянная удочка", "price": 1000, "bonus_percent": 55, "required_level": 0},
    {"name": "Резная удочка", "price": 2000, "bonus_percent": 70, "required_level": 2},
    {"name": "Бесподобная удочка", "price": 5000, "bonus_percent": 80, "required_level": 5},
]

GUILD_BAITS = [
    {
        "name": "Майский жук",
        "price": 50,
        "duration":60,
        "probabilities":{"common":40,"rare":57,"legendary":3},
        "required_level":1
    },
    {
        "name":"Вяленая рыба",
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

def get_guild_membership_rank(uid, gid, db):
    g=db.get_guild(gid)
    if g["leader_id"]==uid:
        return "Глава гильдии"
    user = db.get_user(uid)
    join_time=user[15]
    if not join_time:
        return "Новичок гильдии"
    join_dt = datetime.fromisoformat(join_time)
    delta=datetime.utcnow()-join_dt
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

def calculate_guild_rating(gid, db):
    g = db.get_guild(gid)
    members = db.get_guild_members(gid)
    total_gold=0
    total_kg=0
    total_exp=0
    for uid in members:
        u=db.get_user(uid)
        total_gold+=u[12]
        total_kg+=u[13]
        total_exp+=u[3]
    rating=(total_gold+total_kg+total_exp)*(1+(g["level"]*0.1))
    return int(rating)

def check_guild_level_up(g,db):
    current_level=g["level"]
    while current_level<7:
        required=GUILD_LEVELS[current_level+1]
        if g["experience"]>=required:
            current_level+=1
            db.update_guild(g["guild_id"], level=current_level)
            g["level"]=current_level
        else:
            break

def add_guild_exp(uid, player_exp, db):
    u=db.get_user(uid)
    gid=u[14]
    if gid is None:
        return
    g=db.get_guild(gid)
    n=len(db.get_guild_members(gid))
    guild_exp_contribution = int(player_exp*100/(n+10))
    new_exp = g["experience"]+guild_exp_contribution
    db.update_guild(gid, experience=new_exp)
    g["experience"]=new_exp
    check_guild_level_up(g,db)

def guild_main_menu_keyboard(user_id, db):
    u=db.get_user(user_id)
    gid=u[14]
    if gid is None:
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

def guild_info_text(gid, db):
    g=db.get_guild(gid)
    if not g or g["name"] is None:
        return "Гильдия не найдена или удалена."
    guild_name=g["name"]
    lvl=g["level"]
    exp=g["experience"]
    rating=calculate_guild_rating(gid,db)
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

    members_count=len(db.get_guild_members(gid))
    leader_id=g["leader_id"]
    leader_user=db.get_user(leader_id)
    leader_name=leader_user[1] if leader_user[1] else "нет"
    created_time=datetime.fromisoformat(g["created_time"])
    delta=datetime.utcnow()-created_time
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
    db=context.application.bot_data["db"]
    user=update.effective_user
    u=db.get_user(user.id)
    gid=u[14]
    if gid is None:
        await update.message.reply_text(
            "У вас нет гильдии. Создайте или вступите в существующую.",
            reply_markup=guild_main_menu_keyboard(user.id,db)
        )
    else:
        g= db.get_guild(gid)
        if g and g["name"] is not None:
            text=guild_info_text(gid, db)
        else:
            text="Гильдия удалена."
        await update.message.reply_text(
            text,
            reply_markup=guild_main_menu_keyboard(user.id,db)
        )
    return GUILD_MENU

async def create_guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Без кнопки "Вернуться"
    await update.message.reply_text(
        "Введите название гильдии (до 25 символов):",
        reply_markup=ReplyKeyboardRemove() 
    )
    return ASK_GUILD_NAME

async def set_guild_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=context.application.bot_data["db"]
    guild_name = update.message.text.strip()
    if len(guild_name)>25:
        await update.message.reply_text("Название слишком длинное.")
        return ASK_GUILD_NAME
    if not re.match(r'^[A-Za-zА-Яа-яЁё\s]+$', guild_name):
        await update.message.reply_text("Только буквы и пробелы!")
        return ASK_GUILD_NAME
    user=update.effective_user
    context.user_data["new_guild_name"]=guild_name
    await update.message.reply_text(
        f"Создать гильдию '{guild_name}' за 1 золота?",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("✅ Да"),KeyboardButton("❌ Нет")]],resize_keyboard=True)
    )
    return CONFIRM_CREATE_GUILD

async def confirm_create_guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=context.application.bot_data["db"]
    user=update.effective_user
    u=db.get_user(user.id)
    gold=u[2]
    guild_name=context.user_data["new_guild_name"]
    if update.message.text=="✅ Да":
        if gold<1:
            await update.message.reply_text("Недостаточно золота!",reply_markup=guild_main_menu_keyboard(user.id,db))
            return GUILD_MENU
        gid=db.create_guild(guild_name,user.id)
        db.update_user(user.id, gold=gold-1, guild_id=gid, guild_join_time=datetime.utcnow().isoformat())
        text=guild_info_text(gid, db)
        await update.message.reply_text(
            text,
            reply_markup=guild_main_menu_keyboard(user.id,db)
        )
        return GUILD_MENU
    else:
        await update.message.reply_text("Создание отменено.",reply_markup=guild_main_menu_keyboard(user.id,db))
        return GUILD_MENU

async def join_guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=context.application.bot_data["db"]
    conn = sqlite3.connect(db.db_path)
    c=conn.cursor()
    c.execute("SELECT guild_id,name FROM guilds WHERE name IS NOT NULL")
    all_g=c.fetchall()
    conn.close()

    user=update.effective_user
    if not all_g:
        await update.message.reply_text("Нет доступных гильдий.",
                                        reply_markup=guild_main_menu_keyboard(user.id,db))
        return GUILD_MENU
    text="Существующие гильдии:\n"
    for gid,name in all_g:
        members=db.get_guild_members(gid)
        text+=f"{name} - {len(members)} участников\n"
    text+="Выберите гильдию или введите что-то другое, чтобы отменить."
    keyboard=[[KeyboardButton(name)] for gid,name in all_g]
    keyboard.append([KeyboardButton(BUTTON_GO_BACK)])
    await update.message.reply_text(text,reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True))
    return GUILD_LIST

async def select_guild_to_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=context.application.bot_data["db"]
    guild_name=update.message.text.strip()
    user=update.effective_user
    if guild_name==BUTTON_GO_BACK:
        await update.message.reply_text("Возвращаемся...",
                                        reply_markup=ReplyKeyboardMarkup(
                                            [[KeyboardButton("🏞 Озеро"),KeyboardButton("📦 Инвентарь"),KeyboardButton("👤 О рыбаке")],
                                             [KeyboardButton("🏪 Магазин"),KeyboardButton("🏆 Таблица Лидеров"),KeyboardButton("🛡️ Гильдии")],
                                             [KeyboardButton("🔍 Помощь")]],
                                            resize_keyboard=True))
        return ConversationHandler.END
    conn = sqlite3.connect(db.db_path)
    c=conn.cursor()
    c.execute("SELECT guild_id FROM guilds WHERE name=?",(guild_name,))
    row=c.fetchone()
    conn.close()
    if row is None:
        await update.message.reply_text("Гильдия не найдена. Повторите ввод или вернитесь.",
                                        reply_markup=ReplyKeyboardMarkup([
                                            [KeyboardButton(BUTTON_GO_BACK)]],resize_keyboard=True))
        return GUILD_LIST
    gid=row[0]
    context.user_data["join_guild_id"]=gid
    await update.message.reply_text(
        f"Вступить в '{guild_name}'?",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("✅ Да"),KeyboardButton("❌ Нет")]],resize_keyboard=True)
    )
    return GUILD_CONFIRM_JOIN

async def confirm_join_guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=context.application.bot_data["db"]
    user=update.effective_user
    if update.message.text=="✅ Да":
        gid=context.user_data["join_guild_id"]
        db.add_guild_member(gid,user.id)
        now = datetime.utcnow().isoformat()
        db.update_user(user.id, guild_id=gid, guild_join_time=now)
        text=guild_info_text(gid, db)
        await update.message.reply_text(
            text,
            reply_markup=guild_main_menu_keyboard(user.id,db)
        )
        return GUILD_MENU
    else:
        await update.message.reply_text("Вступление отменено.",
                                        reply_markup=guild_main_menu_keyboard(user.id,db))
        return GUILD_MENU

async def leave_guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=context.application.bot_data["db"]
    user=update.effective_user
    u=db.get_user(user.id)
    gid=u[14]
    if gid is None:
        await update.message.reply_text("Вы не в гильдии.",
                                        reply_markup=guild_main_menu_keyboard(user.id,db))
        return GUILD_MENU
    g=db.get_guild(gid)
    await update.message.reply_text(
        f"Покинуть гильдию '{g['name']}'?",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("✅ Да"),KeyboardButton("❌ Нет")]],resize_keyboard=True)
    )
    return GUILD_LEAVE_CONFIRM

async def confirm_leave_guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=context.application.bot_data["db"]
    user=update.effective_user
    u=db.get_user(user.id)
    gid=u[14]
    if gid is None:
        await update.message.reply_text("Вы не в гильдии.",
                                        reply_markup=guild_main_menu_keyboard(user.id,db))
        return GUILD_MENU
    g=db.get_guild(gid)
    if update.message.text=="✅ Да":
        db.remove_guild_member(gid,user.id)
        if g["leader_id"]==user.id:
            members=db.get_guild_members(gid)
            if members:
                new_leader = members[0]
                db.update_guild(gid, leader_id=new_leader)
            else:
                db.update_guild(gid, name=None)
        db.update_user(user.id, guild_id=None, guild_join_time=None)
        await update.message.reply_text("Вы покинули гильдию.",
                                        reply_markup=guild_main_menu_keyboard(user.id,db))
    else:
        await update.message.reply_text("Вы остались в гильдии.",
                                        reply_markup=guild_main_menu_keyboard(user.id,db))
    return GUILD_MENU

async def guild_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=context.application.bot_data["db"]
    user=update.effective_user
    u=db.get_user(user.id)
    gid=u[14]
    if gid is None:
        await update.message.reply_text("У вас нет гильдии!",reply_markup=guild_main_menu_keyboard(user.id,db))
        return GUILD_MENU
    g=db.get_guild(gid)
    guild_level=g["level"]
    guild_name=g["name"]

    rods_available=[rod for rod in GUILD_RODS if guild_level>=rod["required_level"]]
    baits_available=[bait for bait in GUILD_BAITS if guild_level>=bait["required_level"]]

    text=f"🛍️ Гильдейский Магазин {guild_name}:\n\n"
    if rods_available:
        text+="Удочки:\n"
        for rod in rods_available:
            text+=f"{rod['name']} - {rod['price']} золота (-{rod['bonus_percent']}% время)\n"
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
        keyboard.append([KeyboardButton(rod["name"])])
    for bait in baits_available:
        keyboard.append([KeyboardButton(bait["name"])])

    keyboard.append([KeyboardButton(BUTTON_GUILD_BACK)])
    await update.message.reply_text(text,reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True))
    return GUILD_SHOP_MENU

async def guild_shop_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=context.application.bot_data["db"]
    user=update.effective_user
    item_name=update.message.text.strip()

    if item_name==BUTTON_GUILD_BACK:
        u=db.get_user(user.id)
        gid=u[14]
        if gid is None:
            await update.message.reply_text("Возвращаемся...",
                                            reply_markup=ReplyKeyboardMarkup(
                                                [[KeyboardButton("🏞 Озеро"),KeyboardButton("📦 Инвентарь"),KeyboardButton("👤 О рыбаке")],
                                                 [KeyboardButton("🏪 Магазин"),KeyboardButton("🏆 Таблица Лидеров"),KeyboardButton("🛡️ Гильдии")],
                                                 [KeyboardButton("🔍 Помощь")]],
                                                resize_keyboard=True))
            return ConversationHandler.END
        else:
            text=guild_info_text(gid, db)
            await update.message.reply_text(text,reply_markup=guild_main_menu_keyboard(user.id,db))
            return GUILD_MENU

    # Поиск предмета в GUILD_RODS и GUILD_BAITS
    g=db.get_user(user.id)
    gid=g[14]
    if gid is None:
        await update.message.reply_text("У вас нет гильдии!",
                                        reply_markup=guild_main_menu_keyboard(user.id,db))
        return GUILD_MENU
    G=db.get_guild(gid)
    guild_level=G["level"]

    rods_available=[rod for rod in GUILD_RODS if guild_level>=rod["required_level"]]
    baits_available=[bait for bait in GUILD_BAITS if guild_level>=bait["required_level"]]

    chosen_item=None
    item_type=None
    for rod in rods_available:
        if rod["name"]==item_name:
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
            f"Купить {chosen_item['name']} за {chosen_item['price']} золота?",
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
    db=context.application.bot_data["db"]
    user=update.effective_user
    u=db.get_user(user.id)
    item=context.user_data["guild_shop_item"]
    item_type=context.user_data["guild_shop_item_type"]
    gid=u[14]
    g=db.get_guild(gid)
    guild_name=g["name"]

    if update.message.text=="✅ Да":
        if u[2]>=item["price"]:
            db.update_user(user.id, gold=u[2]-item["price"])
            if item_type=="rod":
                # Покупка удочки
                db.update_user(user.id, current_rod_name=item["name"], current_rod_bonus=item["bonus_percent"])
                await update.message.reply_text(f"Вы купили {item['name']}!",
                                                reply_markup=ReplyKeyboardMarkup([[KeyboardButton(BUTTON_GUILD_BACK)]],resize_keyboard=True))
            else:
                # Покупка наживки
                from datetime import datetime, timedelta
                end_time = datetime.utcnow()+timedelta(minutes=item["duration"])
                import json
                db.update_user(user.id, current_bait_name=item["name"],
                               current_bait_end=end_time.isoformat(),
                               current_bait_probs=json.dumps(item["probabilities"]))
                await update.message.reply_text(
                    f"Вы купили наживку {item['name']}!",
                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton(BUTTON_GUILD_BACK)]],resize_keyboard=True)
                )
        else:
            need=item["price"]-u[2]
            await update.message.reply_text(f"Недостаточно золота! Не хватает {need}.",
                                            reply_markup=ReplyKeyboardMarkup([[KeyboardButton(BUTTON_GUILD_BACK)]],resize_keyboard=True))
    else:
        await update.message.reply_text("Покупка отменена.",
                                        reply_markup=ReplyKeyboardMarkup([[KeyboardButton(BUTTON_GUILD_BACK)]],resize_keyboard=True))
    context.user_data.pop("guild_shop_item",None)
    context.user_data.pop("guild_shop_item_type",None)
    return GUILD_SHOP_MENU

async def guild_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=context.application.bot_data["db"]
    user=update.effective_user
    u=db.get_user(user.id)
    gid=u[14]
    if gid is None:
        await update.message.reply_text("Вы не в гильдии.",
                                        reply_markup=guild_main_menu_keyboard(user.id,db))
        return GUILD_MENU
    g=db.get_guild(gid)
    members=db.get_guild_members(gid)
    leader_id=g["leader_id"]
    members.remove(leader_id)

    def jt(uid):
        uu=db.get_user(uid)
        if uu[15]:
            return datetime.fromisoformat(uu[15])
        return datetime.utcnow()

    members.sort(key=jt)
    members=[leader_id]+members

    msg="Список участников гильдии:\n"
    for i,uid_ in enumerate(members,start=1):
        d=db.get_user(uid_)
        name=d[1] if d[1] else "Неизвестный"
        lvl=d[4]
        rank=get_guild_membership_rank(uid_,gid,db)
        msg+=f"{i}. {name} ({lvl} ур.) - {rank}\n"
    keyboard=[[KeyboardButton(BUTTON_GUILD_BACK)]]
    await update.message.reply_text(msg,reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True))
    return GUILD_MEMBERS_MENU

async def not_implemented_leaders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=context.application.bot_data["db"]
    user=update.effective_user
    u=db.get_user(user.id)
    gid=u[14]
    if gid is None:
        await update.message.reply_text("Вы не в гильдии.",
                                        reply_markup=guild_main_menu_keyboard(user.id,db))
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
    db=context.application.bot_data["db"]
    user=update.effective_user
    u=db.get_user(user.id)
    gid=u[14]
    g=db.get_guild(gid)
    text=update.message.text
    members=db.get_guild_members(gid)

    users=[]
    for uid_ in members:
        uu=db.get_user(uid_)
        users.append(uu)

    if text==BUTTON_GUILD_LEADERS_GOLD:
        cat="золоту"
        users.sort(key=lambda x:x[12],reverse=True)
        val=lambda d: d[12]
    elif text==BUTTON_GUILD_LEADERS_KG:
        cat="улову"
        users.sort(key=lambda x:x[13],reverse=True)
        val=lambda d: d[13]
    elif text==BUTTON_GUILD_LEADERS_EXP:
        cat="опыту"
        users.sort(key=lambda x:x[3],reverse=True)
        val=lambda d: d[3]
    elif text==BUTTON_GUILD_BACK:
        text_=guild_info_text(gid,db)
        await update.message.reply_text(text_,reply_markup=guild_main_menu_keyboard(user.id,db))
        return GUILD_MENU
    else:
        text_=guild_info_text(gid,db)
        await update.message.reply_text(text_,reply_markup=guild_main_menu_keyboard(user.id,db))
        return GUILD_MENU

    msg=f"🏆 Топ по {cat} внутри гильдии:\n"
    for i,d in enumerate(users[:10], start=1):
        name=d[1] if d[1] else "Неизвестный рыбак"
        lvl=d[4]
        rank=get_guild_membership_rank(d[0],gid,db)
        msg+=f"{i}. {name} ({lvl} ур.) - {rank} - {val(d)}\n"

    await update.message.reply_text(msg,reply_markup=ReplyKeyboardMarkup([[KeyboardButton(BUTTON_GUILD_BACK)]],resize_keyboard=True))
    return GUILD_LEADERS_MENU

async def go_back_guild(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Возвращаемся...",
                                    reply_markup=ReplyKeyboardMarkup(
                                        [[KeyboardButton("🏞 Озеро"),KeyboardButton("📦 Инвентарь"),KeyboardButton("👤 О рыбаке")],
                                         [KeyboardButton("🏪 Магазин"),KeyboardButton("🏆 Таблица Лидеров"),KeyboardButton("🛡️ Гильдии")],
                                         [KeyboardButton("🔍 Помощь")]],
                                        resize_keyboard=True))
    return ConversationHandler.END

async def go_back_guild_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Возвращаемся...",
                                    reply_markup=ReplyKeyboardMarkup(
                                        [[KeyboardButton("🏞 Озеро"),KeyboardButton("📦 Инвентарь"),KeyboardButton("👤 О рыбаке")],
                                         [KeyboardButton("🏪 Магазин"),KeyboardButton("🏆 Таблица Лидеров"),KeyboardButton("🛡️ Гильдии")],
                                         [KeyboardButton("🔍 Помощь")]],
                                        resize_keyboard=True))
    return ConversationHandler.END

def guild_conversation_handler():
    # Добавляем фильтр, чтобы реагировать и на "Гильдии" и на "Моя Гильдия"
    guild_entry_filter = filters.Regex(f"^{re.escape(BUTTON_GUILDS)}$|^{re.escape(BUTTON_MY_GUILD)}$")
    return ConversationHandler(
        entry_points=[MessageHandler(guild_entry_filter, guilds_handler)],
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
                # Без кнопки Вернуться, так что тут нет хендлера на BUTTON_GO_BACK
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
