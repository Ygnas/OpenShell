# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from openshell.utils.http_helpers import retry_with_backoff


def _response(status_code: int) -> SimpleNamespace:
    """Return a lightweight stand-in for httpx.Response."""
    r = SimpleNamespace()
    r.status_code = status_code
    return r


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------


def test_returns_response_on_first_success() -> None:
    resp = _response(200)
    func = MagicMock(return_value=resp)

    result = retry_with_backoff(func, max_retries=3, base_delay=0.0)

    assert result is resp
    func.assert_called_once()


def test_returns_response_on_non_retryable_4xx() -> None:
    resp = _response(404)
    func = MagicMock(return_value=resp)

    result = retry_with_backoff(func, max_retries=3, base_delay=0.0)

    assert result is resp
    func.assert_called_once()


# ---------------------------------------------------------------------------
# Retry paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
def test_retries_on_retryable_status_then_succeeds(status_code: int) -> None:
    ok_resp = _response(200)
    fail_resp = _response(status_code)
    # Fail twice, then succeed
    func = MagicMock(side_effect=[fail_resp, fail_resp, ok_resp])

    with patch("openshell.utils.http_helpers.time.sleep"):
        result = retry_with_backoff(func, max_retries=3, base_delay=0.0)

    assert result is ok_resp
    assert func.call_count == 3


def test_raises_after_exhausting_retries() -> None:
    fail_resp = _response(503)
    func = MagicMock(return_value=fail_resp)

    with patch("openshell.utils.http_helpers.time.sleep"), pytest.raises(
        RuntimeError, match="HTTP 503"
    ):
        retry_with_backoff(func, max_retries=2, base_delay=0.0)

    # Initial call + 2 retries = 3 total
    assert func.call_count == 3


def test_raises_after_exhausting_retries_on_429() -> None:
    fail_resp = _response(429)
    func = MagicMock(return_value=fail_resp)

    with patch("openshell.utils.http_helpers.time.sleep"), pytest.raises(
        RuntimeError, match="HTTP 429"
    ):
        retry_with_backoff(func, max_retries=3, base_delay=0.0)

    assert func.call_count == 4  # 1 initial + 3 retries


# ---------------------------------------------------------------------------
# Backoff timing
# ---------------------------------------------------------------------------


def test_sleep_is_called_between_retries() -> None:
    fail_resp = _response(500)
    ok_resp = _response(200)
    func = MagicMock(side_effect=[fail_resp, ok_resp])

    with patch("openshell.utils.http_helpers.time.sleep") as mock_sleep, patch(
        "openshell.utils.http_helpers.random.random", return_value=0.5
    ):
        retry_with_backoff(func, max_retries=3, base_delay=2.0)

    # Attempt 0: wait = 2.0 * 2^0 + 0.5 = 2.5
    mock_sleep.assert_called_once()
    args, _ = mock_sleep.call_args
    assert abs(args[0] - 2.5) < 1e-9


def test_sleep_not_called_on_first_success() -> None:
    func = MagicMock(return_value=_response(200))

    with patch("openshell.utils.http_helpers.time.sleep") as mock_sleep:
        retry_with_backoff(func, max_retries=3, base_delay=1.0)

    mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# Exception propagation
# ---------------------------------------------------------------------------


def test_propagates_exception_from_func_immediately() -> None:
    exc = ConnectionError("network down")
    func = MagicMock(side_effect=exc)

    with pytest.raises(ConnectionError, match="network down"):
        retry_with_backoff(func, max_retries=3, base_delay=0.0)

    # No retries — exception should be raised on the first call
    func.assert_called_once()


# ---------------------------------------------------------------------------
# Default parameters
# ---------------------------------------------------------------------------


def test_default_parameters_succeed_first_try() -> None:
    ok_resp = _response(201)
    func = MagicMock(return_value=ok_resp)

    with patch("openshell.utils.http_helpers.time.sleep"):
        result = retry_with_backoff(func)

    assert result is ok_resp
