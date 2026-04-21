import time
import logging
from typing import Any, Optional
import requests
from requests.exceptions import RequestException

from .config import MAX_HTTP_RETRIES, TIMEOUT_SECONDS, RATE_LIMIT_DELAY

log = logging.getLogger(__name__)


def get(url: str, params: dict | None = None, headers: dict | None = None) -> Optional[Any]:
    """
    Perform an HTTP GET with retries and backoff.

    Args:
        url: Endpoint URL
        params: Query parameters
        headers: Optional headers
    Returns:
        Parsed JSON response, or None on failure.
    """
    retries = MAX_HTTP_RETRIES
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=TIMEOUT_SECONDS
            )
            response.raise_for_status()
            log.info(f"GET {url} succeeded (attempt {attempt}/{retries})")
            return response.json()
        except RequestException as e:
            status = getattr(e.response, 'status_code', 'N/A')
            log.warning(
                f"GET {url} failed (attempt {attempt}/{retries}): {e} [status={status}]"
            )
            if attempt == retries:
                log.error(f"All retries failed for {url}")
                return None
            # Incremental backoff
            time.sleep(RATE_LIMIT_DELAY * attempt)
    return None
