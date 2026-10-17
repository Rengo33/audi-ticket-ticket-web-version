"""
Generate a VAPID keypair for Web Push.

Run once, copy both values into .env:

    python -m scripts.generate_vapid_keys

Outputs:
  VAPID_PUBLIC_KEY   — base64url, uncompressed P-256 point (x04 || X || Y).
                       The browser expects this as `applicationServerKey`.
  VAPID_PRIVATE_KEY  — base64url-encoded 32-byte scalar; pywebpush accepts
                       this directly and it fits on one .env line.

Losing these invalidates every live subscription.
"""
import base64

from cryptography.hazmat.primitives.asymmetric import ec


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def main() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    pub = private_key.public_key().public_numbers()
    priv_int = private_key.private_numbers().private_value

    raw_public = b"\x04" + pub.x.to_bytes(32, "big") + pub.y.to_bytes(32, "big")
    raw_private = priv_int.to_bytes(32, "big")

    print("# --- Paste these into your .env ---")
    print(f"VAPID_PUBLIC_KEY={_b64url(raw_public)}")
    print(f"VAPID_PRIVATE_KEY={_b64url(raw_private)}")
    print("VAPID_CONTACT_EMAIL=you@example.com")


if __name__ == "__main__":
    main()
