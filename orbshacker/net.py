"""
net.py – Shared HTTP helpers.
"""

import requests

from . import config
from .errors import NetworkError


def fetch_json(url: str, headers: dict = None, params: dict = None, timeout: int = None) -> object:
    """GET *url* and return parsed JSON. Raises NetworkError on failure."""
    try:
        resp = requests.get(
            url,
            headers=headers or {},
            params=params or {},
            timeout=timeout or config.REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise NetworkError(f"Request to {url} failed: {exc}") from exc
