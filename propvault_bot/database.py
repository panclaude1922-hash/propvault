"""
database.py — SQLite через aiosqlite
Таблицы: users, subscriptions, properties, moderation_log
"""

import aiosqlite
from datetime import datetime

DB_PATH = "propvault.db"


async def init_db():
    """Создаём таблицы при первом запуске."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        -- Пользователи
        CREATE TABLE IF NOT EXISTS users (
            tg_id       INTEGER PRIMARY KEY,
            username    TEXT,
            full_name   TEXT,
            role        TEXT NOT NULL DEFAULT 'investor',  -- investor | realtor | admin
            registered_at TEXT NOT NULL
        );

        -- Подписки риелторов
        CREATE TABLE IF NOT EXISTS subscriptions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id       INTEGER NOT NULL,
            plan        TEXT NOT NULL,   -- start | pro | elite
            started_at  TEXT NOT NULL,
            expires_at  TEXT NOT NULL,
            is_active   INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (tg_id) REFERENCES users(tg_id)
        );

        -- Объекты недвижимости
        CREATE TABLE IF NOT EXISTS properties (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            realtor_id      INTEGER NOT NULL,
            title           TEXT NOT NULL,
            region          TEXT NOT NULL,
            city            TEXT NOT NULL,
            yield_pct       REAL NOT NULL,
            min_entry       INTEGER NOT NULL,
            goal_amount     INTEGER NOT NULL,
            collected       INTEGER NOT NULL DEFAULT 0,
            deadline        TEXT NOT NULL,
            description     TEXT NOT NULL,
            phone           TEXT NOT NULL,
            email           TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected
            reject_reason   TEXT,
            created_at      TEXT NOT NULL,
            approved_at     TEXT,
            FOREIGN KEY (realtor_id) REFERENCES users(tg_id)
        );

        -- Лог модерации
        CREATE TABLE IF NOT EXISTS moderation_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id     INTEGER NOT NULL,
            moderator_id    INTEGER NOT NULL,
            action          TEXT NOT NULL,   -- approved | rejected
            comment         TEXT,
            acted_at        TEXT NOT NULL,
            FOREIGN KEY (property_id) REFERENCES properties(id)
        );
        """)
        await db.commit()


# ── USERS ──────────────────────────────────────────────

async def get_user(tg_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE tg_id = ?", (tg_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create_user(tg_id: int, username: str, full_name: str, role: str = "investor"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (tg_id, username, full_name, role, registered_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (tg_id, username, full_name, role, datetime.utcnow().isoformat())
        )
        await db.commit()


async def set_user_role(tg_id: int, role: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET role = ? WHERE tg_id = ?", (role, tg_id)
        )
        await db.commit()


# ── SUBSCRIPTIONS ───────────────────────────────────────

PLAN_DAYS = {"start": 30, "pro": 30, "elite": 30}
PLAN_LIMITS = {"start": 1, "pro": 5, "elite": 9999}
PLAN_PRICES = {"start": 1900, "pro": 4900, "elite": 12900}
PLAN_LABELS = {"start": "Старт", "pro": "Pro", "elite": "Elite"}


async def get_active_subscription(tg_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM subscriptions "
            "WHERE tg_id = ? AND is_active = 1 AND expires_at > ? "
            "ORDER BY expires_at DESC LIMIT 1",
            (tg_id, datetime.utcnow().isoformat())
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create_subscription(tg_id: int, plan: str) -> dict:
    from datetime import timedelta
    now = datetime.utcnow()
    expires = now + timedelta(days=PLAN_DAYS.get(plan, 30))
    async with aiosqlite.connect(DB_PATH) as db:
        # деактивируем старые
        await db.execute(
            "UPDATE subscriptions SET is_active = 0 WHERE tg_id = ?", (tg_id,)
        )
        await db.execute(
            "INSERT INTO subscriptions (tg_id, plan, started_at, expires_at, is_active) "
            "VALUES (?, ?, ?, ?, 1)",
            (tg_id, plan, now.isoformat(), expires.isoformat())
        )
        await db.commit()
    return {"plan": plan, "expires_at": expires.strftime("%d.%m.%Y")}


async def get_property_count(realtor_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM properties "
            "WHERE realtor_id = ? AND status IN ('pending','approved')",
            (realtor_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


# ── PROPERTIES ──────────────────────────────────────────

async def create_property(data: dict) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO properties "
            "(realtor_id, title, region, city, yield_pct, min_entry, goal_amount, "
            " deadline, description, phone, email, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (
                data["realtor_id"], data["title"], data["region"], data["city"],
                data["yield_pct"], data["min_entry"], data["goal_amount"],
                data["deadline"], data["description"], data["phone"], data["email"],
                datetime.utcnow().isoformat()
            )
        )
        await db.commit()
        return cur.lastrowid


async def get_property(prop_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT p.*, u.full_name as realtor_name, u.username as realtor_username "
            "FROM properties p JOIN users u ON p.realtor_id = u.tg_id "
            "WHERE p.id = ?", (prop_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_pending_properties() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT p.*, u.full_name as realtor_name "
            "FROM properties p JOIN users u ON p.realtor_id = u.tg_id "
            "WHERE p.status = 'pending' ORDER BY p.created_at"
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_realtor_properties(realtor_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM properties WHERE realtor_id = ? ORDER BY created_at DESC",
            (realtor_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def approve_property(prop_id: int, moderator_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.utcnow().isoformat()
        await db.execute(
            "UPDATE properties SET status = 'approved', approved_at = ? WHERE id = ?",
            (now, prop_id)
        )
        await db.execute(
            "INSERT INTO moderation_log (property_id, moderator_id, action, acted_at) "
            "VALUES (?, ?, 'approved', ?)",
            (prop_id, moderator_id, now)
        )
        await db.commit()
    return True


async def reject_property(prop_id: int, moderator_id: int, reason: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.utcnow().isoformat()
        await db.execute(
            "UPDATE properties SET status = 'rejected', reject_reason = ? WHERE id = ?",
            (reason, prop_id)
        )
        await db.execute(
            "INSERT INTO moderation_log (property_id, moderator_id, action, comment, acted_at) "
            "VALUES (?, ?, 'rejected', ?, ?)",
            (prop_id, moderator_id, reason, now)
        )
        await db.commit()
    return True


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async def count(sql, params=()):
            async with db.execute(sql, params) as c:
                r = await c.fetchone()
                return r[0] if r else 0

        return {
            "total_users":     await count("SELECT COUNT(*) FROM users"),
            "investors":       await count("SELECT COUNT(*) FROM users WHERE role='investor'"),
            "realtors":        await count("SELECT COUNT(*) FROM users WHERE role='realtor'"),
            "properties_total":await count("SELECT COUNT(*) FROM properties"),
            "pending":         await count("SELECT COUNT(*) FROM properties WHERE status='pending'"),
            "approved":        await count("SELECT COUNT(*) FROM properties WHERE status='approved'"),
            "subs_start":      await count("SELECT COUNT(*) FROM subscriptions WHERE plan='start' AND is_active=1"),
            "subs_pro":        await count("SELECT COUNT(*) FROM subscriptions WHERE plan='pro' AND is_active=1"),
            "subs_elite":      await count("SELECT COUNT(*) FROM subscriptions WHERE plan='elite' AND is_active=1"),
        }
