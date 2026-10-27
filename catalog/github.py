"""A small GitHub client on the standard library, so the nightly job needs no installs.

REST and GraphQL share one token. Code search has its own limit of ten requests
a minute, so those calls are spaced out here rather than retried after a 403.
"""

from __future__ import annotations

import http.client
import json
import logging
import os
import subprocess
import threading
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
USER_AGENT = "ha-bazaar-catalog"

_LOGGER = logging.getLogger(__name__)


class GitHubError(RuntimeError):
    """A request GitHub answered with an error that waiting does not fix."""


def find_token() -> str | None:
    """The token from the environment, else the one the gh CLI is logged in with."""
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        if token := os.environ.get(name):
            return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


class GitHub:
    """REST, GraphQL, code search and plain downloads, with rate limits respected."""

    def __init__(self, token: str | None, code_search_interval: float = 6.5) -> None:
        self._token = token
        self._code_search_interval = code_search_interval
        self._last_code_search = 0.0
        self._lock = threading.Lock()

    def _headers(self, accept: str = "application/vnd.github+json") -> dict[str, str]:
        headers = {"Accept": accept, "User-Agent": USER_AGENT, "X-GitHub-Api-Version": "2022-11-28"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _send(self, request: urllib.request.Request, attempts: int = 6) -> tuple[bytes, dict[str, str]]:
        for attempt in range(attempts):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    return response.read(), dict(response.headers)
            except urllib.error.HTTPError as err:
                wait = self._wait_for(err)
                if wait is None or attempt == attempts - 1:
                    body = err.read()[:300].decode(errors="replace")
                    raise GitHubError(f"{err.code} {request.full_url}: {body}") from err
                _LOGGER.warning("GitHub said %s, waiting %.0f s", err.code, wait)
                time.sleep(wait)
            except (urllib.error.URLError, http.client.HTTPException, OSError) as err:
                # A dropped connection or a cut-off body (RemoteDisconnected,
                # IncompleteRead, ConnectionResetError) is worth another try.
                if attempt == attempts - 1:
                    raise GitHubError(f"{request.full_url}: {err!r}") from err
                time.sleep(2 ** attempt)
        raise GitHubError(f"{request.full_url}: gave up")

    @staticmethod
    def _wait_for(err: urllib.error.HTTPError) -> float | None:
        """How long to wait before trying again, or None when trying again is pointless."""
        if err.code in (500, 502, 503, 504):
            return 5.0
        if err.code not in (403, 429):
            return None
        if retry_after := err.headers.get("Retry-After"):
            return float(retry_after) + 1
        if err.headers.get("X-RateLimit-Remaining") == "0":
            reset = float(err.headers.get("X-RateLimit-Reset", time.time() + 60))
            return max(reset - time.time(), 0) + 2
        # A secondary rate limit without a hint: GitHub asks for at least a minute.
        return 61.0

    def rest(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = path if path.startswith("http") else f"{API}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        body, _ = self._send(urllib.request.Request(url, headers=self._headers()))
        return json.loads(body)

    def code_search(self, query: str, page: int = 1) -> dict[str, Any]:
        with self._lock:
            pause = self._last_code_search + self._code_search_interval - time.monotonic()
            if pause > 0:
                time.sleep(pause)
            self._last_code_search = time.monotonic()
        return self.rest("/search/code", {"q": query, "per_page": 100, "page": page})

    def graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = json.dumps({"query": query, "variables": variables or {}}).encode()
        request = urllib.request.Request(
            f"{API}/graphql", data=payload, headers=self._headers("application/json"), method="POST"
        )
        for attempt in range(4):
            body, _ = self._send(request)
            result = json.loads(body)
            errors = result.get("errors") or []
            # A repository that is gone or private comes back as NOT_FOUND next to
            # the others' data; that is an answer, not a failure.
            serious = [e for e in errors if e.get("type") not in ("NOT_FOUND", "FORBIDDEN")]
            if not serious:
                return result.get("data") or {}
            if any(e.get("type") == "RATE_LIMITED" for e in serious) and attempt < 3:
                time.sleep(60)
                continue
            if result.get("data") and attempt == 3:
                _LOGGER.warning("GraphQL partial answer: %s", serious[:2])
                return result["data"]
            if attempt == 3:
                raise GitHubError(f"GraphQL: {serious[:2]}")
            time.sleep(5)
        return {}

    def download(self, url: str, limit: int) -> bytes | None:
        """A file of at most `limit` bytes, or None when it is larger or missing."""
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                length = response.headers.get("Content-Length")
                if length and int(length) > limit:
                    return None
                data = response.read(limit + 1)
        except (urllib.error.URLError, http.client.HTTPException, OSError):
            return None
        return None if len(data) > limit else data

    def raw(self, url: str) -> bytes:
        """A public file that is not part of the API, such as raw.githubusercontent.com."""
        body, _ = self._send(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}))
        return body
