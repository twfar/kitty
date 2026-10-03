from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI, Request

from app.core.config import settings
from app.database.database import close_database
from app.services.rollypay_client import RollyPayClient
from app.services.xui_client import XuiClient


@asynccontextmanager
async def lifespan(
    application: FastAPI,
) -> AsyncIterator[None]:
    """Управляет ресурсами приложения."""

    http_session = aiohttp.ClientSession()
    application.state.http_session = http_session

    try:
        yield
    finally:
        await http_session.close()
        await close_database()


def get_http_session(
    request: Request,
) -> aiohttp.ClientSession:
    """Возвращает общую HTTP-сессию приложения."""

    session = request.app.state.http_session

    if not isinstance(session, aiohttp.ClientSession):
        raise RuntimeError("HTTP session is not initialized")

    return session


def get_xui_client(request: Request) -> XuiClient:
    """Создаёт XuiClient поверх общей HTTP-сессии."""

    return XuiClient(
        session=get_http_session(request),
        settings=settings,
    )


def get_rollypay_client(
    request: Request,
) -> RollyPayClient:
    """Создаёт RollyPayClient поверх общей HTTP-сессии."""

    return RollyPayClient(
        session=get_http_session(request),
        settings=settings,
    )


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    """Проверяет доступность процесса."""

    return {"status": "ok"}
