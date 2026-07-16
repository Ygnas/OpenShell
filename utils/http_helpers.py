# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""HTTP helper utilities for OpenShell."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable

import httpx

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {429} | set(range(500, 600))


def retry_with_backoff(
    func: Callable[[], httpx.Response],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> httpx.Response:
    """Call *func* and retry on retryable HTTP status codes with exponential backoff.

    Retries are triggered when the response status code is 429 (Too Many
    Requests) or any 5xx server error.  Between each attempt the helper
    waits ``base_delay * 2 ** attempt + random(0, 1)`` seconds (exponential
    backoff with jitter).

    Args:
        func: A zero-argument callable that performs an HTTP request and
            returns an :class:`httpx.Response`.
        max_retries: Maximum number of retry attempts after the initial
            call.  Defaults to ``3``.
        base_delay: Base delay in seconds used to compute the exponential
            back-off interval.  Defaults to ``1.0``.

    Returns:
        The :class:`httpx.Response` returned by *func* on success.

    Raises:
        httpx.HTTPStatusError: Re-raises when all retries are exhausted and
            the last failure was a retryable HTTP status code.
        httpx.TransportError: Re-raises when all retries are exhausted and
            the last failure was a transport-level error.
    """
    last_exception: httpx.HTTPStatusError | httpx.TransportError | None = None

    for attempt in range(max_retries + 1):
        try:
            response = func()
            if response.status_code not in _RETRYABLE_STATUS_CODES:
                return response

            last_exception = httpx.HTTPStatusError(
                f"HTTP {response.status_code}",
                request=response.request,
                response=response,
            )

        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            last_exception = exc

        if attempt == max_retries:
            break

        wait = base_delay * (2**attempt) + random.random()  # noqa: S311
        logger.warning(
            "Retry attempt %d/%d after %.2fs (reason: %s)",
            attempt + 1,
            max_retries,
            wait,
            last_exception,
        )
        time.sleep(wait)

    raise last_exception  # type: ignore[misc]
