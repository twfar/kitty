from __future__ import annotations

import argparse
import asyncio
import logging
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import async_session_factory
from app.database.models import (
    BotSetting,
    DeviceSnapshot,
    NotificationLog,
    Payment,
    PromoCode,
    PromoUse,
    Referral,
    ReferralReward,
    User,
)

LOGGER = logging.getLogger("kitty.migration")


class MigrationError(RuntimeError):
    """Ошибка переноса legacy SQLite -> PostgreSQL."""


def unix_to_utc(value: object | None) -> datetime | None:
    """Конвертирует unix timestamp в timezone-aware UTC datetime."""

    if value is None or value == "":
        return None
    try:
        timestamp = float(value)
    except (TypeError, ValueError) as exc:
        raise MigrationError(f"invalid unix timestamp: {value!r}") from exc
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def required_unix_to_utc(value: object, field_name: str) -> datetime:
    """Конвертирует обязательный unix timestamp."""

    result = unix_to_utc(value)
    if result is None:
        raise MigrationError(f"required timestamp {field_name!r} is empty")
    return result


def row_value(
    row: sqlite3.Row,
    key: str,
    default: object | None = None,
) -> object | None:
    """Безопасно получает поле sqlite row."""

    try:
        return row[key]
    except (IndexError, KeyError):
        return default


def optional_str(value: object | None) -> str | None:
    """Возвращает строковое значение legacy-поля или None."""

    return None if value is None else str(value)


def required_str(value: object | None, field_name: str) -> str:
    """Возвращает обязательное строковое значение legacy-поля."""

    result = optional_str(value)
    if result is None:
        raise MigrationError(f"required field {field_name!r} is empty")
    return result


def as_int(value: object | None, default: int = 0) -> int:
    """Преобразует sqlite-значение в int."""

    if value is None or value == "":
        return default
    return int(value)


def as_bool(value: object | None) -> bool:
    """Преобразует legacy integer flag в bool."""

    return bool(as_int(value))


def as_decimal(value: object) -> Decimal:
    """Преобразует legacy numeric/text amount в Decimal."""

    try:
        return Decimal(str(value))
    except Exception as exc:
        raise MigrationError(f"invalid decimal value: {value!r}") from exc


def read_rows(connection: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    """Читает таблицу legacy SQLite."""

    cursor = connection.execute(f'SELECT * FROM "{table}"')
    return cursor.fetchall()


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    """Проверяет наличие legacy-таблицы."""

    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def open_sqlite(path: Path) -> sqlite3.Connection:
    """Открывает legacy SQLite в read-only режиме."""

    if not path.is_file():
        raise MigrationError(f"SQLite database not found: {path}")
    connection = sqlite3.connect(
        f"file:{path.resolve()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


async def clear_target(session: AsyncSession) -> None:
    """Очищает целевые таблицы в порядке зависимостей."""

    models = (
        NotificationLog,
        DeviceSnapshot,
        ReferralReward,
        PromoUse,
        Payment,
        Referral,
        BotSetting,
        PromoCode,
        User,
    )
    for model in models:
        await session.execute(delete(model))
    await session.flush()


async def migrate(sqlite_path: Path) -> None:
    """Полностью переносит legacy SQLite в PostgreSQL одной транзакцией."""

    connection = open_sqlite(sqlite_path)
    try:
        required_tables = (
            "users",
            "promo_codes",
            "promo_uses",
            "payments",
            "referrals",
            "referral_rewards",
            "bot_settings",
            "notification_blocked_users",
            "notification_log",
            "device_snapshots",
        )
        missing = [
            table for table in required_tables
            if not table_exists(connection, table)
        ]
        if missing:
            raise MigrationError(
                f"legacy tables are missing: {', '.join(missing)}"
            )

        users = read_rows(connection, "users")
        blocked_rows = read_rows(
            connection,
            "notification_blocked_users",
        )
        blocked_ids = {
            as_int(row_value(row, "tg_id"))
            for row in blocked_rows
        }

        async with async_session_factory() as session:
            async with session.begin():
                await clear_target(session)

                user_by_tg_id: dict[int, User] = {}
                for row in users:
                    tg_id = as_int(row_value(row, "tg_id"))
                    created_at = required_unix_to_utc(
                        row_value(row, "created_at"),
                        "users.created_at",
                    )
                    user = User(
                        tg_id=tg_id,
                        username=optional_str(
                            row_value(row, "username")
                        ),
                        email=optional_str(
                            row_value(row, "email")
                        ),
                        sub_id=optional_str(
                            row_value(row, "sub_id")
                        ),
                        subscription_url=optional_str(
                            row_value(row, "subscription_url")
                        ),
                        status=str(
                            row_value(row, "status", "new")
                        ),
                        created_at=created_at,
                        updated_at=created_at,
                        expires_at=unix_to_utc(
                            row_value(row, "expires_at")
                        ),
                        is_blocked=tg_id in blocked_ids,
                    )
                    session.add(user)
                    user_by_tg_id[tg_id] = user
                await session.flush()

                # blocked users may exist only in the dedicated
                # legacy table. create a minimal user record so
                # the block is not lost.
                for row in blocked_rows:
                    tg_id = as_int(row_value(row, "tg_id"))
                    if tg_id in user_by_tg_id:
                        continue
                    blocked_at = required_unix_to_utc(
                        row_value(row, "blocked_at"),
                        "notification_blocked_users.blocked_at",
                    )
                    user = User(
                        tg_id=tg_id,
                        username=optional_str(
                            row_value(row, "username")
                        ),
                        status="new",
                        created_at=blocked_at,
                        updated_at=blocked_at,
                        is_blocked=True,
                    )
                    session.add(user)
                    user_by_tg_id[tg_id] = user
                await session.flush()

                promos = read_rows(connection, "promo_codes")
                promo_by_code: dict[str, PromoCode] = {}
                for row in promos:
                    code = required_str(
                        row_value(row, "code"),
                        "promo_codes.code",
                    )
                    promo = PromoCode(
                        code=code,
                        reward_days=as_int(
                            row_value(row, "reward_days")
                        ),
                        max_uses=as_int(
                            row_value(row, "max_uses")
                        ),
                        uses_count=as_int(
                            row_value(row, "used_count")
                        ),
                        is_active=as_bool(
                            row_value(row, "enabled", 1)
                        ),
                        expires_at=unix_to_utc(
                            row_value(row, "expires_at")
                        ),
                    )
                    session.add(promo)
                    promo_by_code[code] = promo
                await session.flush()

                payments = read_rows(connection, "payments")
                payment_by_legacy_id: dict[str, Payment] = {}
                for row in payments:
                    tg_id = as_int(row_value(row, "tg_id"))
                    user = user_by_tg_id.get(tg_id)
                    if user is None:
                        raise MigrationError(
                            "payment "
                            f"{row_value(row, 'payment_id')!r} "
                            f"references missing user {tg_id}"
                        )
                    payment_id = required_str(
                        row_value(row, "payment_id"),
                        "payments.payment_id",
                    )
                    created_at = required_unix_to_utc(
                        row_value(row, "created_at"),
                        "payments.created_at",
                    )
                    updated_at = (
                        unix_to_utc(
                            row_value(row, "updated_at")
                        )
                        or created_at
                    )
                    payment = Payment(
                        user_id=user.id,
                        external_id=payment_id,
                        amount=as_decimal(
                            row_value(row, "amount")
                        ),
                        currency=str(
                            row_value(row, "currency", "RUB")
                        ),
                        status=str(
                            row_value(row, "status", "created")
                        ),
                        plan=None,
                        days=as_int(
                            row_value(row, "days"),
                            30,
                        ),
                        device_limit=as_int(
                            row_value(row, "device_limit"),
                            3,
                        ),
                        months=as_int(
                            row_value(row, "months"),
                            1,
                        ),
                        test=as_bool(
                            row_value(row, "test")
                        ),
                        payment_url=None,
                        paid_at=None,
                        raw_payload={
                            "legacy_order_id": optional_str(
                                row_value(row, "order_id")
                            )
                        },
                        created_at=created_at,
                        updated_at=updated_at,
                    )
                    session.add(payment)
                    payment_by_legacy_id[payment_id] = payment
                await session.flush()

                promo_uses = read_rows(
                    connection,
                    "promo_uses",
                )
                for row in promo_uses:
                    code = required_str(
                        row_value(row, "code"),
                        "promo_uses.code",
                    )
                    tg_id = as_int(row_value(row, "tg_id"))
                    promo = promo_by_code.get(code)
                    user = user_by_tg_id.get(tg_id)
                    if promo is None or user is None:
                        raise MigrationError(
                            "promo use references missing data: "
                            f"code={code!r}, tg_id={tg_id}"
                        )
                    session.add(
                        PromoUse(
                            promo_code_id=promo.id,
                            user_id=user.id,
                            payment_id=None,
                            used_at=required_unix_to_utc(
                                row_value(row, "used_at"),
                                "promo_uses.used_at",
                            ),
                        )
                    )

                referrals = read_rows(
                    connection,
                    "referrals",
                )
                referral_by_referred_tg_id: dict[
                    int, Referral
                ] = {}
                for row in referrals:
                    referred_id = as_int(
                        row_value(row, "referred_id")
                    )
                    referrer_id = as_int(
                        row_value(row, "referrer_id")
                    )
                    referred_user = user_by_tg_id.get(
                        referred_id
                    )
                    referrer = user_by_tg_id.get(
                        referrer_id
                    )
                    if (
                        referred_user is None
                        or referrer is None
                    ):
                        raise MigrationError(
                            "referral references missing user(s): "
                            f"referrer={referrer_id}, "
                            f"referred={referred_id}"
                        )
                    created_at = required_unix_to_utc(
                        row_value(row, "created_at"),
                        "referrals.created_at",
                    )
                    referral = Referral(
                        referrer_id=referrer.id,
                        referred_user_id=referred_user.id,
                        status="active",
                        created_at=created_at,
                        updated_at=created_at,
                    )
                    session.add(referral)
                    referral_by_referred_tg_id[
                        referred_id
                    ] = referral
                await session.flush()

                rewards = read_rows(
                    connection,
                    "referral_rewards",
                )
                for row in rewards:
                    referred_id = as_int(
                        row_value(row, "referred_id")
                    )
                    referrer_id = as_int(
                        row_value(row, "referrer_id")
                    )
                    referrer = user_by_tg_id.get(
                        referrer_id
                    )
                    if referrer is None:
                        raise MigrationError(
                            "referral reward references "
                            f"missing referrer {referrer_id}"
                        )
                    created_at = required_unix_to_utc(
                        row_value(row, "created_at"),
                        "referral_rewards.created_at",
                    )
                    referral = referral_by_referred_tg_id.get(
                        referred_id
                    )
                    payment = payment_by_legacy_id.get(
                        str(row_value(row, "payment_id"))
                    )
                    reward = ReferralReward(
                        user_id=referrer.id,
                        referral_id=(
                            referral.id
                            if referral
                            else None
                        ),
                        payment_id=(
                            payment.id
                            if payment
                            else None
                        ),
                        # legacy rewards stored days, not money.
                        amount=Decimal("0"),
                        currency="RUB",
                        status=(
                            "applied"
                            if as_bool(
                                row_value(row, "applied")
                            )
                            else "pending"
                        ),
                        reward_days=as_int(
                            row_value(row, "reward_days")
                        ),
                        created_at=created_at,
                        updated_at=created_at,
                    )
                    session.add(reward)

                settings = read_rows(
                    connection,
                    "bot_settings",
                )
                now = datetime.now(timezone.utc)
                for row in settings:
                    session.add(
                        BotSetting(
                            key=required_str(
                                row_value(row, "key"),
                                "bot_settings.key",
                            ),
                            value=str(
                                row_value(row, "value", "")
                            ),
                            created_at=now,
                            updated_at=now,
                        )
                    )

                notification_logs = read_rows(
                    connection,
                    "notification_log",
                )
                for row in notification_logs:
                    tg_id = as_int(
                        row_value(row, "tg_id")
                    )
                    user = user_by_tg_id.get(tg_id)
                    if user is None:
                        LOGGER.warning(
                            "skipping notification log for "
                            "missing user tg_id=%s",
                            tg_id,
                        )
                        continue
                    session.add(
                        NotificationLog(
                            user_id=user.id,
                            notification_type=required_str(
                                row_value(
                                    row,
                                    "notification_type",
                                ),
                                "notification_log.notification_type",
                            ),
                            marker=str(
                                row_value(row, "marker", "")
                            ),
                            status="sent",
                            sent_at=required_unix_to_utc(
                                row_value(row, "sent_at"),
                                "notification_log.sent_at",
                            ),
                        )
                    )

                device_rows = read_rows(
                    connection,
                    "device_snapshots",
                )
                devices_by_tg_id: dict[
                    int, list[dict[str, object]]
                ] = {}
                first_seen_by_tg_id: dict[
                    int, datetime
                ] = {}
                for row in device_rows:
                    tg_id = as_int(
                        row_value(row, "tg_id")
                    )
                    user = user_by_tg_id.get(tg_id)
                    if user is None:
                        LOGGER.warning(
                            "skipping device snapshot for "
                            "missing user tg_id=%s",
                            tg_id,
                        )
                        continue
                    first_seen = required_unix_to_utc(
                        row_value(row, "first_seen"),
                        "device_snapshots.first_seen",
                    )
                    device = {
                        "fingerprint": required_str(
                            row_value(row, "device_key"),
                            "device_snapshots.device_key",
                        ),
                        "deviceModel": optional_str(
                            row_value(row, "device_name")
                        ),
                        "first_seen": first_seen.isoformat(),
                    }
                    devices_by_tg_id.setdefault(
                        tg_id,
                        [],
                    ).append(device)
                    previous = first_seen_by_tg_id.get(
                        tg_id
                    )
                    if (
                        previous is None
                        or first_seen < previous
                    ):
                        first_seen_by_tg_id[tg_id] = (
                            first_seen
                        )

                for tg_id, devices in (
                    devices_by_tg_id.items()
                ):
                    user = user_by_tg_id[tg_id]
                    captured_at = first_seen_by_tg_id[
                        tg_id
                    ]
                    session.add(
                        DeviceSnapshot(
                            user_id=user.id,
                            device_count=len(devices),
                            devices=devices,
                            captured_at=captured_at,
                        )
                    )

                await session.flush()

            LOGGER.info(
                "migration completed: users=%d, promos=%d, "
                "payments=%d, referrals=%d, device_users=%d",
                len(user_by_tg_id),
                len(promos),
                len(payments),
                len(referrals),
                len(devices_by_tg_id),
            )
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    """Разбирает аргументы CLI."""

    parser = argparse.ArgumentParser(
        description=(
            "migrate legacy Kitty VPN SQLite database "
            "to PostgreSQL"
        )
    )
    parser.add_argument(
        "--sqlite",
        type=Path,
        default=Path("bot.db"),
        help=(
            "path to legacy bot.db "
            "(default: ./bot.db)"
        ),
    )
    return parser.parse_args()


async def main() -> None:
    """Точка входа миграции."""

    args = parse_args()
    await migrate(args.sqlite)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(levelname)s "
            "%(name)s: %(message)s"
        ),
    )
    try:
        asyncio.run(main())
    except (MigrationError, OSError) as exc:
        LOGGER.error("migration failed: %s", exc)
        raise SystemExit(1) from exc
