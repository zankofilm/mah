# -*- coding: utf-8 -*-
"""Provider-based message sender."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

from .message_api_settings import MessageAPISettings


class ProviderError(RuntimeError):
    pass


@dataclass
class BlockMessage:
    block_id: str
    title: str
    body: str
    priority: str = "normal"

    @property
    def text(self):
        return f"{self.title}\n{self.body}".strip() if self.title else self.body.strip()


class MessageSender:
    def __init__(self, settings):
        self.settings = settings if isinstance(settings, MessageAPISettings) else MessageAPISettings.from_mapping(settings)

    @property
    def provider_title(self):
        return "ارسال آزمایشی" if self.settings.provider == "demo" else ("SMS.ir" if self.settings.provider == "sms_ir" else "API عمومی JSON")

    def _send_demo(self, mobile, message):
        return {
            "success": True,
            "message_id": f"DEMO-{uuid.uuid4().hex[:12].upper()}",
            "response": "پیام در حالت آزمایشی ثبت شد و به سرویس بیرونی ارسال نشد.",
            "mobile": mobile,
            "time": datetime.now().isoformat(timespec="seconds"),
        }

    def _send_sms_ir(self, mobile, message):
        if requests is None:
            raise ProviderError("کتابخانه requests نصب نیست.")
        payload = {
            "lineNumber": self.settings.sender_id,
            "messageText": message,
            "mobiles": [mobile],
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": self.settings.api_key,
        }
        try:
            response = requests.post(
                self.settings.api_url or "https://api.sms.ir/v1/send/bulk",
                json=payload,
                headers=headers,
                timeout=max(3, int(self.settings.timeout_seconds or 15)),
            )
        except Exception as exc:
            raise ProviderError(f"ارتباط با SMS.ir برقرار نشد: {exc}") from exc
        raw = response.text or ""
        if not response.ok:
            raise ProviderError(f"خطای SMS.ir ({response.status_code}): {raw[:500]}")
        try:
            data = response.json()
        except Exception:
            data = {"raw": raw}
        if isinstance(data, dict) and data.get("status") not in (None, 1, "1"):
            if data.get("message"):
                raise ProviderError(str(data.get("message")))
        return {"success": True, "message_id": "", "response": json.dumps(data, ensure_ascii=False)[:2000], "mobile": mobile, "time": datetime.now().isoformat(timespec="seconds")}

    def _send_generic_json(self, mobile, message):
        if requests is None:
            raise ProviderError("کتابخانه requests نصب نیست.")
        payload = {
            "to": mobile,
            "mobile": mobile,
            "receptor": mobile,
            "message": message,
            "text": message,
            "sender": self.settings.sender_id,
            "sender_id": self.settings.sender_id,
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
            headers["X-API-Key"] = self.settings.api_key
        try:
            response = requests.post(
                self.settings.api_url,
                json=payload,
                headers=headers,
                timeout=max(3, int(self.settings.timeout_seconds or 15)),
            )
        except Exception as exc:
            raise ProviderError(f"ارتباط با سرویس پیامک برقرار نشد: {exc}") from exc
        raw = response.text or ""
        if not response.ok:
            raise ProviderError(f"خطای سرویس پیامک ({response.status_code}): {raw[:500]}")
        try:
            data = response.json()
        except Exception:
            data = {"raw": raw}
        message_id = ""
        if isinstance(data, dict):
            message_id = data.get("message_id") or data.get("id") or data.get("messageId") or ""
            success_flag = data.get("success")
            if success_flag is False:
                raise ProviderError(str(data.get("message") or data.get("error") or "سرویس ارسال را ناموفق اعلام کرد."))
        return {
            "success": True,
            "message_id": str(message_id),
            "response": json.dumps(data, ensure_ascii=False)[:2000],
            "mobile": mobile,
            "time": datetime.now().isoformat(timespec="seconds"),
        }

    def send(self, mobile, message):
        self.settings.validate()
        if not mobile:
            raise ProviderError("شماره گیرنده خالی است.")
        if not message or not message.strip():
            raise ProviderError("متن پیام خالی است.")
        if self.settings.provider == "demo":
            return self._send_demo(mobile, message)
        if self.settings.provider == "sms_ir":
            return self._send_sms_ir(mobile, message)
        if self.settings.provider == "generic_json":
            return self._send_generic_json(mobile, message)
        raise ProviderError("ارائه‌دهنده پیامک پشتیبانی نمی‌شود.")
