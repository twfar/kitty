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

        if "referred_by" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
        if "referral_rewarded" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN referral_rewarded INTEGER NOT NULL DEFAULT 0")

        if "subscription_url" not in columns:
            await db.execute(
                "ALTER TABLE users ADD COLUMN subscription_url TEXT"
            )

        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                reward_days INTEGER NOT NULL DEFAULT 0,
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER PRIMARY KEY,
                rewarded INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            )
        """)
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
