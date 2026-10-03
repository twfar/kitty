from __future__ import annotations

import uuid
from decimal import Decimal

import aiohttp

from app.core.config import Settings
from app.services.base_http_client import BaseHTTPClient


class RollyPayAPIError(RuntimeError):
    """Ошибка API RollyPay."""


class RollyPayClient(BaseHTTPClient):
    """Асинхронный клиент RollyPay."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        settings: Settings,
    ) -> None:
        super().__init__(
            session,
            base_url=str(settings.rollypay_base_url),
            timeout_seconds=settings.rollypay_timeout_seconds,
            client_name="rollypay",
        )
        self._api_key = (
            settings.rollypay_api_key.get_secret_value()
        )

    async def create_payment(
        self,
        *,
        amount: Decimal,
        tg_id: int,
        days: int,
        test: bool,
        devices: int = 3,
        months: int = 1,
    ) -> dict[str, object]:
        """Создаёт платёж."""

        order_id = (
            f"kitty_{tg_id}_{uuid.uuid4().hex[:12]}"
        )

        payload: dict[str, object] = {
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
            "X-API-Key": self._api_key,
            "X-Nonce": str(uuid.uuid4()),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        response = await self.request(
            "POST",
            "/api/v1/payments",
            headers=headers,
            json_body=payload,
        )

        if not isinstance(response, dict):
            raise RollyPayAPIError(
                "rollypay returned invalid response"
            )

        if not response.get("payment_id"):
            raise RollyPayAPIError(
                f"rollypay api error: {response}"
            )

        if not response.get("pay_url"):
            raise RollyPayAPIError(
                f"rollypay api error: {response}"
            )

        return response
