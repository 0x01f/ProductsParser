from __future__ import annotations

import time
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def create_session(user_agent: Optional[str] = None, total_retries: int = 5) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent or DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
        }
    )

    retry = Retry(
        total=total_retries,
        backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def fetch_html(
    url: str,
    session: Optional[requests.Session] = None,
    timeout_seconds: int = 15,
    pause_seconds: float = 0.0,
) -> tuple[str, str]:
    """
    Fetch HTML document. Returns (final_url, html_text).
    Raises requests.HTTPError for non-200 responses.
    """
    sess = session or create_session()
    if pause_seconds > 0:
        time.sleep(pause_seconds)
    response = sess.get(url, timeout=timeout_seconds, allow_redirects=True)
    response.raise_for_status()
    return response.url, response.text

