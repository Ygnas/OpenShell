# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""HTTP utility helpers for the OpenShell SDK."""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)

# HTTP status codes that warrant a retry
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset(
    {429, 500, 501, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511}
)


def retry_with_backoff(
    func: Callable[[], "httpx.Response"],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> "httpx.Response":
    """Call *func* and retry on HTTP 429 / 5xx responses using exponential backoff.

    Each retry waits ``base_delay * 2 ** attempt + random(0, 1)`` seconds
    before the next attempt, where *attempt* is zero-indexed.

    Args:
        func: A zero-argument callable that performs an HTTP request and
            returns an ``httpx.Response``.  It may also raise an exception
            (e.g. ``httpx.RequestError``), which is treated the same as a
            retryable status code.
        max_retries: Maximum number of retry attempts after the initial call
            (default: 3, meaning up to 4 total calls).
        base_delay: Base delay in seconds used for the exponential backoff
            formula (default: 1.0).

    Returns:
        The ``httpx.Response`` returned by *func* on the first successful
        (non-429, non-5xx) call.

    Raises:
        Exception: The last exception raised by *func* after all retry
            attempts are exhausted.  If the final attempt returned a
            retryable HTTP status code rather than raising, the response
            is returned as-is so the caller can inspect it.
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = func()
        except Exception as exc:  # noqa: BLE001
            last_exception = exc
            if attempt == max_retries:
                raise
            wait = base_delay * (2**attempt) + random.random()
            logger.warning(
                "HTTP request raised %s on attempt %d/%d; retrying in %.2fs",
                type(exc).__name__,
                attempt + 1,
                max_retries + 1,
                wait,
            )
            time.sleep(wait)
            continue

        if response.status_code not in _RETRYABLE_STATUS_CODES:
            return response

        if attempt == max_retries:
            # Exhausted retries — return the last response so the caller
            # can decide how to handle it.
            return response

        wait = base_delay * (2**attempt) + random.random()
        logger.warning(
            "HTTP request returned status %d on attempt %d/%d; retrying in %.2fs",
            response.status_code,
            attempt + 1,
            max_retries + 1,
            wait,
        )
        time.sleep(wait)

    # Unreachable, but satisfies type checkers.
    if last_exception is not None:
        raise last_exception
    raise RuntimeError("retry_with_backoff exhausted retries without a result")
