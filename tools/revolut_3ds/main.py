"""
Revolut 3DS auto-approver — entry point.

Usage:
    python -m tools.revolut_3ds.main

First run: walks through device registration, saves credentials.
Subsequent runs: loads credentials, polls for pending 3DS challenges, auto-approves.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from .api import RevolutAPI
from .auth import load, register


POLL_INTERVAL = 1.5  # seconds


async def run() -> None:
    loaded = load()
    if loaded is None:
        print("No saved credentials. Starting device registration...")
        device_id, creds = await register()
    else:
        device_id, creds = loaded
        print(f"✓ Loaded credentials for device {device_id[:8]}…")

    api = RevolutAPI(device_id, creds)
    try:
        r = await api.wallet()
        if r.status_code != 200:
            print(f"✗ Credentials rejected ({r.status_code}). Delete ~/.revolut-bot/credentials.json and re-run.")
            return

        print("Polling for 3DS challenges (Ctrl+C to stop)...")
        while True:
            try:
                challenges = await api.get_pending_challenges()
                for c in challenges:
                    cid = c.get("id") or c.get("challengeId")
                    await api.approve_challenge(cid)
                    print(f"[{datetime.now():%H:%M:%S}] approved challenge {cid}")
            except NotImplementedError:
                print("3DS endpoints not yet captured — see CAPTURE.md")
                return
            except Exception as e:
                print(f"[{datetime.now():%H:%M:%S}] poll error: {e}")
            await asyncio.sleep(POLL_INTERVAL)
    finally:
        await api.close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nStopped.")
