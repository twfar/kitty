from __future__ import annotations

import time
from urllib.parse import quote

import aiohttp

from app.core.config import Settings
from app.services.base_http_client import BaseHTTPClient


class XuiAPIError(RuntimeError):
    """Ошибка прикладного API 3x-ui."""


class XuiClient(BaseHTTPClient):
    """Асинхронный клиент панели 3x-ui."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        settings: Settings,
    ) -> None:
        super().__init__(
            session,
            base_url=str(settings.xui_base_url),
            timeout_seconds=settings.xui_timeout_seconds,
            client_name="3x-ui",
        )
        self._api_token = settings.xui_api_token.get_secret_value()
        self._subscription_base_url = (
            str(settings.subscription_base_url).rstrip("/")
        )
        self._inbound_ids = settings.xui_inbound_ids

    @property
    def _headers(self) -> dict[str, str]:
        """Возвращает заголовки 3x-ui."""

        return {
            "Authorization": f"Bearer {self._api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _api_request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        response = await self.request(
            method, path, headers=self._headers, json_body=json_body
        )

        if not isinstance(response, dict):
            raise XuiAPIError(
                "3x-ui returned a non-object response"
            )

        if response.get("success") is not True:
            message = response.get("msg")
            raise XuiAPIError(
                message
                if isinstance(message, str) and message
                else "3x-ui API request failed"
            )

        return response

    async def get_client(
        self,
        *,
        email: str | None = None,
        tg_id: int | None = None,
    ) -> dict[str, object] | None:
        """Возвращает клиента по email или Telegram ID."""

        if email is None and tg_id is None:
            raise ValueError("email or tg_id is required")

        if email is not None:
            response = await self._api_request(
                "GET",
                f"/panel/api/clients/get/{quote(email, safe='')}",
            )
            obj = response.get("obj")
            return obj if isinstance(obj, dict) else None

        response = await self._api_request(
            "GET",
            f"/panel/api/clients/get/tgId/{tg_id}",
        )
        obj = response.get("obj")

        if not isinstance(obj, list):
            return None

        for client in obj:
            if isinstance(client, dict):
                return client

        return None

    async def get_inbounds(self) -> list[dict[str, object]]:
        """Возвращает inbound'ы."""

        response = await self._api_request(
            "GET",
            "/panel/api/inbounds/list",
        )
        obj = response.get("obj")

        if not isinstance(obj, list):
            return []

        return [item for item in obj if isinstance(item, dict)]

    async def get_traffic(
        self,
        email: str,
    ) -> dict[str, object] | None:
        """Возвращает статистику трафика."""

        response = await self._api_request(
            "GET",
            f"/panel/api/clients/traffic/{quote(email, safe='')}",
        )
        obj = response.get("obj")
        return obj if isinstance(obj, dict) else None

    async def find_client(
        self,
        email: str,
    ) -> dict[str, object] | None:
        """Ищет клиента по email."""

        for inbound in await self.get_inbounds():
            settings = inbound.get("settings")
            if not isinstance(settings, dict):
                continue

            clients = settings.get("clients")
            if not isinstance(clients, list):
                continue

            for client in clients:
                if (
                    isinstance(client, dict)
                    and client.get("email") == email
                ):
                    return client

        return None

    async def find_client_by_sub_id(
        self,
        sub_id: str,
    ) -> dict[str, object] | None:
        """Ищет клиента по sub_id."""

        for inbound in await self.get_inbounds():
            settings = inbound.get("settings")
            if not isinstance(settings, dict):
                continue

            clients = settings.get("clients")
            if not isinstance(clients, list):
                continue

            for client in clients:
                if (
                    isinstance(client, dict)
                    and client.get("subId") == sub_id
                ):
                    return client

        return None

    def get_subscription_url(
        self,
        sub_id: str,
        *,
        json_mode: bool = False,
    ) -> str:
        """Формирует URL подписки."""

        if not sub_id:
            raise ValueError("sub_id is empty")

        suffix = "jsnn" if json_mode else "s"
        return f"{self._subscription_base_url}/{suffix}/{sub_id}"

    async def create_client(
        self,
        *,
        tg_id: int,
        email: str,
        expiry_hours: int,
        total_gb: int = 0,
        group: str = "trial",
        hwid_limit: int = 1,
    ) -> dict[str, object]:
        """Создаёт клиента."""

        expiry_time = (
            int(time.time() * 1000)
            + expiry_hours * 60 * 60 * 1000
        )

        payload: dict[str, object] = {
            "client": {
                "email": email,
                "enable": True,
                "expiryTime": expiry_time,
                "totalGB": total_gb,
                "tgId": tg_id,
                "limitHwid": hwid_limit,
                "limitIp": 0,
                "reset": 0,
                "resetDay": 0,
                "resetMax": 0,
                "trafficReset": "never",
                "trafficResetDay": 1,
                "flow": "xtls-rprx-vision",
                "security": "auto",
                "comment": "",
                "group": group,
            },
            "inboundIds": self._inbound_ids,
        }

        api_result = await self._api_request(
            "POST",
            "/panel/api/clients/add",
            json_body=payload,
        )

        client = await self.find_client(email)
        if client is None:
            raise XuiAPIError(
                f"client {email} was created but not found"
            )

        sub_id = client.get("subId")
        if not isinstance(sub_id, str) or not sub_id:
            raise XuiAPIError(f"client {email} has no subId")

        return {
            "email": email,
            "tg_id": tg_id,
            "expiry_time": expiry_time,
            "inbound_ids": self._inbound_ids,
            "group": group,
            "flow": "xtls-rprx-vision",
            "sub_id": sub_id,
            "subscription_url": self.get_subscription_url(
                sub_id, json_mode=True
            ),
            "api_result": api_result,
        }

    async def update_client(
        self,
        email: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        """Обновляет клиента."""

        response = await self._api_request(
            "POST",
            f"/panel/api/clients/update/{quote(email, safe='')}",
            json_body=payload,
        )
        obj = response.get("obj")
        return obj if isinstance(obj, dict) else response

    async def get_hwid_devices(
        self,
        email: str,
    ) -> list[dict[str, object]]:
        """Возвращает HWID-устройства."""

        response = await self._api_request(
            "POST",
            f"/panel/api/clients/hwids/{quote(email, safe='')}",
        )
        obj = response.get("obj")

        if not isinstance(obj, list):
            return []

        return [item for item in obj if isinstance(item, dict)]

    async def delete_all_hwid_devices(self, email: str) -> None:
        """Удаляет все HWID-устройства."""

        await self._api_request(
            "DELETE",
            f"/panel/api/clients/hwids/{quote(email, safe='')}",
        )

    async def disable_client(self, email: str) -> bool:
        """Отключает клиента."""

        client = await self.get_client(email=email)
        if client is None:
            return False

        client_data = client.get("client", client)
        if not isinstance(client_data, dict):
            raise XuiAPIError("invalid client payload")

        payload = {
            **client_data,
            "email": client_data.get("email", email),
            "subId": client_data.get("subId"),
            "id": client_data.get("uuid") or client_data.get("id"),
            "limitHwid": 3,
            "enable": False,
        }

        await self.update_client(email, payload)
        return True

    async def renew_client_by_sub_id(
        self,
        sub_id: str,
        *,
        days: int = 30,
        device_limit: int = 3,
    ) -> dict[str, object]:
        """Продлевает подписку."""

        if days <= 0:
            raise ValueError("days must be positive")

        client = await self.find_client_by_sub_id(sub_id)
        if client is None:
            raise XuiAPIError("subscription not found")

        email = client.get("email")
        if not isinstance(email, str) or not email:
            raise XuiAPIError("client email not found")

        client_data = client.get("client", client)
        if not isinstance(client_data, dict):
            raise XuiAPIError("invalid client payload")

        now = int(time.time() * 1000)
        current_expiry = int(client_data.get("expiryTime") or 0)
        expiry_time = max(current_expiry, now) + (
            days * 24 * 60 * 60 * 1000
        )

        payload = {
            **client_data,
            "email": client_data.get("email", email),
            "subId": client_data.get("subId"),
            "id": client_data.get("uuid") or client_data.get("id"),
            "expiryTime": expiry_time,
            "limitHwid": device_limit,
            "group": "paid",
            "enable": True,
        }

        await self.update_client(email, payload)

        updated = await self.find_client(email)
        if updated is None:
            raise XuiAPIError(
                "client disappeared after renewal"
            )

        return updated
