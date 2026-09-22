import aiosqlite

from config import DATABASE_PATH


async def init_db_beta():
    async with aiosqlite.connect(DATABASE_PATH) as db:
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

        cursor = await db.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in await cursor.fetchall()}

        if "referred_by" not in columns:
            await db.execute(
                "ALTER TABLE users ADD COLUMN referred_by INTEGER"
            )

        if "referral_rewarded" not in columns:
            await db.execute(
                "ALTER TABLE users ADD COLUMN referral_rewarded INTEGER NOT NULL DEFAULT 0"
            )

        await db.commit()


async def get_promo(code: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM promo_codes WHERE code = ?",
            (code.upper(),),
        )
        return await cursor.fetchone()


async def create_promo(code: str, reward_days: int, max_uses: int, expires_at=None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO promo_codes (
                code, reward_days, max_uses, expires_at, enabled
            )
            VALUES (?, ?, ?, ?, 1)
        """, (code.upper(), reward_days, max_uses, expires_at))
        await db.commit()


async def use_promo(code: str, tg_id: int, used_at: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM promo_uses WHERE code = ? AND tg_id = ?",
            (code.upper(), tg_id),
        )
        if await cursor.fetchone():
            return False

        await db.execute("""
            INSERT INTO promo_uses (code, tg_id, used_at)
            VALUES (?, ?, ?)
        """, (code.upper(), tg_id, used_at))

        await db.execute("""
            UPDATE promo_codes
            SET used_count = used_count + 1
            WHERE code = ?
        """, (code.upper(),))

        await db.commit()
        return True


async def get_referral(referrer_id: int, referred_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM referrals WHERE referrer_id = ? AND referred_id = ?",
            (referrer_id, referred_id),
        )
        return await cursor.fetchone()


async def create_referral(referrer_id: int, referred_id: int, created_at: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO referrals (
                referrer_id, referred_id, rewarded, created_at
            )
            VALUES (?, ?, 0, ?)
        """, (referrer_id, referred_id, created_at))
        await db.commit()


async def mark_referral_rewarded(referred_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE referrals SET rewarded = 1 WHERE referred_id = ?",
            (referred_id,),
        )
        await db.execute(
            "UPDATE users SET referral_rewarded = 1 WHERE tg_id = ?",
            (referred_id,),
        )
        await db.commit()
