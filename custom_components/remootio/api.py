"""API client for this integration."""

from __future__ import annotations

import aiohttp


class ApiClient:
    """API client."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
