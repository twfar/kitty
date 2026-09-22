import aiosqlite

from config import DATABASE_PATH


async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                tg_id INTEGER PRIMARY KEY,
                username TEXT,
                email TEXT UNIQUE,
                sub_id TEXT,
                subscription_url TEXT,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER
            )
        """)

        # миграция старой базы
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = {
            row[1]
            for row in await cursor.fetchall()
        }

        if "sub_id" not in columns:
            await db.execute(
                "ALTER TABLE users ADD COLUMN sub_id TEXT"
            )

        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                reward_days INTEGER NOT NULL,
                max_uses INTEGER NOT NULL DEFAULT 0,
                used_count INTEGER NOT NULL DEFAULT 0,
                expires_at INTEGER,
                enabled INTEGER NOT NULL DEFAULT 1
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_uses (
                code TEXT NOT NULL,
                tg_id INTEGER NOT NULL,
                used_at INTEGER NOT NULL,
                PRIMARY KEY (code, tg_id)
            )
        """)

        if "subscription_url" not in columns:
            await db.execute(
                "ALTER TABLE users ADD COLUMN subscription_url TEXT"
            )

        await db.commit()


async def get_user(tg_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            "SELECT * FROM users WHERE tg_id = ?",
            (tg_id,),
        )

        return await cursor.fetchone()


async def create_user(
    tg_id: int,
    username: str,
    email: str,
    sub_id: str,
    subscription_url: str,
    status: str,
    created_at: int,
    expires_at: int,
):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO users (
                tg_id,
                username,
                email,
                sub_id,
                subscription_url,
                status,
                created_at,
                expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tg_id,
            username,
            email,
            sub_id,
            subscription_url,
            status,
            created_at,
            expires_at,
        ))

        await db.commit()
async def update_user(
    tg_id: int,
    username: str,
    email: str,
    sub_id: str,
    subscription_url: str,
    status: str,
    created_at: int,
    expires_at: int,
):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE users
            SET
                username = ?,
                email = ?,
                sub_id = ?,
                subscription_url = ?,
                status = ?,
                created_at = ?,
                expires_at = ?
            WHERE tg_id = ?
        """, (
            username,
            email,
            sub_id,
            subscription_url,
            status,
            created_at,
            expires_at,
            tg_id,
        ))

        await db.commit()


async def get_promo(code: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM promo_codes WHERE code = ?",
            (code,),
        )
        return await cursor.fetchone()


async def create_promo(
    code: str,
    reward_days: int,
    max_uses: int = 0,
    expires_at: int | None = None,
):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO promo_codes (
                code,
                reward_days,
                max_uses,
                used_count,
                expires_at,
                enabled
            )
            VALUES (?, ?, ?, 0, ?, 1)
            """,
            (code, reward_days, max_uses, expires_at),
        )
        await db.commit()


async def use_promo(code: str, tg_id: int, used_at: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            "SELECT * FROM promo_codes WHERE code = ?",
            (code,),
        )
        promo = await cursor.fetchone()

        if not promo:
            return False

        if not promo["enabled"]:
            return False

        if promo["expires_at"] and promo["expires_at"] < used_at:
            return False

        if promo["max_uses"] > 0 and promo["used_count"] >= promo["max_uses"]:
            return False

        cursor = await db.execute(
            """
            SELECT 1
            FROM promo_uses
            WHERE code = ? AND tg_id = ?
            """,
            (code, tg_id),
        )
        if await cursor.fetchone():
            return False

        await db.execute(
            """
            INSERT INTO promo_uses (code, tg_id, used_at)
            VALUES (?, ?, ?)
            """,
            (code, tg_id, used_at),
        )

        await db.execute(
            """
            UPDATE promo_codes
            SET used_count = used_count + 1
            WHERE code = ?
            """,
            (code,),
        )

        await db.commit()
        return True


async def get_setting(key: str, default=None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO bot_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (key, value),
        )
        await db.commit()


async def delete_setting(key: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM bot_settings WHERE key = ?", (key,))
        await db.commit()
