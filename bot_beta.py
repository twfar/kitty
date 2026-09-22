# beta branch of bot functionality
#
# this file is intentionally separate from the stable bot.py.
# promo/referral logic is designed to be integrated and tested here first.

import time
from urllib.parse import quote

from db_beta import (
    create_promo,
    create_referral,
    get_promo,
    mark_referral_rewarded,
    use_promo,
)
from xui import find_client_by_sub_id, renew_client_by_sub_id


REFERRAL_REWARD_DAYS = 7
REFERRAL_START_PREFIX = "ref_"


def make_referral_payload(tg_id: int) -> str:
    return f"{REFERRAL_START_PREFIX}{tg_id}"


def parse_referral_payload(payload: str | None):
    if not payload or not payload.startswith(REFERRAL_START_PREFIX):
        return None

    raw_id = payload[len(REFERRAL_START_PREFIX):]

    try:
        return int(raw_id)
    except ValueError:
        return None


async def register_referral(referred_id: int, payload: str | None):
    referrer_id = parse_referral_payload(payload)

    if not referrer_id or referrer_id == referred_id:
        return None

    await create_referral(
        referrer_id=referrer_id,
        referred_id=referred_id,
        created_at=int(time.time()),
    )

    return referrer_id


def promo_is_available(promo, tg_id: int) -> tuple[bool, str]:
    if not promo:
        return False, "промокод не найден"

    if not promo["enabled"]:
        return False, "промокод отключён"

    if promo["expires_at"] and promo["expires_at"] < int(time.time()):
        return False, "срок действия промокода истёк"

    if promo["max_uses"] and promo["used_count"] >= promo["max_uses"]:
        return False, "лимит активаций исчерпан"

    return True, ""


async def redeem_promo(
    tg_id: int,
    code: str,
    sub_id: str,
):
    code = code.strip().upper()
    promo = await get_promo(code)

    ok, reason = promo_is_available(promo, tg_id)
    if not ok:
        return False, reason, 0

    client = find_client_by_sub_id(sub_id)
    if not client:
        return False, "подписка не найдена", 0

    reward_days = int(promo["reward_days"])
    if reward_days <= 0:
        return False, "у промокода не задана награда", 0

    # сначала фиксируем использование кода, чтобы один telegram id
    # не смог активировать один и тот же код повторно.
    used = await use_promo(
        code=code,
        tg_id=tg_id,
        used_at=int(time.time()),
    )

    if not used:
        return False, "ты уже использовал этот промокод", 0

    try:
        renew_client_by_sub_id(
            sub_id=sub_id,
            days=reward_days,
        )
    except Exception:
        raise

    return True, "промокод активирован", reward_days


async def reward_referral_for_paid_user(referred_id: int):
    # интеграционный хук для paid-покупки.
    # получение referrer и начисление награды подключается в bot_beta.py
    # после того, как новая платная подписка подтверждена.
    #
    # награда: +7 дней.
    return REFERRAL_REWARD_DAYS
