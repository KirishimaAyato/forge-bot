import aiosqlite
import json
import os
from datetime import date

DB_PATH = os.getenv("DB_PATH", "forge.db")

LEVELS = [
    (1, 200, "Новобранец"), (2, 400, "Ученик"), (3, 700, "Воин"),
    (4, 1100, "Ветеран"), (5, 1600, "Элита"), (6, 2200, "Чемпион"),
    (7, 3000, "Легенда"), (8, 4000, "Мастер"), (9, 5500, "Архонт"),
    (10, 99999, "Бессмертный"),
]

def get_level_title(level: int) -> str:
    for l, _, title in LEVELS:
        if l == level:
            return title
    return "Бессмертный"

def get_xp_to_next(level: int) -> int:
    for l, xp, _ in LEVELS:
        if l == level:
            return xp
    return 99999


class Database:
    def __init__(self):
        self.db_path = DB_PATH

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    name TEXT DEFAULT 'Воин',
                    level INTEGER DEFAULT 1,
                    xp INTEGER DEFAULT 0,
                    yoga INTEGER DEFAULT 0,
                    walk INTEGER DEFAULT 0,
                    home INTEGER DEFAULT 0,
                    total INTEGER DEFAULT 0,
                    streak INTEGER DEFAULT 0,
                    last_date TEXT DEFAULT '',
                    prs TEXT DEFAULT '{}',
                    unlocked_achs TEXT DEFAULT '[]',
                    body_log TEXT DEFAULT '[]',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS workouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    type TEXT,
                    intensity TEXT DEFAULT 'auto',
                    xp INTEGER,
                    duration INTEGER,
                    notes TEXT DEFAULT '',
                    date TEXT,
                    is_pr INTEGER DEFAULT 0,
                    exercises TEXT DEFAULT '[]',
                    walk_data TEXT DEFAULT '{}',
                    yoga_data TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS water_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ml INTEGER,
                    time TEXT,
                    date TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            # Migration: add body_log column if upgrading from older version
            try:
                await db.execute("ALTER TABLE users ADD COLUMN body_log TEXT DEFAULT '[]'")
            except Exception:
                pass  # Column already exists
            await db.commit()

    async def ensure_user(self, user_id: int, username: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, username, name) VALUES (?, ?, ?)",
                (user_id, username, username)
            )
            await db.commit()

    async def get_user_data(self, user_id: int) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                d = dict(row)
                d["level_title"] = get_level_title(d["level"])
                d["xp_to_next"] = get_xp_to_next(d["level"])
                d["prs"] = json.loads(d["prs"])
                d["unlocked_achs"] = json.loads(d["unlocked_achs"])
                d["body_log"] = json.loads(d.get("body_log") or "[]")
                return d

    async def save_user_data(self, user_id: int, data: dict):
        """Save full state from WebApp (JSON blob from frontend)"""
        s = data.get("S", {})
        ua = data.get("ua", [])

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users SET
                    name = ?,
                    level = ?,
                    xp = ?,
                    yoga = ?,
                    walk = ?,
                    home = ?,
                    total = ?,
                    streak = ?,
                    last_date = ?,
                    prs = ?,
                    unlocked_achs = ?,
                    body_log = ?
                WHERE user_id = ?
            """, (
                s.get("name", "Воин"),
                s.get("level", 1),
                s.get("xp", 0),
                s.get("yoga", 0),
                s.get("walk", 0),
                s.get("home", 0),
                s.get("total", 0),
                s.get("streak", 0),
                s.get("lastDate", ""),
                json.dumps(s.get("prs", {})),
                json.dumps(ua),
                json.dumps(s.get("bodyLog", [])),
                user_id
            ))

            # Save workout history
            history = s.get("history", [])
            if history:
                # Delete and re-insert (simplest sync strategy)
                await db.execute("DELETE FROM workouts WHERE user_id = ?", (user_id,))
                for h in history[:200]:  # cap at 200
                    await db.execute("""
                        INSERT INTO workouts
                        (user_id, type, intensity, xp, duration, notes, date, is_pr, exercises, walk_data, yoga_data)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        user_id,
                        h.get("type", ""),
                        h.get("intensity", "auto"),
                        h.get("xp", 0),
                        h.get("dur", 0),
                        h.get("notes", ""),
                        h.get("date", ""),
                        1 if h.get("isPR") else 0,
                        json.dumps(h.get("exercises", [])),
                        json.dumps(h.get("walkData", {})),
                        json.dumps(h.get("yogaData", {})),
                    ))

            # Save water log
            water_log = s.get("waterLog", [])
            today = str(date.today().strftime("%d.%m.%Y"))
            await db.execute(
                "DELETE FROM water_log WHERE user_id = ? AND date = ?",
                (user_id, today)
            )
            for w in water_log:
                await db.execute(
                    "INSERT INTO water_log (user_id, ml, time, date) VALUES (?, ?, ?, ?)",
                    (user_id, w.get("ml", 0), w.get("time", ""), today)
                )

            await db.commit()

    async def load_full_state(self, user_id: int) -> dict:
        """Return full state JSON for WebApp"""
        user = await self.get_user_data(user_id)
        if not user:
            return {}

        # Load workouts
        history = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM workouts WHERE user_id = ? ORDER BY created_at DESC LIMIT 200",
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                for r in rows:
                    history.append({
                        "type": r["type"],
                        "intensity": r["intensity"],
                        "xp": r["xp"],
                        "dur": r["duration"],
                        "notes": r["notes"],
                        "date": r["date"],
                        "isPR": bool(r["is_pr"]),
                        "exercises": json.loads(r["exercises"]),
                        "walkData": json.loads(r["walk_data"]),
                        "yogaData": json.loads(r["yoga_data"]),
                    })

            # Load today's water
            today = str(date.today().strftime("%d.%m.%Y"))
            water_log = []
            async with db.execute(
                "SELECT ml, time FROM water_log WHERE user_id = ? AND date = ? ORDER BY id",
                (user_id, today)
            ) as cursor:
                rows = await cursor.fetchall()
                for r in rows:
                    water_log.append({"ml": r["ml"], "time": r["time"]})

        return {
            "name": user["name"],
            "level": user["level"],
            "xp": user["xp"],
            "xpToNext": user["xp_to_next"],
            "yoga": user["yoga"],
            "walk": user["walk"],
            "home": user["home"],
            "total": user["total"],
            "streak": user["streak"],
            "lastDate": user["last_date"],
            "prs": user["prs"],
            "history": history,
            "waterLog": water_log,
            "waterDate": today,
            "unlockedAchs": user["unlocked_achs"],
            "bodyLog": user["body_log"],
        }

    async def get_today_water(self, user_id: int) -> int:
        today = str(date.today().strftime("%d.%m.%Y"))
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COALESCE(SUM(ml), 0) FROM water_log WHERE user_id = ? AND date = ?",
                (user_id, today)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def reset_user(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users SET level=1, xp=0, yoga=0, walk=0, home=0,
                total=0, streak=0, last_date='', prs='{}', unlocked_achs='[]'
                WHERE user_id = ?
            """, (user_id,))
            await db.execute("DELETE FROM workouts WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM water_log WHERE user_id = ?", (user_id,))
            await db.commit()
