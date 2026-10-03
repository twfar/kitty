from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import Settings
from app.database.crud import UserRepository
from app.database.models import User
from app.services.xui_client import XuiAPIError, XuiClient


class SubscriptionError(RuntimeError):
    """Ошибка бизнес-логики подписки."""


class SubscriptionService:
    """Бизнес-логика VPN-подписок."""

    def __init__(
        self,
        user_repository: UserRepository,
        xui_client: XuiClient,
        settings: Settings,
    ) -> None:
        self._users = user_repository
        self._xui = xui_client
        self._settings = settings

    async def grant_trial(
        self,
        *,
        tg_id: int,
        username: str | None,
    ) -> User:
        """Выдаёт trial и сохраняет его в БД."""

        user = await self._users.get_by_tg_id(tg_id)

        if user is not None and user.email:
            existing_client = await self._xui.find_client(user.email)
            if existing_client is not None:
                raise SubscriptionError(
                    "у пользователя уже есть подписка"
                )

        email = f"tg_{tg_id}"

        try:
            client = await self._xui.create_client(
                tg_id=tg_id,
                email=email,
                expiry_hours=self._settings.trial_hours,
                group="trial",
                hwid_limit=1,
            )
        except XuiAPIError as exc:
            raise SubscriptionError(
                "не удалось создать trial в 3x-ui"
            ) from exc

        expires_at = datetime.fromtimestamp(
            int(client["expiry_time"]) / 1000,
            tz=timezone.utc,
        )

        if user is None:
            return await self._users.create(
                tg_id=tg_id,
                username=username,
                email=email,
                sub_id=str(client["sub_id"]),
                subscription_url=str(client["subscription_url"]),
                status="trial",
                expires_at=expires_at,
            )

        return await self._users.update_subscription(
            user,
            email=email,
            sub_id=str(client["sub_id"]),
            subscription_url=str(client["subscription_url"]),
            status="trial",
            expires_at=expires_at,
        )

    async def get_subscription_info(
        self,
        user: User,
    ) -> dict[str, object] | None:
        """Синхронизирует и возвращает актуальную информацию о подписке."""

        if not user.email:
            return None

        client = await self._xui.find_client(user.email)
        if client is None:
            return None

        sub_id = client.get("subId")
        expiry_time = client.get("expiryTime")

        if not isinstance(sub_id, str) or not sub_id:
            return None
        if not isinstance(expiry_time, int):
            return None

        expires_at = datetime.fromtimestamp(
            expiry_time / 1000,
            tz=timezone.utc,
        )
        subscription_url = self._xui.get_subscription_url(
            sub_id,
            json_mode=True,
        )

        await self._users.update_subscription(
            user,
            email=user.email,
            sub_id=sub_id,
            subscription_url=subscription_url,
            status=user.status,
            expires_at=expires_at,
        )

        devices = await self._xui.get_hwid_devices(user.email)

        return {
            "status": user.status,
            "expires_at": expires_at,
            "subscription_url": subscription_url,
            "client": client,
            "devices": devices,
            "device_limit": int(client.get("limitHwid") or 0),
        }

    async def get_devices(
        self,
        user: User,
    ) -> tuple[list[dict[str, object]], int] | None:
        """Возвращает устройства и лимит подписки."""

        if not user.email:
            return None

        client = await self._xui.find_client(user.email)
        if client is None:
            return None

        devices = await self._xui.get_hwid_devices(user.email)
        limit = int(client.get("limitHwid") or 0)

        return devices, limit

    async def delete_all_devices(self, user: User) -> bool:
        """Удаляет все HWID-устройства пользователя."""

        if not user.email:
            return False

        client = await self._xui.find_client(user.email)
        if client is None:
            return False

        await self._xui.delete_all_hwid_devices(user.email)
        return True
