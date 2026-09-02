# -*- coding: utf-8 -*-
"""هسته مستقل از رابط برای مجوزدهی و تبادل امن فایل میان ادمین و کلاینت.

فرمت‌ها:
- .jrr درخواست فعال‌سازی وابسته به دستگاه
- .jra فایل فعال‌سازی/تمدید امضاشده و رمزنگاری‌شده با کد ملی
- .jrcx بسته اطلاعاتی کلاینت، امضاشده و رمزنگاری‌شده برای ادمین

این ماژول عمداً هیچ وابستگی به PyQt ندارد تا بتوان آن را با آزمون‌های خودکار
و در هر دو برنامه ادمین و کلاینت استفاده کرد.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import re
import secrets
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

REQUEST_FORMAT = "JAVANROOD-CLIENT-REQUEST"
ACTIVATION_FORMAT = "JAVANROOD-CLIENT-ACTIVATION"
PACKAGE_FORMAT = "JAVANROOD-CLIENT-DATA"
FORMAT_VERSION = 1
PACKAGE_VERSION = 2
PACKAGE_KEY_MODE = "license-password-hash-hkdf-v1"

ARGON2 = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16)


class ExchangeError(ValueError):
    """خطای قابل نمایش در رابط کاربری."""


class SignatureError(ExchangeError):
    pass


class DecryptionError(ExchangeError):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    text = (value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def b64d(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode((value or "").encode("ascii"))
    except Exception as exc:
        raise ExchangeError("ساختار داده رمزنگاری‌شده معتبر نیست.") from exc


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_national_code(value: str) -> str:
    trans = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    code = re.sub(r"\D", "", (value or "").translate(trans))
    if len(code) != 10:
        raise ExchangeError("کد ملی باید دقیقاً ۱۰ رقم باشد.")
    return code


def national_code_hash(value: str) -> str:
    return sha256_bytes(normalize_national_code(value).encode("ascii"))


def password_hash(password: str) -> str:
    if len(password or "") < 8:
        raise ExchangeError("رمز عبور کلاینت باید حداقل ۸ نویسه باشد.")
    return ARGON2.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        return bool(ARGON2.verify(encoded_hash, password or ""))
    except (VerifyMismatchError, Exception):
        return False


def raw_ed25519_public(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def raw_x25519_public(key: X25519PublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def public_fingerprint(raw_key: bytes) -> str:
    digest = hashlib.sha256(raw_key).hexdigest().upper()
    return ":".join(digest[i:i + 4] for i in range(0, 32, 4))


def _set_private_permissions(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def _device_material() -> str:
    pieces = [
        platform.system(), platform.release(), platform.machine(), platform.node(),
        socket.gethostname(), os.environ.get("COMPUTERNAME", ""), os.environ.get("USERNAME", ""),
    ]
    try:
        pieces.append(str(uuid.getnode()))
    except Exception:
        pass
    return "|".join(str(x or "") for x in pieces)


def device_fingerprint() -> str:
    """شناسه پایدار دستگاه. برای حریم خصوصی فقط هش خروجی داده می‌شود."""
    return sha256_bytes(_device_material().encode("utf-8"))


class AdminKeyStore:
    """کلیدهای امضا و رمزگشایی ادمین با نگهداری محلی محافظت‌شده."""

    def __init__(self, root_dir: str):
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.secret_path = self.root / "admin_master_secret.bin"
        self.sign_path = self.root / "admin_sign_private.pem"
        self.enc_path = self.root / "admin_exchange_private.pem"
        self._ensure()

    def _master_password(self) -> bytes:
        if not self.secret_path.exists():
            self.secret_path.write_bytes(secrets.token_bytes(48))
            _set_private_permissions(self.secret_path)
        return hashlib.sha256(self.secret_path.read_bytes() + b"javanrood-admin-key-store-v1").digest()

    def _ensure(self) -> None:
        password = self._master_password()
        if not self.sign_path.exists():
            key = Ed25519PrivateKey.generate()
            self.sign_path.write_bytes(key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.BestAvailableEncryption(password),
            ))
            _set_private_permissions(self.sign_path)
        if not self.enc_path.exists():
            key = X25519PrivateKey.generate()
            self.enc_path.write_bytes(key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.BestAvailableEncryption(password),
            ))
            _set_private_permissions(self.enc_path)

    def signing_private(self) -> Ed25519PrivateKey:
        return serialization.load_pem_private_key(self.sign_path.read_bytes(), self._master_password())

    def encryption_private(self) -> X25519PrivateKey:
        return serialization.load_pem_private_key(self.enc_path.read_bytes(), self._master_password())

    def trust_bundle(self) -> Dict[str, str]:
        sign_raw = raw_ed25519_public(self.signing_private().public_key())
        enc_raw = raw_x25519_public(self.encryption_private().public_key())
        return {
            "format": "JAVANROOD-ADMIN-TRUST",
            "version": FORMAT_VERSION,
            "sign_public": b64e(sign_raw),
            "exchange_public": b64e(enc_raw),
            "sign_fingerprint": public_fingerprint(sign_raw),
            "exchange_fingerprint": public_fingerprint(enc_raw),
        }

    def export_trust_bundle(self, path: str) -> str:
        Path(path).write_text(json.dumps(self.trust_bundle(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path


class ClientKeyStore:
    """کلید امضای کلاینت که به دستگاه محلی گره می‌خورد."""

    def __init__(self, root_dir: str, expected_device_id: Optional[str] = None):
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.secret_path = self.root / "client_device_secret.bin"
        self.sign_path = self.root / "client_sign_private.pem"
        self.device_id = expected_device_id or device_fingerprint()
        self._ensure()

    def _password(self) -> bytes:
        if not self.secret_path.exists():
            self.secret_path.write_bytes(secrets.token_bytes(48))
            _set_private_permissions(self.secret_path)
        return hashlib.sha256(self.secret_path.read_bytes() + self.device_id.encode("ascii") + b"client-key-v1").digest()

    def _ensure(self) -> None:
        if not self.sign_path.exists():
            key = Ed25519PrivateKey.generate()
            self.sign_path.write_bytes(key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.BestAvailableEncryption(self._password()),
            ))
            _set_private_permissions(self.sign_path)

    def signing_private(self) -> Ed25519PrivateKey:
        try:
            return serialization.load_pem_private_key(self.sign_path.read_bytes(), self._password())
        except Exception as exc:
            raise ExchangeError("کلید کلاینت با این دستگاه سازگار نیست یا آسیب دیده است.") from exc

    def signing_public_raw(self) -> bytes:
        return raw_ed25519_public(self.signing_private().public_key())


@dataclass
class ActivationResult:
    payload: Dict[str, Any]
    trust_bundle: Dict[str, str]


def build_activation_request(path: str, national_code: str, key_store: ClientKeyStore,
                             client_version: str = "1.0.0") -> Dict[str, Any]:
    core = {
        "format": REQUEST_FORMAT,
        "version": FORMAT_VERSION,
        "request_id": str(uuid.uuid4()),
        "created_at": utc_now_iso(),
        "device_id": key_store.device_id,
        "national_code_hash": national_code_hash(national_code),
        "client_sign_public": b64e(key_store.signing_public_raw()),
        "client_version": client_version,
    }
    core["signature"] = b64e(key_store.signing_private().sign(canonical_json_bytes(core)))
    Path(path).write_text(json.dumps(core, ensure_ascii=False, indent=2), encoding="utf-8")
    return core


def read_activation_request(path: str) -> Dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise ExchangeError("فایل درخواست فعال‌سازی قابل خواندن نیست.") from exc
    if data.get("format") != REQUEST_FORMAT or int(data.get("version") or 0) != FORMAT_VERSION:
        raise ExchangeError("فرمت درخواست فعال‌سازی پشتیبانی نمی‌شود.")
    signature = b64d(data.get("signature"))
    core = dict(data)
    core.pop("signature", None)
    try:
        Ed25519PublicKey.from_public_bytes(b64d(data.get("client_sign_public"))).verify(
            signature, canonical_json_bytes(core)
        )
    except (InvalidSignature, ValueError) as exc:
        raise SignatureError("امضای درخواست فعال‌سازی معتبر نیست.") from exc
    if not re.fullmatch(r"[0-9a-f]{64}", str(data.get("device_id") or "")):
        raise ExchangeError("شناسه دستگاه درخواست معتبر نیست.")
    return data


def _activation_aad(envelope: Dict[str, Any]) -> bytes:
    return canonical_json_bytes({
        "format": envelope["format"], "version": envelope["version"],
        "kind": envelope["kind"], "license_id": envelope["license_id"],
        "issued_at": envelope["issued_at"],
    })


def build_activation_file(path: str, payload: Dict[str, Any], national_code: str,
                          admin_keys: AdminKeyStore, kind: str = "activation") -> Dict[str, Any]:
    code = normalize_national_code(national_code)
    license_id = str(payload.get("license_id") or uuid.uuid4())
    issued_at = utc_now_iso()
    payload = dict(payload)
    payload["license_id"] = license_id
    payload["national_code_verifier"] = sha256_bytes((code + "|" + license_id).encode("ascii"))
    payload["issued_at"] = issued_at
    payload["kind"] = kind
    salt = secrets.token_bytes(16)
    key = Scrypt(salt=salt, length=32, n=2 ** 15, r=8, p=1).derive(code.encode("ascii"))
    nonce = secrets.token_bytes(12)
    trust = admin_keys.trust_bundle()
    envelope = {
        "format": ACTIVATION_FORMAT,
        "version": FORMAT_VERSION,
        "kind": kind,
        "license_id": license_id,
        "issued_at": issued_at,
        "admin_sign_public": trust["sign_public"],
        "admin_exchange_public": trust["exchange_public"],
        "admin_sign_fingerprint": trust["sign_fingerprint"],
        "salt": b64e(salt),
        "nonce": b64e(nonce),
    }
    envelope["ciphertext"] = b64e(AESGCM(key).encrypt(nonce, canonical_json_bytes(payload), _activation_aad(envelope)))
    envelope["signature"] = b64e(admin_keys.signing_private().sign(canonical_json_bytes(envelope)))
    Path(path).write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    return envelope


def open_activation_file(path: str, national_code: str,
                         trusted_sign_public: Optional[str] = None) -> ActivationResult:
    code = normalize_national_code(national_code)
    try:
        envelope = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise ExchangeError("فایل فعال‌سازی قابل خواندن نیست.") from exc
    if envelope.get("format") != ACTIVATION_FORMAT or int(envelope.get("version") or 0) != FORMAT_VERSION:
        raise ExchangeError("فرمت فایل فعال‌سازی پشتیبانی نمی‌شود.")
    sign_raw = b64d(envelope.get("admin_sign_public"))
    if trusted_sign_public and b64d(trusted_sign_public) != sign_raw:
        raise SignatureError("این فایل توسط مدیر مورد اعتماد این کلاینت صادر نشده است.")
    signature = b64d(envelope.get("signature"))
    core = dict(envelope)
    core.pop("signature", None)
    try:
        Ed25519PublicKey.from_public_bytes(sign_raw).verify(signature, canonical_json_bytes(core))
    except (InvalidSignature, ValueError) as exc:
        raise SignatureError("امضای فایل فعال‌سازی معتبر نیست.") from exc
    try:
        salt, nonce = b64d(envelope["salt"]), b64d(envelope["nonce"])
        key = Scrypt(salt=salt, length=32, n=2 ** 15, r=8, p=1).derive(code.encode("ascii"))
        clear = AESGCM(key).decrypt(nonce, b64d(envelope["ciphertext"]), _activation_aad(envelope))
        payload = json.loads(clear.decode("utf-8"))
    except (InvalidTag, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise DecryptionError("کد ملی با فایل فعال‌سازی تطابق ندارد یا فایل دست‌کاری شده است.") from exc
    expected = sha256_bytes((code + "|" + envelope["license_id"]).encode("ascii"))
    if payload.get("national_code_verifier") != expected:
        raise DecryptionError("کد ملی واردشده با مجوز مطابقت ندارد.")
    if payload.get("license_id") != envelope.get("license_id"):
        raise ExchangeError("شناسه مجوز در فایل ناسازگار است.")
    trust = {
        "format": "JAVANROOD-ADMIN-TRUST", "version": FORMAT_VERSION,
        "sign_public": envelope["admin_sign_public"],
        "exchange_public": envelope["admin_exchange_public"],
        "sign_fingerprint": envelope.get("admin_sign_fingerprint") or public_fingerprint(sign_raw),
    }
    return ActivationResult(payload=payload, trust_bundle=trust)


def _derive_package_key(shared_secret: bytes, salt: bytes, package_id: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=salt,
        info=("javanrood-client-package-v1|" + package_id).encode("ascii"),
    ).derive(shared_secret)


def _package_aad(envelope: Dict[str, Any]) -> bytes:
    aad = {
        "format": envelope["format"], "version": envelope["version"],
        "package_id": envelope["package_id"], "license_id": envelope["license_id"],
        "device_id": envelope["device_id"], "created_at": envelope["created_at"],
    }
    if int(envelope.get("version") or 0) >= 2:
        aad["key_mode"] = envelope.get("key_mode")
    return canonical_json_bytes(aad)


def _derive_license_package_key(package_secret: str, salt: bytes, package_id: str,
                                license_id: str, device_id: str) -> bytes:
    if not package_secret:
        raise ExchangeError("کلید تبادل امن این مجوز در دیتابیس موجود نیست.")
    info = f"javanrood-client-package-v2|{package_id}|{license_id}|{device_id}".encode("utf-8")
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=salt, info=info,
    ).derive(str(package_secret).encode("utf-8"))


def build_client_package(path: str, payload: Dict[str, Any], client_keys: ClientKeyStore,
                         admin_exchange_public: str) -> Dict[str, Any]:
    package_id = str(payload.get("package_id") or uuid.uuid4())
    license_id = str(payload.get("license_id") or "")
    device_id = str(payload.get("device_id") or client_keys.device_id)
    if not license_id:
        raise ExchangeError("شناسه مجوز برای ساخت خروجی موجود نیست.")
    payload = dict(payload)
    payload.update({"package_id": package_id, "license_id": license_id, "device_id": device_id})
    created_at = str(payload.get("created_at") or utc_now_iso())
    payload["created_at"] = created_at
    ephemeral = X25519PrivateKey.generate()
    admin_pub = X25519PublicKey.from_public_bytes(b64d(admin_exchange_public))
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    key = _derive_package_key(ephemeral.exchange(admin_pub), salt, package_id)
    envelope = {
        "format": PACKAGE_FORMAT,
        "version": FORMAT_VERSION,
        "package_id": package_id,
        "license_id": license_id,
        "device_id": device_id,
        "created_at": created_at,
        "ephemeral_public": b64e(raw_x25519_public(ephemeral.public_key())),
        "salt": b64e(salt),
        "nonce": b64e(nonce),
    }
    envelope["ciphertext"] = b64e(AESGCM(key).encrypt(nonce, canonical_json_bytes(payload), _package_aad(envelope)))
    envelope["signature"] = b64e(client_keys.signing_private().sign(canonical_json_bytes(envelope)))
    Path(path).write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    return envelope


def open_client_package(path: str, admin_keys: AdminKeyStore,
                        client_sign_public: str, package_secret: Optional[str] = None) -> Dict[str, Any]:
    try:
        envelope = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise ExchangeError("فایل خروجی کلاینت قابل خواندن نیست.") from exc
    package_version = int(envelope.get("version") or 0)
    if envelope.get("format") != PACKAGE_FORMAT or package_version not in {FORMAT_VERSION, PACKAGE_VERSION}:
        raise ExchangeError("فرمت فایل خروجی کلاینت پشتیبانی نمی‌شود.")
    signature = b64d(envelope.get("signature"))
    core = dict(envelope)
    core.pop("signature", None)
    try:
        Ed25519PublicKey.from_public_bytes(b64d(client_sign_public)).verify(signature, canonical_json_bytes(core))
    except (InvalidSignature, ValueError) as exc:
        raise SignatureError("امضای فایل کلاینت معتبر نیست یا با مجوز ثبت‌شده تطابق ندارد.") from exc
    try:
        salt, nonce = b64d(envelope["salt"]), b64d(envelope["nonce"])
        if package_version >= 2:
            if envelope.get("key_mode") != PACKAGE_KEY_MODE:
                raise ExchangeError("روش رمزگذاری این فایل پشتیبانی نمی‌شود.")
            key = _derive_license_package_key(
                package_secret or "", salt, str(envelope["package_id"]),
                str(envelope["license_id"]), str(envelope["device_id"]),
            )
        else:
            ephemeral = X25519PublicKey.from_public_bytes(b64d(envelope["ephemeral_public"]))
            key = _derive_package_key(admin_keys.encryption_private().exchange(ephemeral), salt, envelope["package_id"])
        clear = AESGCM(key).decrypt(nonce, b64d(envelope["ciphertext"]), _package_aad(envelope))
        payload = json.loads(clear.decode("utf-8"))
    except ExchangeError:
        raise
    except (InvalidTag, KeyError, ValueError, json.JSONDecodeError) as exc:
        if package_version == FORMAT_VERSION:
            raise DecryptionError(
                "این فایل با کلید نسخه قبلی ادمین رمز شده است. فایل را با کلاینت جدید دوباره خروجی بگیرید."
            ) from exc
        raise DecryptionError("رمزگشایی فایل کلاینت ناموفق بود؛ فایل آسیب‌دیده است یا با مجوز دیگری ساخته شده است.") from exc
    for key_name in ("package_id", "license_id", "device_id", "created_at"):
        if str(payload.get(key_name) or "") != str(envelope.get(key_name) or ""):
            raise ExchangeError(f"مشخصه {key_name} در بسته ناسازگار است.")
    return payload


def content_hash(data: Dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(data))


def validate_record(record: Dict[str, Any]) -> None:
    if not re.fullmatch(r"[0-9a-fA-F-]{32,36}", str(record.get("record_uuid") or "")):
        raise ExchangeError("شناسه یکی از رکوردهای کلاینت معتبر نیست.")
    if record.get("record_type") not in {"member", "meeting", "issue", "resolution", "action"}:
        raise ExchangeError("نوع یکی از رکوردهای کلاینت پشتیبانی نمی‌شود.")
    if int(record.get("revision") or 0) < 1:
        raise ExchangeError("شماره بازبینی یکی از رکوردها معتبر نیست.")
    if not isinstance(record.get("data"), dict):
        raise ExchangeError("محتوای یکی از رکوردها معتبر نیست.")
    expected = content_hash(record["data"])
    if record.get("content_hash") != expected:
        raise ExchangeError("هش محتوای یکی از رکوردها تطابق ندارد.")


def validate_package_payload(payload: Dict[str, Any]) -> None:
    records = payload.get("records")
    if not isinstance(records, list):
        raise ExchangeError("فهرست رکوردهای بسته معتبر نیست.")
    for item in records:
        validate_record(item)


__all__ = [
    "ExchangeError", "SignatureError", "DecryptionError", "AdminKeyStore", "ClientKeyStore",
    "PACKAGE_VERSION", "PACKAGE_KEY_MODE",
    "ActivationResult", "build_activation_request", "read_activation_request", "build_activation_file",
    "open_activation_file", "build_client_package", "open_client_package", "validate_package_payload",
    "content_hash", "sha256_file", "normalize_national_code", "national_code_hash", "password_hash",
    "verify_password", "device_fingerprint", "utc_now_iso", "parse_utc", "public_fingerprint",
]
