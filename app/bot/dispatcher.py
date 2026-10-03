from __future__ import annotations

from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from app.bot.middlewares.database import DatabaseSessionMiddleware
from app.bot.middlewares.dependencies import DependenciesMiddleware
from app.bot.middlewares.maintenance import MaintenanceMiddleware
from app.bot.runtime import BotRuntime

from app.bot.handlers.admin import router as admin_router
from app.bot.handlers.user import router as user_router


def create_dispatcher(runtime: BotRuntime) -> Dispatcher:
    """Создаёт и настраивает главный Dispatcher бота."""

    storage = RedisStorage.from_url(runtime.settings.redis_url)
    dispatcher = Dispatcher(storage=storage)

    dispatcher.update.middleware(DatabaseSessionMiddleware(runtime.session_factory))
    dispatcher.update.middleware(
        DependenciesMiddleware(runtime.settings, runtime.http_session)
    )
    dispatcher.update.middleware(MaintenanceMiddleware())

    dispatcher.include_router(admin_router)
    dispatcher.include_router(user_router)

    # следующие зоны подключим после их реализации:
    # from app.bot.handlers.payments import router as payments_router
    # from app.bot.handlers.admin import router as admin_router
    # dispatcher.include_router(payments_router)
    # dispatcher.include_router(admin_router)

    return dispatcher
