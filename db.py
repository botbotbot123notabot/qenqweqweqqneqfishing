import sqlite3
import json
from datetime import datetime

class Database:
    def __init__(self, db_path="fishing_game.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """
        Инициализирует необходимые таблицы в файле fishing_game.db (если их нет).
        Дополнительно создаём таблицы quests и bonuses для хранения состояния квестов и бонусов.
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # ----- Основные таблицы (уже существовали) -----
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            nickname TEXT,
            gold INTEGER,
            experience INTEGER,
            level INTEGER,
            rank TEXT,
            registration_time TEXT,
            current_rod_name TEXT,
            current_rod_bonus INTEGER,
            current_bait_name TEXT,
            current_bait_end TEXT,
            current_bait_probs TEXT,
            total_gold_earned INTEGER,
            total_kg_caught INTEGER,
            guild_id INTEGER,
            guild_join_time TEXT
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            user_id INTEGER,
            fish_name TEXT,
            weight INTEGER,
            rarity TEXT,
            quantity INTEGER,
            PRIMARY KEY (user_id, fish_name, weight, rarity)
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS unidentified (
            user_id INTEGER PRIMARY KEY,
            common INTEGER,
            rare INTEGER,
            legendary INTEGER
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS guilds (
            guild_id INTEGER PRIMARY KEY,
            name TEXT,
            level INTEGER,
            experience INTEGER,
            leader_id INTEGER,
            created_time TEXT
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS guild_members (
            guild_id INTEGER,
            user_id INTEGER,
            UNIQUE(guild_id, user_id)
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            user_id INTEGER PRIMARY KEY,
            fish_caught_per_rod TEXT,
            fish_caught_per_bait TEXT
        )
        """)

        # ----- Новая таблица quests -----
        # Хранит: 
        # - cat_next_time (TEXT) — когда снова можно кормить котика
        # - cat_color (TEXT) — текущий цвет кота
        # - sailor_fish_name (TEXT) — какую рыбу хочет моряк
        # - sailor_fish_rarity (TEXT) — rarirty, нужна для определения награды и проверки
        # - sailor_gold (INTEGER) — награда золота
        # - sailor_xp (INTEGER) — награда опыта
        # - sailor_active (INTEGER) — 0/1
        c.execute("""
        CREATE TABLE IF NOT EXISTS quests (
            user_id INTEGER PRIMARY KEY,
            cat_next_time TEXT,
            cat_color TEXT,
            sailor_fish_name TEXT,
            sailor_fish_rarity TEXT,
            sailor_gold INTEGER,
            sailor_xp INTEGER,
            sailor_active INTEGER
        )
        """)

        # ----- Таблица bonuses -----
        # хранит активный бонус у пользователя:
        # - bonus_name (TEXT) — «Друг животных» и т.п.
        # - bonus_end (TEXT) — isoformat datetime, когда истекает
        # - bonus_fishing_speed (INTEGER) — +% к скорости рыбалки
        # - bonus_gold_percent (INTEGER) — +% к золоту
        # - bonus_xp_percent (INTEGER) — +% к опыту
        c.execute("""
        CREATE TABLE IF NOT EXISTS bonuses (
            user_id INTEGER PRIMARY KEY,
            bonus_name TEXT,
            bonus_end TEXT,
            bonus_fishing_speed INTEGER,
            bonus_gold_percent INTEGER,
            bonus_xp_percent INTEGER
        )
        """)

        conn.commit()
        conn.close()

    # -------------------- Методы для users --------------------

    def get_user(self, user_id):
        """
        Возвращает кортеж со всеми полями из таблицы users для user_id.
        Если записи нет, создаёт новую по умолчанию и возвращает её.
        Поля (user_id, nickname, gold, experience, level, rank, registration_time, ...)
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()

        if row is None:
            now = datetime.utcnow().isoformat()
            # Создаём запись по умолчанию
            c.execute("""
            INSERT INTO users
            (user_id, nickname, gold, experience, level, rank,
             registration_time, current_rod_name, current_rod_bonus,
             current_bait_name, current_bait_end, current_bait_probs,
             total_gold_earned, total_kg_caught, guild_id, guild_join_time)
            VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, NULL, NULL)
            """, (user_id, 0, 0, 1, "Юный рыбак", now, "Бамбуковая удочка 🎣", 0, 0, 0))
            conn.commit()

            # Создаем запись в unidentified
            c.execute("INSERT INTO unidentified (user_id, common, rare, legendary) VALUES (?,?,?,?)",
                      (user_id, 0, 0, 0))
            conn.commit()

            # Создаём запись в stats
            c.execute("INSERT INTO stats (user_id, fish_caught_per_rod, fish_caught_per_bait) VALUES (?,?,?)",
                      (user_id, "{}", "{}"))
            conn.commit()

            # Повторно достаём
            c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            row = c.fetchone()

        conn.close()
        return row  # Это кортеж

    def update_user(self, user_id, **kwargs):
        """
        Обновляет поля в таблице users для user_id.
        Использование: update_user(1234, gold=100, experience=50)
        """
        if not kwargs:
            return
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        fields = []
        values = []
        for k,v in kwargs.items():
            fields.append(f"{k}=?")
            values.append(v)
        values.append(user_id)
        sql = "UPDATE users SET " + ",".join(fields) + " WHERE user_id=?"
        c.execute(sql, tuple(values))
        conn.commit()
        conn.close()

    # -------------------- Методы для unidentified --------------------

    def get_unidentified(self, user_id):
        """
        Возвращает словарь { 'common':..., 'rare':..., 'legendary':... }
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT common,rare,legendary FROM unidentified WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if row is None:
            c.execute("INSERT INTO unidentified (user_id,common,rare,legendary) VALUES (?,?,?,?)",
                      (user_id,0,0,0))
            conn.commit()
            row=(0,0,0)
        conn.close()
        return {"common":row[0], "rare":row[1], "legendary":row[2]}

    def update_unidentified(self, user_id, common=None, rare=None, legendary=None):
        """
        Обновляет поля common/rare/legendary у unidentified пользователя.
        """
        current = self.get_unidentified(user_id)
        if common is not None:
            current["common"]=common
        if rare is not None:
            current["rare"]=rare
        if legendary is not None:
            current["legendary"]=legendary

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE unidentified SET common=?, rare=?, legendary=? WHERE user_id=?",
                  (current["common"], current["rare"], current["legendary"], user_id))
        conn.commit()
        conn.close()

    # -------------------- Методы для inventory --------------------

    def get_inventory(self, user_id):
        """
        Возвращает словарь { (fish_name,weight,rarity): quantity, ... }
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT fish_name, weight, rarity, quantity FROM inventory WHERE user_id=?", (user_id,))
        rows = c.fetchall()
        conn.close()
        inv={}
        for fname,w,r,qty in rows:
            inv[(fname,w,r)] = qty
        return inv

    def update_inventory(self, user_id, fish_data):
        """
        Принимает словарь { (fname,w,r): qty, ... } и пишет в базу.
        qty<=0 => удаляем строку
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        for (fname,w,r),qty in fish_data.items():
            if qty>0:
                c.execute("""
                INSERT OR REPLACE INTO inventory (user_id, fish_name, weight, rarity, quantity)
                VALUES (?,?,?,?,?)
                """, (user_id, fname, w, r, qty))
            else:
                c.execute("""
                DELETE FROM inventory WHERE user_id=? AND fish_name=? AND weight=? AND rarity=?
                """, (user_id, fname, w, r))
        conn.commit()
        conn.close()

    # -------------------- Методы для quests --------------------

    def get_quests(self, user_id):
        """
        Возвращает словарь с полями:
          cat_next_time, cat_color,
          sailor_fish_name, sailor_fish_rarity, sailor_gold, sailor_xp, sailor_active
        Если записи нет, создаём пустую.
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
        SELECT cat_next_time, cat_color, sailor_fish_name, sailor_fish_rarity,
               sailor_gold, sailor_xp, sailor_active
        FROM quests
        WHERE user_id=?
        """, (user_id,))
        row = c.fetchone()
        if row is None:
            # вставляем пустую
            c.execute("""
            INSERT INTO quests (user_id, cat_next_time, cat_color, sailor_fish_name,
                                sailor_fish_rarity, sailor_gold, sailor_xp, sailor_active)
            VALUES (?, NULL, NULL, NULL, NULL, 0, 0, 0)
            """, (user_id,))
            conn.commit()
            cat_next_time=None
            cat_color=None
            sf_name=None
            sf_rarity=None
            sf_gold=0
            sf_xp=0
            sf_active=0
        else:
            cat_next_time, cat_color, sf_name, sf_rarity, sf_gold, sf_xp, sf_active = row
        conn.close()

        return {
            "cat_next_time": cat_next_time,
            "cat_color": cat_color,
            "sailor_fish_name": sf_name,
            "sailor_fish_rarity": sf_rarity,
            "sailor_gold": sf_gold,
            "sailor_xp": sf_xp,
            "sailor_active": sf_active
        }

    def update_quests(self, user_id, **kwargs):
        """
        Обновляет поля в таблице quests. Например:
          update_quests(user_id, cat_next_time=..., cat_color=..., sailor_fish_name=..., ...)
        """
        if not kwargs:
            return
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        fields=[]
        values=[]
        for k,v in kwargs.items():
            fields.append(f"{k}=?")
            values.append(v)
        values.append(user_id)
        sql="UPDATE quests SET "+",".join(fields)+" WHERE user_id=?"
        c.execute(sql, tuple(values))
        conn.commit()
        conn.close()

    # -------------------- Методы для bonuses --------------------

    def get_bonus(self, user_id):
        """
        Возвращает словарь с полями:
         bonus_name, bonus_end, bonus_fishing_speed, bonus_gold_percent, bonus_xp_percent
        или None, если записи нет или бонус истёк.
        """
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        c.execute("""
        SELECT bonus_name, bonus_end, bonus_fishing_speed, bonus_gold_percent, bonus_xp_percent
        FROM bonuses WHERE user_id=?
        """, (user_id,))
        row=c.fetchone()
        conn.close()
        if not row:
            return None
        b_name, b_end, b_fs, b_gold, b_xp = row
        end_dt=datetime.fromisoformat(b_end)
        now=datetime.utcnow()
        if end_dt<now:
            # бонус истёк => удалим
            self.remove_bonus(user_id)
            return None
        return {
            "bonus_name": b_name,
            "bonus_end": b_end,
            "bonus_fishing_speed": b_fs,
            "bonus_gold_percent": b_gold,
            "bonus_xp_percent": b_xp
        }

    def update_bonus(self, user_id, **kwargs):
        """
        Создаёт или обновляет строку в таблице bonuses.
        """
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        # Проверяем, есть ли запись
        c.execute("SELECT user_id FROM bonuses WHERE user_id=?", (user_id,))
        row=c.fetchone()
        if row is None:
            # вставляем
            columns=["user_id"]
            placeholders=["?"]
            values=[user_id]
            for k,v in kwargs.items():
                columns.append(k)
                placeholders.append("?")
                values.append(v)
            sql="INSERT INTO bonuses ("+",".join(columns)+") VALUES("+",".join(placeholders)+")"
            c.execute(sql, tuple(values))
        else:
            # обновляем
            fields=[]
            values=[]
            for k,v in kwargs.items():
                fields.append(f"{k}=?")
                values.append(v)
            values.append(user_id)
            sql="UPDATE bonuses SET "+",".join(fields)+" WHERE user_id=?"
            c.execute(sql, tuple(values))
        conn.commit()
        conn.close()

    def remove_bonus(self, user_id):
        """
        Удаляет строку в bonuses для данного пользователя.
        """
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        c.execute("DELETE FROM bonuses WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()

    # -------------------- Методы для stats --------------------

    def get_stats(self, user_id):
        """
        Возвращает (rods_stats, baits_stats) — словари python.
        rods_stats = { 'Удочка Новичка 🎣': кол-во пойманной рыбы, ...}
        baits_stats = { 'Червяк 🪱': кол-во пойманной рыбы, ...}
        """
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        c.execute("SELECT fish_caught_per_rod, fish_caught_per_bait FROM stats WHERE user_id=?", (user_id,))
        row=c.fetchone()
        if not row:
            # создаём
            c.execute("INSERT INTO stats (user_id, fish_caught_per_rod, fish_caught_per_bait) VALUES (?,?,?)",
                      (user_id,"{}","{}"))
            conn.commit()
            rods, baits = {}, {}
        else:
            rods_s, baits_s = row
            import json
            rods = json.loads(rods_s) if rods_s else {}
            baits = json.loads(baits_s) if baits_s else {}
        conn.close()
        return rods, baits

    def update_stats(self, user_id, rods_stats=None, baits_stats=None):
        """
        Обновляет словари stats. rods_stats={...}, baits_stats={...}
        Просто сливаем со старыми значениями.
        """
        current_rods, current_baits = self.get_stats(user_id)
        if rods_stats is not None:
            for k,v in rods_stats.items():
                if k in current_rods:
                    current_rods[k]+=v
                else:
                    current_rods[k]=v
        if baits_stats is not None:
            for k,v in baits_stats.items():
                if k in current_baits:
                    current_baits[k]+=v
                else:
                    current_baits[k]=v

        # Сохраняем
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        import json
        c.execute("""
        UPDATE stats
        SET fish_caught_per_rod=?, fish_caught_per_bait=?
        WHERE user_id=?
        """,(json.dumps(current_rods), json.dumps(current_baits), user_id))
        conn.commit()
        conn.close()

    # -------------------- Методы для guilds (пример, не все) --------------------

    def get_guild(self, guild_id):
        """
        Возвращает словарь с данными гильдии, или None.
        """
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        c.execute("""
        SELECT guild_id, name, level, experience, leader_id, created_time
        FROM guilds
        WHERE guild_id=?
        """, (guild_id,))
        row=c.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "guild_id": row[0],
            "name": row[1],
            "level": row[2],
            "experience": row[3],
            "leader_id": row[4],
            "created_time": row[5]
        }

    def update_guild(self, guild_id, **kwargs):
        """
        Обновляет поля в guilds для guild_id.
        """
        if not kwargs:
            return
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        fields=[]
        values=[]
        for k,v in kwargs.items():
            fields.append(f"{k}=?")
            values.append(v)
        values.append(guild_id)
        sql="UPDATE guilds SET "+",".join(fields)+" WHERE guild_id=?"
        c.execute(sql, tuple(values))
        conn.commit()
        conn.close()

    def get_guild_members(self, guild_id):
        """
        Возвращает список user_id членов гильдии.
        """
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        c.execute("SELECT user_id FROM guild_members WHERE guild_id=?", (guild_id,))
        rows=c.fetchall()
        conn.close()
        return [r[0] for r in rows]

    def add_guild_member(self, guild_id, user_id):
        """
        Добавляет user_id в гильдию, игнорируя дубликаты.
        """
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        c.execute("INSERT OR IGNORE INTO guild_members (guild_id, user_id) VALUES (?,?)", (guild_id,user_id))
        conn.commit()
        conn.close()

    def remove_guild_member(self, guild_id, user_id):
        """
        Удаляет user_id из гильдии.
        """
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        c.execute("DELETE FROM guild_members WHERE guild_id=? AND user_id=?", (guild_id,user_id))
        conn.commit()
        conn.close()
