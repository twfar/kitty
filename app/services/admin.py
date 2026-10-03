from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.database.crud import (
    BotSettingRepository,
    PromoCodeRepository,
    UserRepository,
)
from app.database.models import PromoCode, User
from app.services.xui_client import XuiClient


class AdminService:
    """Бизнес-логика кабинета директора."""

    def __init__(
        self,
        *,
        settings: Settings,
        user_repository: UserRepository,
        promo_repository: PromoCodeRepository,
        setting_repository: BotSettingRepository,
        xui_client: XuiClient,
    ) -> None:
        self._settings = settings
        self._users = user_repository
        self._promos = promo_repository
        self._settings_repo = setting_repository
        self._xui = xui_client

    async def create_promo(
        self,
        *,
        code: str,
        reward_days: int,
        max_uses: int,
        expires_in_days: int | None,
    ) -> PromoCode:
        normalized = code.strip().upper()
        if not normalized:
            raise ValueError("код промокода пустой")
        if reward_days <= 0:
            raise ValueError("количество дней должно быть больше нуля")
        if max_uses < 0:
            raise ValueError("лимит не может быть отрицательным")

        if await self._promos.get_by_code(normalized) is not None:
            raise ValueError("такой промокод уже существует")

        expires_at = None
        if expires_in_days is not None:
            if expires_in_days <= 0:
                raise ValueError("срок действия должен быть больше нуля")
            expires_at = datetime.now(timezone.utc) + timedelta(
                days=expires_in_days
            )

        return await self._promos.create(
            code=normalized,
            reward_days=reward_days,
            max_uses=None if max_uses == 0 else max_uses,
            expires_at=expires_at,
        )

    async def list_promos(self) -> list[PromoCode]:
        return await self._promos.get_all()

    async def delete_promo(self, code: str) -> bool:
        promo = await self._promos.get_by_code(code.strip().upper())
        if promo is None:
            return False
        await self._promos.delete(promo)
        return True

    async def set_maintenance(
        self,
        *,
        enabled: bool,
        message: str | None = None,
    ) -> None:
        await self._settings_repo.set(
            "maintenance_enabled",
            "1" if enabled else "0",
        )
        if message is not None:
            await self._settings_repo.set(
                "maintenance_message",
                message.strip(),
            )

    async def get_maintenance(self) -> tuple[bool, str]:
        enabled = await self._settings_repo.get_value(
            "maintenance_enabled",
            "0",
        )
        message = await self._settings_repo.get_value(
            "maintenance_message",
            "🔧 технические работы\n\nбот временно недоступен. попробуй позже.",
        )
        return enabled == "1", message or ""

    async def clear_test_account(self, tg_id: int) -> None:
        await self._xui.delete_client_by_tg_id(tg_id)
        await self._users.delete_by_tg_id(tg_id)

    async def find_user(
        self,
        identifier: str,
    ) -> User | None:
        value = identifier.strip()
        if value.startswith("@"):
            return await self._users.get_by_username(value)
        try:
            return await self._users.get_by_tg_id(int(value))
        except ValueError:
            return None


__all__ = ["AdminService"]
