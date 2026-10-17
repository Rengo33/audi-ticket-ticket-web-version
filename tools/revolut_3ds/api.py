"""
Revolut internal mobile API client.

Known endpoints come from https://github.com/tducret/revolut-python (archived 2022).
3DS challenge endpoints are filled in after mitmproxy capture — see CAPTURE.md.

Base URL for both personal and business: https://api.revolut.com
"""
from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass
from typing import Any, Optional

import httpx


BASE = "https://api.revolut.com"

# Default token used by the unauthenticated /signin call (from tducret).
# Base64 of "App:S9WUnSFBy67gWan7" — the static public client credential.
DEFAULT_AUTH = "QXBwOlM5V1VuU0ZCeTY3Z1dhbjc="

# App identity — these may need bumping to match a current Revolut Business build.
# Update from the User-Agent seen in mitmproxy during capture.
CLIENT_VERSION = "6.34.3"
USER_AGENT = "Revolut/5.5 500500250 (CLI; Android 4.4.2)"


@dataclass
class Credentials:
    device_id: str
    user_id: str
    access_token: str

    @property
    def basic(self) -> str:
        raw = f"{self.user_id}:{self.access_token}".encode()
        return base64.b64encode(raw).decode()


def new_device_id() -> str:
    return str(uuid.uuid4())


def _headers(device_id: str, auth: str) -> dict[str, str]:
    return {
        "X-Api-Version":    "1",
        "X-Client-Version": CLIENT_VERSION,
        "X-Device-Id":      device_id,
        "User-Agent":       USER_AGENT,
        "Authorization":    f"Basic {auth}",
        "Content-Type":     "application/json",
    }


class RevolutAPI:
    def __init__(self, device_id: str, creds: Optional[Credentials] = None):
        self.device_id = device_id
        self.creds = creds
        self._client = httpx.AsyncClient(base_url=BASE, timeout=15.0)

    async def close(self) -> None:
        await self._client.aclose()

    def _auth(self) -> str:
        return self.creds.basic if self.creds else DEFAULT_AUTH

    async def _request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        headers = _headers(self.device_id, self._auth())
        headers.update(kw.pop("headers", {}))
        return await self._client.request(method, path, headers=headers, **kw)

    # ---- Auth (known paths from tducret) --------------------------------

    async def signin(self, phone: str, password: str) -> httpx.Response:
        """Step 1. Triggers SMS/email code or a confirmation link."""
        return await self._request("POST", "/signin", json={
            "phone": phone,
            "password": password,
        })

    async def signin_confirm(self, phone: str, code: str) -> httpx.Response:
        """Step 2. Returns user_id + access_token."""
        return await self._request("POST", "/signin/confirm", json={
            "phone": phone,
            "code": code,
        })

    async def biometric_selfie(self, phone: str, access_token: str, jpeg: bytes) -> httpx.Response:
        """Upload selfie for device verification. Returns {id}."""
        # Biometric endpoint uses (phone:access_token) as basic auth.
        basic = base64.b64encode(f"{phone}:{access_token}".encode()).decode()
        headers = _headers(self.device_id, basic)
        headers["Content-Type"] = "image/jpeg"
        return await self._client.post(
            "/biometric-signin/selfie",
            headers=headers,
            content=jpeg,
        )

    async def biometric_confirm(self, biometric_id: str, phone: str, access_token: str) -> httpx.Response:
        basic = base64.b64encode(f"{phone}:{access_token}".encode()).decode()
        headers = _headers(self.device_id, basic)
        return await self._client.post(
            f"/biometric-signin/confirm/{biometric_id}",
            headers=headers,
        )

    async def wallet(self) -> httpx.Response:
        """Verifies current credentials are valid. Used as a keep-alive."""
        return await self._request("GET", "/user/current/wallet")

    # ---- 3DS challenges (TO BE FILLED after mitmproxy capture) -----------
    #
    # Expected shape (from prior Revolut tooling patterns):
    #   GET  /user/current/card/challenge?status=PENDING  → list
    #   POST /user/current/card/challenge/{id}/confirm    → approve
    #
    # Replace these paths with what mitmproxy reveals in CAPTURE.md step 3.

    async def get_pending_challenges(self) -> list[dict]:
        raise NotImplementedError("Fill in after capture — see CAPTURE.md §3")

    async def approve_challenge(self, challenge_id: str) -> httpx.Response:
        raise NotImplementedError("Fill in after capture — see CAPTURE.md §3")
