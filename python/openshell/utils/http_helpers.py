# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""HTTP utility helpers for the OpenShell SDK."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)

_R = TypeVar("_R", bound="httpx.Response")

#: HTTP status codes that warrant a retry.
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset(
    [429, 500, 502, 503, 504, 505, 506, 507, 508, 510, 511]
)


def retry_with_backoff(
    func: Callable[[], _R],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> _R:
    """Call *func* and retry on transient HTTP errors with exponential backoff.

    Retries are triggered when the response carries an HTTP 429 (Too Many
    Requests) or any 5xx status code.  After exhausting all attempts the last
    exception is re-raised so callers can handle it explicitly.

    Args:
        func: Zero-argument callable that performs the HTTP request and returns
            an :class:`httpx.Response`.  Any exception raised by *func* is
            propagated immediately without retrying (only status-code-based
            retries are performed).
        max_retries: Maximum number of retry attempts.  The initial call is not
            counted, so the callable is invoked at most ``max_retries + 1``
            times.  Defaults to ``3``.
        base_delay: Base delay in seconds used to compute the exponential
            back-off interval.  The wait time for attempt *n* (0-indexed) is
            ``base_delay * (2**n + random(0, 1))``.  Defaults to ``1.0``.

    Returns:
        The :class:`httpx.Response` returned by *func* on a successful
        (non-retryable) call.

    Raises:
        Exception: The exception from the final failed attempt after all
            retries are exhausted.

    Example::

        import httpx
        from openshell.utils.http_helpers import retry_with_backoff

        client = httpx.Client()
        response = retry_with_backoff(lambda: client.get("https://example.com/api"))
        response.raise_for_status()
    """
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = func()
        except Exception:  # noqa: BLE001
            raise

        if response.status_code not in _RETRYABLE_STATUS_CODES:
            return response

        # Build a synthetic exception so the final raise has a useful message.
        last_exc = RuntimeError(
            f"HTTP {response.status_code} response (attempt {attempt + 1}/{max_retries + 1})"
        )

        if attempt < max_retries:
            wait = base_delay * (2**attempt + random.random())  # noqa: S311
            logger.warning(
                "Retrying after HTTP %s (attempt %d/%d, waiting %.2fs)",
                response.status_code,
                attempt + 1,
                max_retries + 1,
                wait,
            )
            time.sleep(wait)

    # All attempts exhausted — re-raise the last recorded exception.
    assert last_exc is not None  # guaranteed: max_retries >= 0
    raise last_exc
