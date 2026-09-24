import hashlib
import hmac
import json
import logging

from aiohttp import web
from aiogram import Bot

from config import BOT_TOKEN, ADMIN_ID, ROLLYPAY_SIGNING_SECRET
from db import (
    get_payment,
    update_payment_status,
    payment_paid_once,
    get_user,
    update_user,
)
from xui import renew_client_by_sub_id


def verify_signature(raw_body, timestamp, signature, secret):
    if not timestamp or not signature or not secret:
        return False

    expected = hmac.new(
        secret.encode(),
        timestamp.encode() + b"." + raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


async def notify_admin(bot, text):
    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception:
        logging.exception("failed to notify admin")


async def webhook(request):
    raw_body = await request.read()

    if not verify_signature(
        raw_body,
        request.headers.get("X-Timestamp", ""),
        request.headers.get("X-Signature", ""),
        ROLLYPAY_SIGNING_SECRET,
    ):
        return web.Response(status=403, text="invalid signature")

    try:
        event = json.loads(raw_body)
    except json.JSONDecodeError:
        return web.Response(status=400, text="invalid json")

    payment_id = event.get("payment_id")
    status = event.get("status")

    if not payment_id or not status:
        return web.Response(status=400, text="missing payment fields")

    payment = await get_payment(payment_id)

    if not payment:
        await notify_admin(
            request.app["bot"],
            f"⚠️ неизвестный платёж\n\n🆔 payment id: {payment_id}",
        )
        return web.Response(status=200, text="ignored")

    if bool(event.get("test", False)) != bool(payment["test"]):
        await notify_admin(
            request.app["bot"],
            f"⚠️ несовпадение test-режима\n\n🆔 payment id: {payment_id}",
        )
        return web.Response(status=400, text="test mode mismatch")

    try:
        event_amount = f"{float(event.get('amount', 0)):.2f}"
        stored_amount = f"{float(payment['amount']):.2f}"
    except (TypeError, ValueError):
        return web.Response(status=400, text="invalid amount")

    if event_amount != stored_amount:
        await notify_admin(
            request.app["bot"],
            f"⚠️ несовпадение суммы\n\n🆔 payment id: {payment_id}",
        )
        return web.Response(status=400, text="amount mismatch")

    if event.get("currency") != payment["currency"]:
        return web.Response(status=400, text="currency mismatch")

    await notify_admin(
        request.app["bot"],
        "📩 webhook rollypay\n\n"
        f"событие: {event.get('event_type', '—')}\n"
        f"статус: {status}\n"
        f"🆔 payment id: {payment_id}\n"
        f"🧪 тест: {'да' if payment['test'] else 'нет'}",
    )

    if status != "paid":
        await update_payment_status(payment_id, status)
        return web.Response(status=200, text="ok")

    if not await payment_paid_once(payment_id):
        return web.Response(status=200, text="already processed")

    user = await get_user(payment["tg_id"])

    if not user or not user["sub_id"]:
        await notify_admin(
            request.app["bot"],
            "❌ оплата получена, но подписка не найдена\n\n"
            f"🆔 telegram id: {payment['tg_id']}\n"
            f"💳 payment id: {payment_id}",
        )
        return web.Response(status=200, text="user not found")

    try:
        updated = renew_client_by_sub_id(
            user["sub_id"],
            int(payment["days"]),
        )
        expires_at = int(updated.get("expiryTime", 0)) // 1000

        await update_user(
            tg_id=user["tg_id"],
            username=user["username"],
            email=user["email"],
            sub_id=user["sub_id"],
            subscription_url=f"https://87.121.82.175:2096/jsnn/{user['sub_id']}",
            status="paid",
            created_at=user["created_at"],
            expires_at=expires_at,
        )
    except Exception:
        logging.exception("failed to renew after payment")
        await notify_admin(
            request.app["bot"],
            "❌ оплата получена, но продление не удалось\n\n"
            f"💳 payment id: {payment_id}\n"
            f"🔗 sub id: {user['sub_id']}",
        )
        return web.Response(status=500, text="renewal failed")

    await request.app["bot"].send_message(
        payment["tg_id"],
        "✅ оплата прошла!\n\n"
        f"🔗 подписка продлена на {payment['days']} дней.",
    )

    await notify_admin(
        request.app["bot"],
        "✅ подписка продлена автоматически\n\n"
        f"👤 telegram id: {payment['tg_id']}\n"
        f"💳 payment id: {payment_id}\n"
        f"🎁 добавлено: {payment['days']} дней\n"
        f"⏳ expires: {expires_at}",
    )

    return web.Response(status=200, text="ok")


async def create_app():
    app = web.Application()
    app["bot"] = Bot(token=BOT_TOKEN)
    app.router.add_post("/rollypay/webhook", webhook)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if not ROLLYPAY_SIGNING_SECRET:
        raise RuntimeError("ROLLYPAY_SIGNING_SECRET is not set")

    web.run_app(
        create_app(),
        host="0.0.0.0",
        port=8443,
    )
