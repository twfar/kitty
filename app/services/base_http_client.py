from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class BaseHTTPClientError(RuntimeError):
    """Базовая ошибка HTTP-клиента."""


class HTTPTransportError(BaseHTTPClientError):
    """Ошибка транспорта или таймаута."""


class HTTPResponseError(BaseHTTPClientError):
    """Внешний API вернул HTTP 4xx/5xx."""


class HTTPJSONError(BaseHTTPClientError):
    """Внешний API вернул некорректный JSON."""


class BaseHTTPClient:
    """Асинхронный HTTP-клиент поверх общей ClientSession."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        base_url: str,
        timeout_seconds: float,
        client_name: str,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._client_name = client_name

    def _build_url(self, path: str) -> str:
        """Собирает полный URL."""

        if path.startswith(("http://", "https://")):
            return path
        return f"{self._base_url}/{path.lstrip('/')}"

    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        json_body: Any = None,
    ) -> object | None:
        """Выполняет запрос и декодирует JSON."""

        url = self._build_url(path)
        logger.debug("%s -> %s %s", self._client_name, method, url)

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=self._timeout,
            ) as response:
                body = await response.text()
                logger.debug(
                    "%s <- %s %s",
                    self._client_name,
                    response.status,
                    url,
                )

                if response.status >= 400:
                    raise HTTPResponseError(
                        f"{self._client_name}: HTTP "
                        f"{response.status}: {body[:1000]}"
                    )

                if not body:
                    return None

                try:
                    return json.loads(body)
                except json.JSONDecodeError as exc:
                    raise HTTPJSONError(
                        f"{self._client_name}: invalid JSON"
                    ) from exc

        except aiohttp.ClientError as exc:
            logger.exception(
                "%s transport error: %s %s",
                self._client_name,
                method,
                url,
            )
            raise HTTPTransportError(
                f"{self._client_name}: request failed"
            ) from exc
        except TimeoutError as exc:
            logger.exception(
                "%s timeout: %s %s",
                self._client_name,
                method,
                url,
            )
            raise HTTPTransportError(
                f"{self._client_name}: request timed out"
            ) from exc
