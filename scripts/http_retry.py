"""Small retrying HTTP reader shared by official data importers."""

from __future__ import annotations

import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def read(url: str, headers: dict[str, str], timeout: float = 60, attempts: int = 5) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urlopen(Request(url, headers=headers), timeout=timeout) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as error:
            last_error = error
            if attempt + 1 < attempts:
                retry_after = error.headers.get("Retry-After") if isinstance(error, HTTPError) else None
                time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt)
    raise RuntimeError(f"Failed to fetch {url} after {attempts} attempts: {last_error}")
