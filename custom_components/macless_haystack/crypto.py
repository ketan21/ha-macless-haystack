"""Decrypt FindMy location reports.

The report format and the decryption steps are the same as in the
OpenHaystack and macless-haystack projects.
"""

from __future__ import annotations

import base64
import hashlib
import struct
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .const import APPLE_EPOCH_OFFSET

KEY_SIZE = 28


def _private_key(private_key_b64: str) -> ec.EllipticCurvePrivateKey:
    raw = base64.b64decode(private_key_b64, validate=True)
    if len(raw) != KEY_SIZE:
        raise ValueError("Private key must be 28 bytes")
    return ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP224R1())


def hashed_adv_key(private_key_b64: str) -> str:
    """Return the hashed advertisement key that Apple uses for the reports."""
    public_key = _private_key(private_key_b64).public_key()
    adv_key = public_key.public_numbers().x.to_bytes(KEY_SIZE, "big")
    return base64.b64encode(hashlib.sha256(adv_key).digest()).decode()


def accessory_keys(accessory: dict[str, Any]) -> dict[str, str]:
    """Return a map of hashed advertisement key to private key."""
    private_keys = [accessory["privateKey"], *accessory.get("additionalKeys", [])]
    return {hashed_adv_key(key): key for key in private_keys}


def accessory_unique_id(accessory: dict[str, Any]) -> str:
    """Return the stable id of an accessory."""
    return hashed_adv_key(accessory["privateKey"])


def decode_report(payload_b64: str, private_key_b64: str) -> dict[str, Any] | None:
    """Decrypt one report. Return None for a report with a bad payload."""
    try:
        data = base64.b64decode(payload_b64)
        # Newer reports hold one extra byte.
        if len(data) > 88:
            data = data[:4] + data[5:]
        if len(data) != 88:
            return None

        ephemeral_key = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP224R1(), data[5:62]
        )
        shared_key = _private_key(private_key_b64).exchange(ec.ECDH(), ephemeral_key)
        symmetric_key = hashlib.sha256(
            shared_key + b"\x00\x00\x00\x01" + data[5:62]
        ).digest()
        plaintext = AESGCM(symmetric_key[:16]).decrypt(
            symmetric_key[16:], data[62:], None
        )

        status = plaintext[9]
        return {
            "timestamp": int.from_bytes(data[0:4], "big") + APPLE_EPOCH_OFFSET,
            "latitude": struct.unpack(">i", plaintext[0:4])[0] / 10000000,
            "longitude": struct.unpack(">i", plaintext[4:8])[0] / 10000000,
            "accuracy": plaintext[8],
            "status": status,
            "battery": (status >> 6) & 0x03,
        }
    except Exception:  # noqa: BLE001 - one bad report must not stop the poll
        return None


def decode_reports(
    reports: list[dict[str, Any]], key_map: dict[str, str]
) -> list[dict[str, Any]]:
    """Decrypt all reports that match a known key."""
    decoded = []
    for report in reports:
        key_id = report.get("id")
        private_key = key_map.get(key_id)
        payload = report.get("payload")
        if private_key is None or not isinstance(payload, str):
            continue
        result = decode_report(payload, private_key)
        if result is None:
            continue
        result["hashed_key"] = key_id
        result["gateway_confidence"] = report.get("confidence")
        decoded.append(result)
    return decoded
