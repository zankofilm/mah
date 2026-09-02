# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from client_exchange_core import (
    ClientKeyStore, ExchangeError, device_fingerprint, open_activation_file,
    parse_utc, utc_now_iso, verify_password,
)
from client_runtime import data_dir


class LicenseStore:
    def __init__(self):
        self.root = data_dir()
        self.security = self.root / "security"
        self.security.mkdir(parents=True, exist_ok=True)
        self.key_store = ClientKeyStore(str(self.security), expected_device_id=device_fingerprint())
        self.vault_secret = self.security / "license_vault_secret.bin"
        self.state_path = self.security / "license_state.bin"
        self.trust_path = self.security / "admin_trust.json"
        if not self.vault_secret.exists():
            self.vault_secret.write_bytes(secrets.token_bytes(48))
            try: os.chmod(self.vault_secret, 0o600)
            except Exception: pass

    def _vault_key(self) -> bytes:
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                    info=b"javanrood-client-license-v1").derive(
            self.vault_secret.read_bytes() + self.key_store.device_id.encode("ascii")
        )

    def _write_state(self, state: Dict[str, Any]):
        nonce = secrets.token_bytes(12)
        clear = json.dumps(state, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.state_path.write_bytes(nonce + AESGCM(self._vault_key()).encrypt(nonce, clear, b"license-state-v1"))
        try: os.chmod(self.state_path, 0o600)
        except Exception: pass

    def load(self) -> Optional[Dict[str, Any]]:
        if not self.state_path.exists():
            return None
        try:
            blob = self.state_path.read_bytes()
            clear = AESGCM(self._vault_key()).decrypt(blob[:12], blob[12:], b"license-state-v1")
            return json.loads(clear.decode("utf-8"))
        except Exception as exc:
            raise ExchangeError("فایل مجوز محلی آسیب دیده یا به دستگاه دیگری منتقل شده است.") from exc

    def trusted_sign_public(self) -> Optional[str]:
        if not self.trust_path.exists():
            return None
        try:
            return json.loads(self.trust_path.read_text(encoding="utf-8")).get("sign_public")
        except Exception:
            return None

    def install(self, activation_path: str, national_code: str) -> Dict[str, Any]:
        current = self.load()
        result = open_activation_file(activation_path, national_code, self.trusted_sign_public())
        payload = dict(result.payload)
        if payload.get("device_id") != self.key_store.device_id:
            raise ExchangeError("این فایل برای دستگاه دیگری صادر شده است.")
        if payload.get("client_sign_public") and payload["client_sign_public"] != __import__('client_exchange_core').b64e(self.key_store.signing_public_raw()):
            raise ExchangeError("کلید امضای این دستگاه با درخواست فعال‌سازی تطابق ندارد.")
        if current:
            if payload.get("license_id") != current.get("license_id"):
                raise ExchangeError("فایل انتخابی مربوط به مجوز دیگری است.")
            for field in ("zone_id", "committee_code", "device_id"):
                if str(payload.get(field)) != str(current.get(field)):
                    raise ExchangeError("فایل تمدید نمی‌تواند محدوده دسترسی یا دستگاه را تغییر دهد.")
            merged = dict(current)
            merged.update(payload)
            if not payload.get("password_hash"):
                merged["password_hash"] = current.get("password_hash")
            payload = merged
        payload["installed_at"] = utc_now_iso()
        payload["last_seen_utc"] = utc_now_iso()
        self._write_state(payload)
        self.trust_path.write_text(json.dumps(result.trust_bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    @staticmethod
    def _end_time(value: str) -> datetime:
        text = str(value or "")
        if "T" not in text:
            text += "T23:59:59+00:00"
        return parse_utc(text)

    @staticmethod
    def _start_time(value: str) -> datetime:
        text = str(value or "")
        if "T" not in text:
            text += "T00:00:00+00:00"
        return parse_utc(text)

    def validate(self, update_clock=True) -> Dict[str, Any]:
        state = self.load()
        if not state:
            return {"status": "not_activated", "license": None, "message": "کلاینت هنوز فعال نشده است."}
        now = datetime.now(timezone.utc)
        try:
            last = parse_utc(state.get("last_seen_utc") or utc_now_iso())
        except Exception:
            last = now
        if now.timestamp() + 300 < last.timestamp():
            return {"status": "clock_rollback", "license": state, "message": "ساعت سیستم نسبت به آخرین اجرای معتبر به عقب برگشته است. فایل تمدید یا تأیید مدیر لازم است."}
        if state.get("status") not in (None, "فعال"):
            return {"status": "blocked", "license": state, "message": f"مجوز در وضعیت «{state.get('status')}» است."}
        start = self._start_time(state.get("valid_from"))
        end = self._end_time(state.get("valid_until"))
        if now < start:
            return {"status": "not_yet_valid", "license": state, "message": "تاریخ شروع اعتبار این کلاینت هنوز نرسیده است."}
        if now > end:
            return {"status": "expired", "license": state, "message": f"اعتبار کلاینت در تاریخ {state.get('valid_until')} پایان یافته است."}
        remaining = max(0, int((end - now).total_seconds() // 86400) + 1)
        if update_clock:
            state["last_seen_utc"] = utc_now_iso()
            self._write_state(state)
        return {"status": "valid", "license": state, "remaining_days": remaining, "message": "مجوز معتبر است."}

    def authenticate(self, username: str, password: str) -> bool:
        result = self.validate(update_clock=True)
        if result["status"] != "valid":
            return False
        lic = result["license"]
        return username.strip().lower() == str(lic.get("username") or "").strip().lower() and verify_password(password, lic.get("password_hash") or "")

    def data_key(self) -> bytes:
        state = self.load()
        if not state:
            raise ExchangeError("کلاینت فعال نشده است.")
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=state["license_id"].encode("ascii"),
                    info=b"javanrood-client-data-v1").derive(
            self.vault_secret.read_bytes() + self.key_store.device_id.encode("ascii")
        )
