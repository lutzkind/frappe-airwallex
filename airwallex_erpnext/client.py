from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterable

from airwallex_erpnext.exceptions import (
    AirwallexAPIError,
    AirwallexAuthenticationError,
    AirwallexPermissionError,
    AirwallexRateLimitError,
)


@dataclass
class AirwallexClient:
    base_url: str
    client_id: str
    api_key: str
    login_as: str | None = None
    timeout_seconds: int = 30
    user_agent: str = "frappe-airwallex/1.0"
    _access_token: str | None = field(default=None, init=False, repr=False)
    _expires_at: float = field(default=0.0, init=False, repr=False)

    def authenticate(self, force: bool = False) -> str:
        if not force and self._access_token and self._expires_at > time.time() + 30:
            return self._access_token

        headers = {
            "x-client-id": self.client_id,
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
        }
        if self.login_as:
            headers["x-login-as"] = self.login_as

        payload = self._raw_request("POST", "/api/v1/authentication/login", headers=headers, body={})
        token = payload.get("token") or payload.get("access_token")
        if not token:
            raise AirwallexAuthenticationError("Authentication response did not contain an access token")

        expires_at = payload.get("expires_at")
        if isinstance(expires_at, (int, float)):
            self._expires_at = float(expires_at) / 1000 if float(expires_at) > 10_000_000_000 else float(expires_at)
        else:
            self._expires_at = time.time() + 25 * 60
        self._access_token = str(token)
        return self._access_token

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | list[Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        token = self.authenticate()
        merged = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
        }
        if headers:
            merged.update(headers)
        try:
            return self._raw_request(method, path, params=params, body=body, headers=merged)
        except AirwallexAuthenticationError:
            merged["Authorization"] = f"Bearer {self.authenticate(force=True)}"
            return self._raw_request(method, path, params=params, body=body, headers=merged)

    def download(self, url: str) -> tuple[bytes, str | None]:
        token = self.authenticate()
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}", "User-Agent": self.user_agent},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                return response.read(), response.headers.get("Content-Type")
        except urllib.error.HTTPError as exc:
            self._raise_http(exc)
        raise AirwallexAPIError("Attachment download failed")

    def paginate_bookmark(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        item_key: str = "items",
        max_items: int = 10_000,
    ) -> Iterable[dict[str, Any]]:
        query = dict(params or {})
        seen_pages: set[str] = set()
        yielded = 0
        while yielded < max_items:
            page = self.request("GET", path, params=query)
            for item in page.get(item_key) or []:
                if isinstance(item, dict):
                    yield item
                    yielded += 1
                    if yielded >= max_items:
                        return
            cursor = page.get("page_after")
            if not cursor or cursor in seen_pages:
                return
            seen_pages.add(str(cursor))
            query["page"] = cursor

    def paginate_numbered(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        item_key: str = "items",
        page_size: int = 1000,
        max_items: int = 10_000,
    ) -> Iterable[dict[str, Any]]:
        query = dict(params or {})
        query["page_size"] = min(max(1, page_size), 1000)
        page_num = int(query.get("page_num", 0))
        yielded = 0
        while yielded < max_items:
            query["page_num"] = page_num
            page = self.request("GET", path, params=query)
            items = page.get(item_key) or []
            if not items:
                return
            for item in items:
                if isinstance(item, dict):
                    yield item
                    yielded += 1
                    if yielded >= max_items:
                        return
            if len(items) < query["page_size"]:
                return
            page_num += 1

    def _raw_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | list[Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = path if path.startswith("http") else self.base_url.rstrip("/") + "/" + path.lstrip("/")
        if params:
            filtered = {k: v for k, v in params.items() if v not in (None, "", [], {})}
            if filtered:
                url += ("&" if "?" in url else "?") + urllib.parse.urlencode(filtered, doseq=True)
        data = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers or {}, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as exc:
            self._raise_http(exc)
        except urllib.error.URLError as exc:
            raise AirwallexAPIError(f"Airwallex request failed: {exc.reason}") from exc
        raise AirwallexAPIError("Airwallex request failed")

    @staticmethod
    def _raise_http(exc: urllib.error.HTTPError) -> None:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            details = json.loads(raw)
        except json.JSONDecodeError:
            details = {"message": raw[:1000]}
        message = details.get("message") or details.get("code") or details.get("error") or f"HTTP {exc.code}"
        if exc.code == 401:
            raise AirwallexAuthenticationError(str(message))
        if exc.code == 403:
            raise AirwallexPermissionError(str(message))
        if exc.code == 429:
            raise AirwallexRateLimitError(str(message))
        raise AirwallexAPIError(f"HTTP {exc.code}: {message}")
