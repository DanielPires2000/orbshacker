"""Tests for net.py – HTTP helper error handling (no real network)."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from orbshacker.errors import NetworkError
from orbshacker.net import fetch_json


def _mock_response(payload=None, text="", raise_exc=None):
    resp = MagicMock()
    if raise_exc is not None:
        resp.raise_for_status.side_effect = raise_exc
    resp.json.return_value = payload
    resp.text = text
    return resp


class TestFetchJson:
    def test_returns_parsed_json(self):
        with patch("orbshacker.net.requests.get", return_value=_mock_response({"a": 1})):
            assert fetch_json("https://example.test/x") == {"a": 1}

    def test_request_exception_wrapped_as_network_error(self):
        with patch("orbshacker.net.requests.get",
                   side_effect=requests.ConnectionError("boom")):
            with pytest.raises(NetworkError):
                fetch_json("https://example.test/x")

    def test_http_error_wrapped_as_network_error(self):
        with patch("orbshacker.net.requests.get",
                   return_value=_mock_response(raise_exc=requests.HTTPError("404"))):
            with pytest.raises(NetworkError):
                fetch_json("https://example.test/x")

    def test_invalid_json_wrapped_as_network_error(self):
        resp = _mock_response()
        resp.json.side_effect = ValueError("no json")
        with patch("orbshacker.net.requests.get", return_value=resp):
            with pytest.raises(NetworkError):
                fetch_json("https://example.test/x")

    def test_explicit_timeout_zero_is_respected(self):
        with patch("orbshacker.net.requests.get", return_value=_mock_response([])) as mock_get:
            fetch_json("https://example.test/x", timeout=0)
        assert mock_get.call_args.kwargs["timeout"] == 0

    def test_default_timeout_used_when_omitted(self):
        from orbshacker import config
        with patch("orbshacker.net.requests.get", return_value=_mock_response([])) as mock_get:
            fetch_json("https://example.test/x")
        assert mock_get.call_args.kwargs["timeout"] == config.REQUEST_TIMEOUT

    def test_headers_and_params_forwarded(self):
        with patch("orbshacker.net.requests.get", return_value=_mock_response([])) as mock_get:
            fetch_json("https://example.test/x", headers={"X-A": "1"}, params={"term": "z"})
        assert mock_get.call_args.kwargs["headers"] == {"X-A": "1"}
        assert mock_get.call_args.kwargs["params"] == {"term": "z"}
