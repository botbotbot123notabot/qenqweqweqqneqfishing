import sqlite3
import json
from datetime import datetime

class Database:
    def __init__(self, db_path="fishing_game.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """
        Инициализирует необходимые таблицы (users, inventory, unidentified, guilds, guild_members, stats, quests, bonuses).
        Добавляем метод create_guild, чтобы можно было создавать новые гильдии.
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Основные таблицы
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

        # quests
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

        # bonuses
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

    # -------------------- CREATE GUILD --------------------
    def create_guild(self, guild_name, leader_id):
        """
        Создаёт новую гильдию с названием `guild_name`, лидером `leader_id`, уровнем 0, опытом 0.
        Возвращает сгенерированный `guild_id`.
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        now = datetime.utcnow().isoformat()
        # создаём запись в guilds
        c.execute("""
            INSERT INTO guilds (name, level, experience, leader_id, created_time)
            VALUES (?, 0, 0, ?, ?)
        """, (guild_name, leader_id, now))
        guild_id = c.lastrowid  # получаем новосозданный guild_id

        # добавляем лидера в таблицу guild_members
        c.execute("INSERT OR IGNORE INTO guild_members (guild_id, user_id) VALUES (?,?)",
                  (guild_id, leader_id))

        conn.commit()
        conn.close()
        return guild_id

    # -------------------- USERS --------------------
    def get_user(self, user_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if row is None:
            now = datetime.utcnow().isoformat()
            c.execute("""
            INSERT INTO users
            (user_id, nickname, gold, experience, level, rank,
             registration_time, current_rod_name, current_rod_bonus,
             current_bait_name, current_bait_end, current_bait_probs,
             total_gold_earned, total_kg_caught, guild_id, guild_join_time)
            VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, NULL, NULL)
            """, (user_id, 0, 0, 1, "Юный рыбак", now, "Бамбуковая удочка 🎣", 0, 0, 0))
            conn.commit()

            c.execute("INSERT INTO unidentified (user_id, common, rare, legendary) VALUES (?,?,?,?)",
                      (user_id, 0, 0, 0))
            conn.commit()

            c.execute("INSERT INTO stats (user_id, fish_caught_per_rod, fish_caught_per_bait) VALUES (?,?,?)",
                      (user_id, "{}", "{}"))
            conn.commit()

            c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            row = c.fetchone()
        conn.close()
        return row

    def update_user(self, user_id, **kwargs):
        if not kwargs:
            return
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        fields=[]
        values=[]
        for k,v in kwargs.items():
            fields.append(f"{k}=?")
            values.append(v)
        values.append(user_id)
        sql="UPDATE users SET "+",".join(fields)+" WHERE user_id=?"
        c.execute(sql, tuple(values))
        conn.commit()
        conn.close()

    # -------------------- UNIDENTIFIED --------------------
    def get_unidentified(self, user_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT common,rare,legendary FROM unidentified WHERE user_id=?", (user_id,))
        row=c.fetchone()
        if row is None:
            c.execute("INSERT INTO unidentified (user_id,common,rare,legendary) VALUES (?,?,?,?)",
                      (user_id,0,0,0))
            conn.commit()
            row=(0,0,0)
        conn.close()
        return {"common":row[0], "rare":row[1], "legendary":row[2]}

    def update_unidentified(self, user_id, common=None, rare=None, legendary=None):
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

    # -------------------- INVENTORY --------------------
    def get_inventory(self, user_id):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT fish_name,weight,rarity,quantity FROM inventory WHERE user_id=?", (user_id,))
        rows=c.fetchall()
        conn.close()
        inv={}
        for fname,w,r,qty in rows:
            inv[(fname,w,r)]=qty
        return inv

    def update_inventory(self, user_id, fish_data):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        for (fname,w,r),qty in fish_data.items():
            if qty>0:
                c.execute("""
                INSERT OR REPLACE INTO inventory (user_id, fish_name, weight, rarity, quantity)
                VALUES (?,?,?,?,?)
                """,(user_id,fname,w,r,qty))
            else:
                c.execute("""
                DELETE FROM inventory WHERE user_id=? AND fish_name=? AND weight=? AND rarity=?
                """,(user_id,fname,w,r))
        conn.commit()
        conn.close()

    # -------------------- GUILDS --------------------
    def get_guild(self, guild_id):
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        c.execute("""
        SELECT guild_id,name,level,experience,leader_id,created_time
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
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        c.execute("SELECT user_id FROM guild_members WHERE guild_id=?", (guild_id,))
        rows=c.fetchall()
        conn.close()
        return [r[0] for r in rows]

    def add_guild_member(self, guild_id, user_id):
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        c.execute("INSERT OR IGNORE INTO guild_members (guild_id, user_id) VALUES (?,?)", (guild_id,user_id))
        conn.commit()
        conn.close()

    def remove_guild_member(self, guild_id, user_id):
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        c.execute("DELETE FROM guild_members WHERE guild_id=? AND user_id=?", (guild_id,user_id))
        conn.commit()
        conn.close()

    # -------------------- STATS --------------------
    def get_stats(self, user_id):
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        c.execute("SELECT fish_caught_per_rod, fish_caught_per_bait FROM stats WHERE user_id=?", (user_id,))
        row=c.fetchone()
        if not row:
            c.execute("INSERT INTO stats (user_id, fish_caught_per_rod, fish_caught_per_bait) VALUES (?,?,?)",
                      (user_id,"{}","{}"))
            conn.commit()
            rods, baits = {}, {}
        else:
            rods_s, baits_s = row
            rods = json.loads(rods_s) if rods_s else {}
            baits = json.loads(baits_s) if baits_s else {}
        conn.close()
        return rods, baits

    def update_stats(self, user_id, rods_stats=None, baits_stats=None):
        current_rods, current_baits = self.get_stats(user_id)
        if rods_stats:
            for k,v in rods_stats.items():
                current_rods[k]=current_rods.get(k,0)+v
        if baits_stats:
            for k,v in baits_stats.items():
                current_baits[k]=current_baits.get(k,0)+v

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

    # -------------------- QUESTS --------------------
    def get_quests(self, user_id):
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        c.execute("""
        SELECT cat_next_time, cat_color, sailor_fish_name, sailor_fish_rarity,
               sailor_gold, sailor_xp, sailor_active
        FROM quests
        WHERE user_id=?
        """,(user_id,))
        row=c.fetchone()
        if row is None:
            c.execute("""
            INSERT INTO quests (user_id,cat_next_time,cat_color,sailor_fish_name,sailor_fish_rarity,
                                sailor_gold,sailor_xp,sailor_active)
            VALUES (?,?,?,?,?,?,?,?)
            """,(user_id,None,None,None,None,0,0,0))
            conn.commit()
            cat_next_time=None
            cat_color=None
            sf_name=None
            sf_rarity=None
            sf_gold=0
            sf_xp=0
            sf_active=0
        else:
            cat_next_time, cat_color, sf_name, sf_rarity, sf_gold, sf_xp, sf_active=row
        conn.close()
        return {
            "cat_next_time":cat_next_time,
            "cat_color":cat_color,
            "sailor_fish_name":sf_name,
            "sailor_fish_rarity":sf_rarity,
            "sailor_gold":sf_gold,
            "sailor_xp":sf_xp,
            "sailor_active":sf_active
        }

    def update_quests(self, user_id, **kwargs):
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

    # -------------------- BONUSES --------------------
    def get_bonus(self, user_id):
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        c.execute("""
        SELECT bonus_name, bonus_end, bonus_fishing_speed, bonus_gold_percent, bonus_xp_percent
        FROM bonuses WHERE user_id=?
        """,(user_id,))
        row=c.fetchone()
        conn.close()
        if not row:
            return None
        b_name, b_end, b_fs, b_gold, b_xp=row
        end_dt=datetime.fromisoformat(b_end)
        now=datetime.utcnow()
        if end_dt<now:
            # бонус истёк => удаляем
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
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        c.execute("SELECT user_id FROM bonuses WHERE user_id=?",(user_id,))
        row=c.fetchone()
        if row is None:
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
        conn=sqlite3.connect(self.db_path)
        c=conn.cursor()
        c.execute("DELETE FROM bonuses WHERE user_id=?",(user_id,))
        conn.commit()
        conn.close()