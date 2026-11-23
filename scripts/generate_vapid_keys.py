"""One-off: generate the VAPID key pair for browser push notifications.

    venv/bin/python scripts/generate_vapid_keys.py

Prints three lines to paste into .env, then restart the service:
    VAPID_PUBLIC_KEY=...
    VAPID_PRIVATE_KEY=...
    VAPID_SUBJECT=mailto:hello@boxbox.in

Run it ONCE. Generating a new pair later invalidates every device that
already subscribed (each one has to click "Enable notifications" again).
Keep VAPID_PRIVATE_KEY secret; it is printed here only so you can copy it
into .env. It writes nothing to disk.
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64url(b):
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


def main():
    key = ec.generate_private_key(ec.SECP256R1())
    private_raw = key.private_numbers().private_value.to_bytes(32, 'big')
    public_raw = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    print(f"VAPID_PUBLIC_KEY={b64url(public_raw)}")
    print(f"VAPID_PRIVATE_KEY={b64url(private_raw)}")
    print("VAPID_SUBJECT=mailto:hello@boxbox.in")


if __name__ == '__main__':
    main()
