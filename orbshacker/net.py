"""
net.py – Shared HTTP helpers.
"""

from typing import Any, Mapping

import requests

from . import config
from .errors import NetworkError


def fetch_json(
    url: str,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, str] | None = None,
    timeout: int | None = None,
) -> Any:
    """GET *url* and return parsed JSON. Raises NetworkError on failure."""
    try:
        resp = requests.get(
            url,
            headers=dict(headers or {}),
            params=dict(params or {}),
            timeout=config.REQUEST_TIMEOUT if timeout is None else timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise NetworkError(f"Request to {url} failed: {exc}") from exc
