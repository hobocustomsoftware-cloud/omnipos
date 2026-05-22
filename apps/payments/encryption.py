"""Fernet at-rest encryption for PSP secrets."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

_STORE_PREFIX = "omnipos_fernet_v1:"


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plaintext: str | None) -> str:
    """Prefix-stored ciphertext; idempotent when already encrypted."""

    if plaintext is None:
        return ""
    text = plaintext.strip() if isinstance(plaintext, str) else str(plaintext)
    if not text:
        return ""
    if text.startswith(_STORE_PREFIX):
        return text
    token = _fernet().encrypt(text.encode("utf-8")).decode("ascii")
    return _STORE_PREFIX + token


def decrypt_secret(stored: str | None) -> str:
    """Decrypt or return legacy plaintext."""

    if stored is None:
        return ""
    text = stored.strip() if isinstance(stored, str) else str(stored)
    if not text:
        return ""
    if not text.startswith(_STORE_PREFIX):
        return text
    payload = text[len(_STORE_PREFIX) :]
    try:
        return _fernet().decrypt(payload.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return ""
