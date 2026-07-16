# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""HTTP utility helpers for OpenShell.

Provides retry logic with exponential backoff for transient HTTP failures.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def _compute_backoff(attempt: int, base_delay: float) -> float:
    """Return exponential backoff delay with uniform jitter.

    Formula: ``base_delay * 2^attempt + random(0, 1)``
    """
    return base_delay * (2 ** attempt) + random.random()  # noqa: S311


# HTTP status codes that are considered retryable
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511})


def retry_with_backoff(
    func: Callable[[], Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> Any:
    """Call *func* and retry on HTTP 429 / 5xx responses using exponential backoff.

    The callable *func* must return a response object that exposes a
    ``status_code`` attribute (e.g. an ``httpx.Response`` or
    ``requests.Response``).  Any exception raised by *func* is treated the
    same as a retryable status code: the call is retried up to *max_retries*
    times before the exception propagates to the caller.

    Args:
        func:        Zero-argument callable that performs the HTTP request and
                     returns a response object.
        max_retries: Maximum number of retry attempts after the initial call
                     fails (default: 3).
        base_delay:  Base delay in seconds used to compute the exponential
                     back-off interval (default: 1.0).

    Returns:
        The response returned by *func* on a successful (non-retryable) call.

    Raises:
        Exception: The last exception raised by *func* after all retry
                   attempts have been exhausted, or a ``RuntimeError`` wrapping
                   the last retryable status code when *func* keeps returning
                   retryable responses without raising.

    Examples:
        >>> import httpx
        >>> response = retry_with_backoff(lambda: httpx.get("https://example.com"))
    """
    for attempt in range(max_retries + 1):
        try:
            response = func()
        except Exception as exc:
            if attempt == max_retries:
                logger.error(
                    "All %d retry attempt(s) exhausted. Raising last exception.",
                    max_retries,
                )
                raise

            wait_time = _compute_backoff(attempt, base_delay)
            logger.warning(
                "Attempt %d/%d failed with exception %r. Retrying in %.2fs.",
                attempt + 1,
                max_retries,
                exc,
                wait_time,
            )
            time.sleep(wait_time)
            continue

        # func() returned a response — check whether the status is retryable.
        if response.status_code not in _RETRYABLE_STATUS_CODES:
            return response

        # Retryable status code.
        if attempt == max_retries:
            logger.error(
                "All %d retry attempt(s) exhausted. Last status code: %d.",
                max_retries,
                response.status_code,
            )
            raise RuntimeError(
                f"HTTP request failed after {max_retries} retries "
                f"(last status code: {response.status_code})"
            )

        wait_time = _compute_backoff(attempt, base_delay)
        logger.warning(
            "Attempt %d/%d received status %d. Retrying in %.2fs.",
            attempt + 1,
            max_retries,
            response.status_code,
            wait_time,
        )
        time.sleep(wait_time)

    # Unreachable — the loop above always either returns or raises.
    raise RuntimeError("Unexpected exit from retry loop")  # pragma: no cover
