# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""HTTP utility helpers for OpenShell."""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# HTTP status codes that warrant a retry.
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset(
    {429, 500, 502, 503, 504}
)


def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
):
    """Call *func* and retry on transient HTTP errors with exponential backoff.

    The callable *func* must return an object that exposes a ``status_code``
    attribute (e.g. an ``httpx.Response`` or ``requests.Response``).  Retries
    are triggered when the response carries an HTTP 429 or any 5xx status code.

    Parameters
    ----------
    func:
        A zero-argument callable that performs the HTTP request and returns a
        response object with a ``status_code`` attribute.
    max_retries:
        Maximum number of retry attempts after the initial call.  The callable
        is invoked at most ``max_retries + 1`` times in total.  Defaults to
        ``3``.
    base_delay:
        Base delay in seconds used for the exponential backoff calculation.
        The actual wait time for attempt *n* (0-indexed) is::

            base_delay * 2**n + random.uniform(0, 1)

        Defaults to ``1.0``.

    Returns
    -------
    response
        The response object returned by *func* on the first successful call.

    Raises
    ------
    Exception
        Re-raises the last exception raised by *func* after all retries are
        exhausted.  If *func* returned a retryable status code on the final
        attempt rather than raising, that response is returned as-is so the
        caller can inspect it.
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = func()
        except Exception as exc:  # noqa: BLE001
            last_exception = exc
            if attempt == max_retries:
                raise
            wait = base_delay * (2**attempt) + random.uniform(0, 1)
            logger.warning(
                "Retry attempt %d/%d after exception (%s); waiting %.2fs",
                attempt + 1,
                max_retries,
                exc,
                wait,
            )
            time.sleep(wait)
            continue

        if response.status_code not in _RETRYABLE_STATUS_CODES:
            return response

        if attempt == max_retries:
            # Retries exhausted — return the final response to the caller.
            return response

        wait = base_delay * (2**attempt) + random.uniform(0, 1)
        logger.warning(
            "Retry attempt %d/%d after HTTP %d; waiting %.2fs",
            attempt + 1,
            max_retries,
            response.status_code,
            wait,
        )
        time.sleep(wait)

    # Unreachable, but satisfies type checkers.
    if last_exception is not None:
        raise last_exception
