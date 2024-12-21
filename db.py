import sqlite3
from datetime import datetime
from math import pi
from collections import defaultdict

class Database:
    def __init__(self, db_path="fishing_game.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Таблица пользователей
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

        # Таблица инвентаря (опознанная рыба)
        # Хранит имя рыбы, вес, количество для каждого юзера
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

        # Таблица неопознанной рыбы
        c.execute("""
        CREATE TABLE IF NOT EXISTS unidentified (
            user_id INTEGER PRIMARY KEY,
            common INTEGER,
            rare INTEGER,
            legendary INTEGER
        )
        """)

        # Таблица гильдий
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

        # Таблица членов гильдий
        c.execute("""
        CREATE TABLE IF NOT EXISTS guild_members (
            guild_id INTEGER,
            user_id INTEGER,
            UNIQUE(guild_id, user_id)
        )
        """)

        # Для отслеживания предпочтений удочек и наживок
        # упрощённо можно хранить их как JSON или отдельные таблицы статистики.
        c.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            user_id INTEGER PRIMARY KEY,
            fish_caught_per_rod TEXT,
            fish_caught_per_bait TEXT
        )
        """)

        conn.commit()
        conn.close()

    def get_user(self, user_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()

        if row is None:
            # Создадим дефолтного пользователя в БД
            now = datetime.utcnow().isoformat()
            c.execute("INSERT INTO users (user_id, gold,experience,level,rank,registration_time,total_gold_earned,total_kg_caught) VALUES (?,?,?,?,?,?,?,?)",
                      (user_id, 0,0,1,"Юный рыбак",now,0,0))
            conn.commit()
            c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            row = c.fetchone()

            # Создать запись в unidentified
            c.execute("INSERT INTO unidentified (user_id,common,rare,legendary) VALUES (?,?,?,?)",
                      (user_id,0,0,0))
            conn.commit()

            # Создать запись в stats
            c.execute("INSERT INTO stats (user_id, fish_caught_per_rod, fish_caught_per_bait) VALUES (?,?,?)", (user_id,"{}","{}"))
            conn.commit()

        conn.close()
        return row

    def update_user(self, user_id, **kwargs):
        # kwargs: nickname=..., gold=..., level=..., etc.
        # Генерируем SQL динамически.
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

    def get_unidentified(self, user_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT common,rare,legendary FROM unidentified WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if row is None:
            # создадим дефолтную запись
            c.execute("INSERT INTO unidentified (user_id,common,rare,legendary) VALUES (?,?,?,?)",
                      (user_id,0,0,0))
            conn.commit()
            row = (0,0,0)
        conn.close()
        return {"common": row[0], "rare": row[1], "legendary": row[2]}

    def update_unidentified(self, user_id, common=None, rare=None, legendary=None):
        # Получаем текущие значения
        u = self.get_unidentified(user_id)
        if common is not None:
            u["common"]=common
        if rare is not None:
            u["rare"]=rare
        if legendary is not None:
            u["legendary"]=legendary

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE unidentified SET common=?,rare=?,legendary=? WHERE user_id=?",
                  (u["common"],u["rare"],u["legendary"],user_id))
        conn.commit()
        conn.close()

    def get_inventory(self, user_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT fish_name, weight, rarity, quantity FROM inventory WHERE user_id=?", (user_id,))
        rows = c.fetchall()
        conn.close()
        inv = {}
        for fname,w,r,qty in rows:
            inv[(fname,w,r)] = qty
        return inv

    def update_inventory(self, user_id, fish_data):
        # fish_data - словарь {(fname,w,r): qty}
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Перебираем все записи и вставляем/обновляем
        for (fname,w,r),qty in fish_data.items():
            if qty>0:
                c.execute("INSERT OR REPLACE INTO inventory (user_id,fish_name,weight,rarity,quantity) VALUES (?,?,?,?,?)",
                          (user_id,fname,w,r,qty))
            else:
                # qty=0 - удаляем запись
                c.execute("DELETE FROM inventory WHERE user_id=? AND fish_name=? AND weight=? AND rarity=?",
                          (user_id,fname,w,r))
        conn.commit()
        conn.close()

    # Аналогично для гильдий, теперь все гильдейские данные также храним в БД
    def get_guild(self, guild_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT guild_id,name,level,experience,leader_id,created_time FROM guilds WHERE guild_id=?", (guild_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return {
                "guild_id": row[0],
                "name": row[1],
                "level": row[2],
                "experience": row[3],
                "leader_id": row[4],
                "created_time": row[5]
            }
        return None

    def create_guild(self, name, leader_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        now = datetime.utcnow().isoformat()
        c.execute("INSERT INTO guilds (name,level,experience,leader_id,created_time) VALUES (?,?,?,?,?)",
                  (name,0,0,leader_id,now))
        guild_id = c.lastrowid
        c.execute("INSERT INTO guild_members (guild_id,user_id) VALUES (?,?)", (guild_id,leader_id))
        conn.commit()
        conn.close()
        return guild_id

    def update_guild(self, guild_id, **kwargs):
        if not kwargs:
            return
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        fields = []
        values = []
        for k,v in kwargs.items():
            fields.append(f"{k}=?")
            values.append(v)
        values.append(guild_id)
        sql = "UPDATE guilds SET " + ",".join(fields) + " WHERE guild_id=?"
        c.execute(sql, tuple(values))
        conn.commit()
        conn.close()

    def add_guild_member(self, guild_id, user_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO guild_members (guild_id,user_id) VALUES (?,?)", (guild_id,user_id))
        conn.commit()
        conn.close()

    def remove_guild_member(self, guild_id, user_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM guild_members WHERE guild_id=? AND user_id=?", (guild_id,user_id))
        conn.commit()
        conn.close()

    def get_guild_members(self, guild_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT user_id FROM guild_members WHERE guild_id=?", (guild_id,))
        rows = c.fetchall()
        conn.close()
        return [r[0] for r in rows]

    # Аналогично реализуем методы для статистики (удочки/наживки), если нужно.
    def get_stats(self, user_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT fish_caught_per_rod, fish_caught_per_bait FROM stats WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if row is None:
            return {},{}
        import json
        rods = json.loads(row[0])
        baits = json.loads(row[1])
        conn.close()
        return rods,baits

    def update_stats(self, user_id, rods_stats=None, baits_stats=None):
        current_rods, current_baits = self.get_stats(user_id)
        if rods_stats is not None:
            current_rods.update(rods_stats)
        if baits_stats is not None:
            current_baits.update(baits_stats)

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        import json
        c.execute("UPDATE stats SET fish_caught_per_rod=?, fish_caught_per_bait=? WHERE user_id=?",
                  (json.dumps(current_rods),json.dumps(current_baits),user_id))
        conn.commit()
        conn.close()