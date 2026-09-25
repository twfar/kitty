import uuid
import aiohttp

BASE_URL = "https://rollypay.io"


async def create_payment(api_key, amount, tg_id, days, test, devices=3, months=1):
    order_id = f"kitty_{tg_id}_{uuid.uuid4().hex[:12]}"
    payload = {
        "amount": f"{amount:.2f}",
        "payment_currency": "RUB",
        "order_id": order_id,
        "description": f"kitty vpn — {days} дней",
        "metadata": {
            "tg_id": str(tg_id),
            "days": str(days),
            "devices": str(devices),
            "months": str(months),
        },
        "test": test,
    }
    headers = {
        "X-API-Key": api_key,
        "X-Nonce": str(uuid.uuid4()),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    timeout = aiohttp.ClientTimeout(total=15)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            f"{BASE_URL}/api/v1/payments",
            json=payload,
            headers=headers,
        ) as response:
            data = await response.json(content_type=None)
            if response.status >= 400 or not data.get("payment_id") or not data.get("pay_url"):
                raise RuntimeError(f"rollypay api error: {data}")
            return data
