"""
Minimal, dependency-light Web Push sender.

Implements:
  - RFC 8291 message encryption ("aes128gcm" content coding, RFC 8188)
  - RFC 8292 VAPID authentication (ES256 JWT)
using only the `cryptography` package and the standard library, so it installs
cleanly on PythonAnywhere, Docker and Windows alike.
"""
import base64
import json
import os
import struct
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, hmac, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

RECORD_SIZE = 4096


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    text = text.strip()
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _hmac_sha256(key: bytes, data: bytes) -> bytes:
    h = hmac.HMAC(key, hashes.SHA256())
    h.update(data)
    return h.finalize()


def _public_bytes(public_key) -> bytes:
    return public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


# --------------------------------------------------------------------------- #
# VAPID keys
# --------------------------------------------------------------------------- #

def generate_vapid_keys():
    """Return (private_key_b64url, public_key_b64url) for a new P-256 key pair."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_raw = private_key.private_numbers().private_value.to_bytes(32, "big")
    return b64url_encode(private_raw), b64url_encode(_public_bytes(private_key.public_key()))


def load_private_key(private_b64: str):
    value = int.from_bytes(b64url_decode(private_b64), "big")
    return ec.derive_private_key(value, ec.SECP256R1())


def vapid_headers(endpoint: str, private_b64: str, public_b64: str, subject: str, ttl_hours: int = 12) -> dict:
    """Authorization header for the push service (RFC 8292)."""
    parts = urlsplit(endpoint)
    claims = {"aud": f"{parts.scheme}://{parts.netloc}", "exp": int(time.time()) + ttl_hours * 3600, "sub": subject}
    header = {"typ": "JWT", "alg": "ES256"}
    signing_input = (
        b64url_encode(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + b64url_encode(json.dumps(claims, separators=(",", ":")).encode())
    )
    der = load_private_key(private_b64).sign(signing_input.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    token = f"{signing_input}.{b64url_encode(signature)}"
    return {"Authorization": f"vapid t={token}, k={public_b64}"}


# --------------------------------------------------------------------------- #
# Encryption (RFC 8291)
# --------------------------------------------------------------------------- #

def encrypt(plaintext: bytes, ua_public_b64: str, auth_secret_b64: str, *, _as_private=None, _salt=None) -> bytes:
    """Encrypt a push message for one browser subscription. Returns the HTTP body."""
    ua_public = b64url_decode(ua_public_b64)
    auth_secret = b64url_decode(auth_secret_b64)
    ua_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)

    as_private = _as_private or ec.generate_private_key(ec.SECP256R1())
    as_public = _public_bytes(as_private.public_key())
    salt = _salt or os.urandom(16)

    ecdh_secret = as_private.exchange(ec.ECDH(), ua_key)
    prk_key = _hmac_sha256(auth_secret, ecdh_secret)
    key_info = b"WebPush: info\x00" + ua_public + as_public
    ikm = _hmac_sha256(prk_key, key_info + b"\x01")

    prk = _hmac_sha256(salt, ikm)
    cek = _hmac_sha256(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]
    nonce = _hmac_sha256(prk, b"Content-Encoding: nonce\x00\x01")[:12]

    record = plaintext + b"\x02"  # single, final record
    if len(record) + 16 > RECORD_SIZE:
        raise ValueError("Push message too large")
    ciphertext = AESGCM(cek).encrypt(nonce, record, None)
    header = salt + struct.pack("!L", RECORD_SIZE) + bytes([len(as_public)]) + as_public
    return header + ciphertext


# --------------------------------------------------------------------------- #
# Sending
# --------------------------------------------------------------------------- #

class PushGone(Exception):
    """The subscription no longer exists (user unsubscribed / reinstalled)."""


def send(endpoint, p256dh, auth, payload: dict, *, private_b64, public_b64, subject, ttl=86400, timeout=10):
    body = encrypt(json.dumps(payload).encode("utf-8"), p256dh, auth)
    headers = {
        "Content-Type": "application/octet-stream",
        "Content-Encoding": "aes128gcm",
        "TTL": str(ttl),
        "Urgency": "normal",
        **vapid_headers(endpoint, private_b64, public_b64, subject),
    }
    request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 410):
            raise PushGone(exc.code) from exc
        raise
