import logging
import random
import math
import re
import sqlite3
from datetime import datetime, timedelta

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

BUTTON_TASKS = "📝 Задания"
BUTTON_CAT = "Котик"
BUTTON_SAILOR = "Старый Моряк"
BUTTON_ACCEPT = "Да"
BUTTON_DECLINE = "Нет"
BUTTON_OK = "Хорошо!"
BUTTON_BACK_QUESTS = "🔙 Назад к заданиям"
BUTTON_NO_FISH = "Пока нет"
BUTTON_YES_TAKE = "Да, бери!"
BUTTON_GO_BACK = "🔙 Вернуться"

QUESTS_MENU = 2000
CAT_STATE = 2001
SAILOR_STATE = 2002

CAT_COOLDOWN_HOURS = 6
CAT_BONUS_MINUTES = 120
CAT_COLORS = ["Серый", "Полосатый", "Рыжий", "Мурлыкающий", "Грустный", "Мохнатый", "Озорной"]

def main_menu_keyboard_quests():
    """
    Локальная клавиатура главного меню без импорта fishingbot.py.
    Гильдии показываем как "🛡️ Гильдии" всегда, упрощённо.
    """
    return ReplyKeyboardMarkup([
        [KeyboardButton("🏞 Озеро"), KeyboardButton("📦 Инвентарь"), KeyboardButton("👤 О рыбаке")],
        [KeyboardButton("🏪 Магазин"), KeyboardButton("🏆 Таблица Лидеров"), KeyboardButton("🛡️ Гильдии")],
        [KeyboardButton("📝 Задания"), KeyboardButton("🔍 Помощь")]
    ], resize_keyboard=True)

def tasks_main_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton(BUTTON_CAT), KeyboardButton(BUTTON_SAILOR)],
        [KeyboardButton(BUTTON_GO_BACK)]
    ], resize_keyboard=True)

def get_required_xp(level):
    """
    Локальная копия функции подсчёта XP для уровней.
    """
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

def update_rank_local(user_id, db_):
    """
    Локальная версия update_rank.
    """
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

    u=db_.get_user(user_id)
    level = u[4]
    for lvl_data in LEVELS:
        if lvl_data["level"]==level:
            db_.update_user(user_id, rank=lvl_data["rank"])
            return

def simple_check_level_up(user_id, db_):
    """
    Локальная проверка level-up, аналогичная fucntion в fishingbot.py,
    но без импорта.
    """
    uu=db_.get_user(user_id)
    exp=uu[3]
    lvl=uu[4]
    gol=uu[2]
    level_up=False
    gold_reward=0
    new_lvl=None
    while lvl<=75 and exp>=get_required_xp(lvl):
        lvl+=1
        reward = lvl*2
        gol+=reward
        gold_reward+=reward
        level_up=True
        new_lvl=lvl
    if new_lvl:
        db_.update_user(user_id, level=new_lvl, gold=gol)
        update_rank_local(user_id, db_)
    return level_up,new_lvl,gold_reward

def apply_bonus_to_xp(user_id, base_xp, db_):
    if base_xp<=0:
        return base_xp
    bonus = db_.get_bonus(user_id)
    if not bonus:
        return base_xp
    xp_percent = bonus["bonus_xp_percent"]
    if xp_percent<=0:
        return base_xp
    inc = math.ceil(base_xp*(xp_percent/100.0))
    if inc<1:
        inc=1
    return base_xp+inc

def apply_bonus_to_gold(user_id, base_gold, db_):
    if base_gold<=0:
        return base_gold
    bonus = db_.get_bonus(user_id)
    if not bonus:
        return base_gold
    gold_percent = bonus["bonus_gold_percent"]
    if gold_percent<=0:
        return base_gold
    inc = math.ceil(base_gold*(gold_percent/100.0))
    if inc<1:
        inc=1
    return base_gold+inc

# ------------------- КОТИК -------------------

async def tasks_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Вы выходите на оживлённую площадь, где всегда можно найти приключения: "
        "поговорить с разными персонажами или взять необычные поручения.\n"
        "Кого хотите навестить?"
    )
    await update.message.reply_text(text, reply_markup=tasks_main_menu_keyboard())
    return QUESTS_MENU

async def cat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    db_=context.application.bot_data["db"]
    quests_data=db_.get_quests(user.id)
    cat_next_str = quests_data["cat_next_time"]
    cat_color = quests_data["cat_color"]

    if cat_next_str:
        cat_next_dt=datetime.fromisoformat(cat_next_str)
        now=datetime.utcnow()
        remain=(cat_next_dt-now).total_seconds()
        if remain>0:
            hours_left=int(remain//3600)+1
            await update.message.reply_text(
                f"Сейчас котик занят своими важными кошачьими делами!\n"
                f"Приходите позже... примерно через {hours_left} час(ов).",
                reply_markup=tasks_main_menu_keyboard()
            )
            return QUESTS_MENU

    if not cat_color:
        color = random.choice(CAT_COLORS)
        db_.update_quests(user.id, cat_color=color)
    else:
        color = cat_color

    text=(
        f"Перед вами {color} котик. Он подошёл и потерся, мурлыкая, об вашу ногу. "
        "Кажется, он очень голоден!\nНакормить его?"
    )
    keyboard=[
        [KeyboardButton(BUTTON_ACCEPT), KeyboardButton(BUTTON_DECLINE)],
        [KeyboardButton(BUTTON_BACK_QUESTS)]
    ]
    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return CAT_STATE

async def cat_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    db_=context.application.bot_data["db"]
    text=update.message.text

    if text==BUTTON_ACCEPT:
        inv=db_.get_inventory(user.id)
        fish_list=[(k,v) for k,v in inv.items() if v>0 and isinstance(k,tuple)]
        if not fish_list:
            await update.message.reply_text(
                "Котик продолжает смотреть на вас грустными глазами. Кажется, он хочет рыбки...",
                reply_markup=tasks_main_menu_keyboard()
            )
            return QUESTS_MENU
        fish_list.sort(key=lambda x:x[0][1])
        (fname,w,r), qty=fish_list[0]
        inv[(fname,w,r)] = qty-1
        db_.update_inventory(user.id, inv)
        # убираем цвет из конечного сообщения
        reply=(
            f"Вы успешно накормили котика рыбкой {fname}!\n"
            "Он всё съел, ещё раз потерся об ноги и убежал, кажется довольный!\n"
            "Вы сделали хорошее дело!"
        )
        await update.message.reply_text(reply)

        bonus_end = datetime.utcnow()+timedelta(minutes=CAT_BONUS_MINUTES)
        db_.update_bonus(user.id,
            bonus_name="Друг животных",
            bonus_end=bonus_end.isoformat(),
            bonus_fishing_speed=1,
            bonus_gold_percent=1,
            bonus_xp_percent=1
        )

        cat_next = datetime.utcnow()+timedelta(hours=CAT_COOLDOWN_HOURS)
        db_.update_quests(user.id, cat_next_time=cat_next.isoformat(), cat_color=None)

        await update.message.reply_text("Возвращаемся на площадь...",reply_markup=tasks_main_menu_keyboard())
        return QUESTS_MENU
    elif text==BUTTON_DECLINE:
        await update.message.reply_text(
            "Котик смотрит на вас разочарованно...",
            reply_markup=tasks_main_menu_keyboard()
        )
        return QUESTS_MENU
    else:
        await update.message.reply_text(
            "Хорошо, возвращаемся...",
            reply_markup=tasks_main_menu_keyboard()
        )
        return QUESTS_MENU

async def sailor_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    db_=context.application.bot_data["db"]
    quests_data=db_.get_quests(user.id)
    fish_name=quests_data["sailor_fish_name"]
    fish_rarity=quests_data["sailor_fish_rarity"]
    gold=quests_data["sailor_gold"]
    xp=quests_data["sailor_xp"]
    active=bool(quests_data["sailor_active"])

    if active and fish_name and fish_rarity:
        text_=(f"Старый Моряк:\nНу что, поймал рыбу {fish_name}?\n")
        inv=db_.get_inventory(user.id)
        matches=[]
        for (fname,w,r),qty in inv.items():
            if qty>0 and r==fish_rarity:
                if fname.endswith(fish_name):
                    matches.append(((fname,w,r),qty))
        if not matches:
            keyboard = [
                [KeyboardButton(BUTTON_NO_FISH)],
                [KeyboardButton(BUTTON_BACK_QUESTS)]
            ]
            await update.message.reply_text(text_, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
            return SAILOR_STATE
        else:
            keyboard = [
                [KeyboardButton(BUTTON_YES_TAKE), KeyboardButton(BUTTON_NO_FISH)],
                [KeyboardButton(BUTTON_BACK_QUESTS)]
            ]
            text_ += "Отдать рыбу?\n"
            await update.message.reply_text(text_, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
            return SAILOR_STATE
    else:
        # генерим новое задание
        rarities=["common","rare","legendary"]
        chosen_rarity=random.choice(rarities)
        if chosen_rarity=="common":
            xp=random.randint(15,35)
            gold=random.randint(10,15)
            if "FISH_DATA" not in context.application.bot_data:
                names=["Карась","Окунь","Лещ","Ротан","Угорь","Судак"]
            else:
                names=context.application.bot_data["FISH_DATA"]["common"]["names"]
        elif chosen_rarity=="rare":
            xp=random.randint(40,100)
            gold=random.randint(25,50)
            if "FISH_DATA" not in context.application.bot_data:
                names=["Карась","Окунь","Лещ","Ротан","Угорь","Судак"]
            else:
                names=context.application.bot_data["FISH_DATA"]["rare"]["names"]
        else:
            xp=random.randint(250,500)
            gold=random.randint(50,100)
            if "FISH_DATA" not in context.application.bot_data:
                names=["Язь","Сом","Налим","Тунец","Угорь","Лосось","Осётр"]
            else:
                names=context.application.bot_data["FISH_DATA"]["legendary"]["names"]

        chosen_name = random.choice(names)

        db_.update_quests(user.id,
            sailor_fish_name=chosen_name,
            sailor_fish_rarity=chosen_rarity,
            sailor_gold=gold,
            sailor_xp=xp,
            sailor_active=0
        )

        text_=(
            "Вы подходите к Старому Моряку, который сидит в своём кресле и курит трубку...\n"
            "Он поднимает глаза на вас:\n\n"
            f"Слушай, а не хочешь подзаработать?\n"
            f"Мне очень нужна рыба {chosen_name}, у меня такая будет в коллекции.\n"
            f"Заплачу {xp} опыта и {gold} золота!\n\n"
            "Что скажешь?"
        )
        keyboard=[
            [KeyboardButton(BUTTON_ACCEPT), KeyboardButton(BUTTON_DECLINE)],
            [KeyboardButton(BUTTON_BACK_QUESTS)]
        ]
        await update.message.reply_text(text_, reply_markup=ReplyKeyboardMarkup(keyboard,resize_keyboard=True))
        return SAILOR_STATE

async def sailor_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    db_=context.application.bot_data["db"]
    text=update.message.text
    quests_data=db_.get_quests(user.id)
    fish_name=quests_data["sailor_fish_name"]
    fish_rarity=quests_data["sailor_fish_rarity"]
    gold=quests_data["sailor_gold"]
    xp=quests_data["sailor_xp"]
    active=bool(quests_data["sailor_active"])

    if not fish_name or not fish_rarity:
        await update.message.reply_text(
            "Что-то пошло не так, не могу найти текущее задание...",
            reply_markup=tasks_main_menu_keyboard()
        )
        return QUESTS_MENU

    if text==BUTTON_ACCEPT and not active:
        db_.update_quests(user.id, sailor_active=1)
        await update.message.reply_text(
            "Вот и отлично! Удачи, жду с уловом!",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton(BUTTON_OK)]],resize_keyboard=True)
        )
        return SAILOR_STATE
    elif text==BUTTON_DECLINE and not active:
        db_.update_quests(user.id, sailor_fish_name=None, sailor_fish_rarity=None, sailor_gold=0, sailor_xp=0, sailor_active=0)
        await update.message.reply_text("Ну как хочешь...",reply_markup=tasks_main_menu_keyboard())
        return QUESTS_MENU
    elif text==BUTTON_OK and active:
        await update.message.reply_text("Хорошо, возвращаемся...",reply_markup=tasks_main_menu_keyboard())
        return QUESTS_MENU
    elif text==BUTTON_NO_FISH:
        await update.message.reply_text("Ну ладно, поймай сначала...",reply_markup=tasks_main_menu_keyboard())
        return QUESTS_MENU
    elif text==BUTTON_YES_TAKE and active:
        inv=db_.get_inventory(user.id)
        matches=[]
        for (fname,w,r),qty in inv.items():
            if qty>0 and r==fish_rarity:
                if fname.endswith(fish_name):
                    matches.append(((fname,w,r), qty))
        if not matches:
            await update.message.reply_text("Похоже, у вас нет нужной рыбы...", reply_markup=tasks_main_menu_keyboard())
            return QUESTS_MENU
        (f0,w0,r0), qty0 = matches[0]
        inv[(f0,w0,r0)] = qty0-1
        db_.update_inventory(user.id, inv)

        final_xp = apply_bonus_to_xp(user.id, xp, db_)
        final_gold=apply_bonus_to_gold(user.id, gold, db_)

        u=db_.get_user(user.id)
        new_exp=u[3]+final_xp
        new_gold=u[2]+final_gold
        db_.update_user(user.id, experience=new_exp, gold=new_gold)

        # Проверяем уровень
        level_up,new_level,g_reward=simple_check_level_up(user.id, db_)
        msg=(f"За выполненное задание вы получили {final_xp} опыта и {final_gold} золота!")
        if level_up:
            msg+=f"\nПоздравляем! Уровень повышен до {new_level}!\nДополнительно золото: {g_reward}"

        # Сбрасываем задание
        db_.update_quests(user.id,
            sailor_fish_name=None,
            sailor_fish_rarity=None,
            sailor_gold=0,
            sailor_xp=0,
            sailor_active=0
        )
        await update.message.reply_text(msg, reply_markup=tasks_main_menu_keyboard())
        return QUESTS_MENU
    else:
        await update.message.reply_text("Возвращаемся...",reply_markup=tasks_main_menu_keyboard())
        return QUESTS_MENU

async def go_back_quests_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    await update.message.reply_text(
        "Вы покинули площадь...",
        reply_markup=main_menu_keyboard_quests()
    )
    return ConversationHandler.END

def quests_conversation_handler():
    guild_entry_filter = filters.Regex(f"^{re.escape(BUTTON_TASKS)}$")
    return ConversationHandler(
        entry_points=[MessageHandler(guild_entry_filter, tasks_entry)],
        states={
            QUESTS_MENU:[
                MessageHandler(filters.Regex("^"+re.escape(BUTTON_CAT)+"$"), cat_handler),
                MessageHandler(filters.Regex("^"+re.escape(BUTTON_SAILOR)+"$"), sailor_handler),
                MessageHandler(filters.Regex("^"+re.escape(BUTTON_GO_BACK)+"$"), go_back_quests_main),
            ],
            CAT_STATE:[
                MessageHandler(filters.Regex(f"^{re.escape(BUTTON_ACCEPT)}$|^{re.escape(BUTTON_DECLINE)}$|^{re.escape(BUTTON_BACK_QUESTS)}$"), cat_decision)
            ],
            SAILOR_STATE:[
                MessageHandler(filters.Regex(f"^{re.escape(BUTTON_ACCEPT)}$|^{re.escape(BUTTON_DECLINE)}$|^{re.escape(BUTTON_OK)}$|^{re.escape(BUTTON_BACK_QUESTS)}$|^{re.escape(BUTTON_NO_FISH)}$|^{re.escape(BUTTON_YES_TAKE)}$"), sailor_decision)
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^"+re.escape(BUTTON_GO_BACK)+"$"), go_back_quests_main)],
        allow_reentry=True
    )