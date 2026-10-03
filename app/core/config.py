from functools import lru_cache

from pydantic import Field, PositiveInt, SecretStr
from pydantic.networks import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация приложения из переменных окружения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "kitty-vpn"
    debug: bool = False
    bot_token: SecretStr
    admin_id: int = Field(gt=0)
    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    xui_base_url: AnyHttpUrl
    xui_api_token: SecretStr
    xui_inbound_ids: list[int] = Field(
        default_factory=lambda: [8, 31, 35, 39, 41]
    )
    xui_timeout_seconds: PositiveInt = 15

    trial_hours: PositiveInt = 24
    paid_subscription_days: PositiveInt = 30
    device_limit: PositiveInt = 3
    test_user_tg_id: int = 8772456974
    broadcast_delay: float = 0.06
    taskiq_queue_name: str = "kitty:broadcasts"
    subscription_base_url: AnyHttpUrl

    rollypay_base_url: AnyHttpUrl = "https://rollypay.io"
    rollypay_api_key: SecretStr
    rollypay_timeout_seconds: PositiveInt = 15
    rollypay_test: bool = True
    rollypay_default_price: int = 80
    rollypay_default_days: PositiveInt = 30
    rollypay_signing_secret: SecretStr | None = None

    webhook_base_url: AnyHttpUrl
    telegram_webhook_secret: SecretStr | None = None
    telegram_webhook_path: str = "/telegram/webhook"
    rollypay_webhook_path: str = "/rollypay/webhook"

    @property
    def telegram_webhook_url(self) -> str:
        """Возвращает полный URL webhook Telegram."""

        return (
            f"{str(self.webhook_base_url).rstrip('/')}"
            f"{self.telegram_webhook_path}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Возвращает единый объект настроек."""

    return Settings()


settings = get_settings()
