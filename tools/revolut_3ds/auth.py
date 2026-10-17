"""
Device registration + credential persistence for the Revolut API client.
"""
from __future__ import annotations

import getpass
import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .api import Credentials, RevolutAPI, new_device_id


CREDS_PATH = Path.home() / ".revolut-bot" / "credentials.json"


def load() -> Optional[tuple[str, Credentials]]:
    """Returns (device_id, credentials) if a saved session exists."""
    if not CREDS_PATH.exists():
        return None
    data = json.loads(CREDS_PATH.read_text())
    return data["device_id"], Credentials(
        device_id=data["device_id"],
        user_id=data["user_id"],
        access_token=data["access_token"],
    )


def save(device_id: str, creds: Credentials) -> None:
    CREDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CREDS_PATH.write_text(json.dumps({
        "device_id":    device_id,
        "user_id":      creds.user_id,
        "access_token": creds.access_token,
    }, indent=2))
    CREDS_PATH.chmod(0o600)


async def register() -> tuple[str, Credentials]:
    """
    Interactive first-run device registration.

    Implements Path A (SMS code + selfie) from the plan. If Revolut Business
    rejects this and returns a confirmation URL instead, switch to Path B
    polling. mitmproxy will tell us which path is current.
    """
    print("\nRevolut device registration")
    print("-" * 40)

    phone = input("Phone number (with country code, e.g. +491701234567): ").strip()
    password = getpass.getpass("Password (your 4-digit Revolut app passcode): ").strip()

    device_id = new_device_id()
    api = RevolutAPI(device_id)
    try:
        r = await api.signin(phone, password)
        r.raise_for_status()
        print("→ Signin initiated. Check SMS/email/app for confirmation code.")

        code = input("Confirmation code: ").strip()
        r = await api.signin_confirm(phone, code)
        r.raise_for_status()
        data = r.json()
        access_token = data["accessToken"]
        user_id = data["user"]["id"]
        print("→ Signin confirmed.")

        selfie_path = input("Path to selfie JPEG: ").strip()
        jpeg = Path(selfie_path).read_bytes()
        r = await api.biometric_selfie(phone, access_token, jpeg)
        r.raise_for_status()
        biometric_id = r.json()["id"]

        r = await api.biometric_confirm(biometric_id, phone, access_token)
        r.raise_for_status()
        print("→ Biometric verified.")

        creds = Credentials(device_id=device_id, user_id=user_id, access_token=access_token)
        save(device_id, creds)
        print(f"✓ Credentials saved to {CREDS_PATH}")
        return device_id, creds
    finally:
        await api.close()
