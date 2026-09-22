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
