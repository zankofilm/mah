# -*- coding: utf-8 -*-
"""Security primitives for local secrets, passwords and encrypted backups."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from pathlib import Path

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
except Exception:  # pragma: no cover - requirements include cryptography
    Fernet = None
    InvalidToken = Exception
    AESGCM = None
    PBKDF2HMAC = None
    hashes = None

_SECRET_PREFIX = "enc:v1:"
_BACKUP_MAGIC = b"JAVANROOD-ENC-BACKUP-v1\n"


def _chmod_private(path: str) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def validate_password_policy(password: str, username: str = "") -> tuple[bool, str]:
    value = str(password or "")
    if len(value) < 10:
        return False, "رمز عبور باید حداقل ۱۰ کاراکتر باشد."
    if len(value) > 128:
        return False, "رمز عبور بیش از حد طولانی است."
    if username and username.casefold() in value.casefold():
        return False, "رمز عبور نباید شامل نام کاربری باشد."
    categories = sum([
        bool(re.search(r"[a-z]", value)),
        bool(re.search(r"[A-Z]", value)),
        bool(re.search(r"\d", value)),
        bool(re.search(r"[^\w\s]", value)),
    ])
    if categories < 3:
        return False, "رمز عبور باید دست‌کم شامل سه گروه از حروف کوچک، حروف بزرگ، عدد و نماد باشد."
    weak = {"password123", "admin123", "1234567890", "qwerty12345"}
    if value.casefold() in weak:
        return False, "این رمز عبور قابل حدس است؛ رمز دیگری انتخاب کنید."
    return True, "ok"


def generate_strong_password(length: int = 18) -> str:
    length = max(14, int(length))
    alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%_-"
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(length))
        if validate_password_policy(value)[0]:
            return value


class SecretVault:
    """Fernet vault backed by a machine-local key file with restrictive permissions."""

    def __init__(self, data_dir: str):
        self.data_dir = os.path.abspath(data_dir)
        self.security_dir = os.path.join(self.data_dir, "security")
        self.key_path = os.path.join(self.security_dir, "master.key")
        os.makedirs(self.security_dir, exist_ok=True)
        self._fernet = self._load_fernet()

    def _load_fernet(self):
        if Fernet is None:
            raise RuntimeError("کتابخانه cryptography برای حفاظت از اطلاعات حساس نصب نشده است.")
        if os.path.exists(self.key_path):
            key = Path(self.key_path).read_bytes().strip()
        else:
            key = Fernet.generate_key()
            temp = self.key_path + ".tmp"
            Path(temp).write_bytes(key)
            _chmod_private(temp)
            os.replace(temp, self.key_path)
        _chmod_private(self.key_path)
        return Fernet(key)

    def encrypt(self, value: str) -> str:
        text = str(value or "")
        if not text or text.startswith(_SECRET_PREFIX):
            return text
        token = self._fernet.encrypt(text.encode("utf-8")).decode("ascii")
        return _SECRET_PREFIX + token

    def decrypt(self, value: str) -> str:
        text = str(value or "")
        if not text.startswith(_SECRET_PREFIX):
            return text
        try:
            return self._fernet.decrypt(text[len(_SECRET_PREFIX):].encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError):
            return ""

    @staticmethod
    def is_encrypted(value: str) -> bool:
        return str(value or "").startswith(_SECRET_PREFIX)

    def fingerprint(self, value: str) -> str:
        key = Path(self.key_path).read_bytes()
        return hmac.new(key, str(value or "").encode("utf-8"), hashlib.sha256).hexdigest()


def is_encrypted_backup_file(path: str) -> bool:
    try:
        with open(path, "rb") as handle:
            return handle.read(len(_BACKUP_MAGIC)) == _BACKUP_MAGIC
    except OSError:
        return False


def encrypt_backup_file(source_path: str, destination_path: str, password: str) -> str:
    ok, message = validate_password_policy(password)
    if not ok:
        raise ValueError(message)
    if AESGCM is None:
        raise RuntimeError("کتابخانه cryptography نصب نشده است.")
    salt = os.urandom(16)
    nonce = os.urandom(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=390000)
    key = kdf.derive(password.encode("utf-8"))
    plaintext = Path(source_path).read_bytes()
    metadata = json.dumps({"filename": os.path.basename(source_path)}, ensure_ascii=False).encode("utf-8")
    payload = len(metadata).to_bytes(4, "big") + metadata + plaintext
    encrypted = AESGCM(key).encrypt(nonce, payload, _BACKUP_MAGIC)
    temp = destination_path + ".tmp"
    os.makedirs(os.path.dirname(os.path.abspath(destination_path)), exist_ok=True)
    with open(temp, "wb") as handle:
        handle.write(_BACKUP_MAGIC)
        handle.write(salt)
        handle.write(nonce)
        handle.write(encrypted)
    _chmod_private(temp)
    os.replace(temp, destination_path)
    return destination_path


def decrypt_backup_file(source_path: str, destination_path: str, password: str) -> str:
    if AESGCM is None:
        raise RuntimeError("کتابخانه cryptography نصب نشده است.")
    blob = Path(source_path).read_bytes()
    if not blob.startswith(_BACKUP_MAGIC):
        raise ValueError("قالب فایل بکاپ رمزگذاری‌شده معتبر نیست.")
    offset = len(_BACKUP_MAGIC)
    salt, nonce, encrypted = blob[offset:offset + 16], blob[offset + 16:offset + 28], blob[offset + 28:]
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=390000)
    key = kdf.derive(password.encode("utf-8"))
    try:
        payload = AESGCM(key).decrypt(nonce, encrypted, _BACKUP_MAGIC)
    except Exception as exc:
        raise ValueError("رمز بکاپ اشتباه است یا فایل آسیب دیده است.") from exc
    meta_len = int.from_bytes(payload[:4], "big")
    database_bytes = payload[4 + meta_len:]
    temp = destination_path + ".tmp"
    os.makedirs(os.path.dirname(os.path.abspath(destination_path)), exist_ok=True)
    Path(temp).write_bytes(database_bytes)
    _chmod_private(temp)
    os.replace(temp, destination_path)
    return destination_path
