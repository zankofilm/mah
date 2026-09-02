# -*- coding: utf-8 -*-
"""Message API settings model."""
from dataclasses import dataclass


@dataclass
class MessageAPISettings:
    provider: str = "demo"
    api_url: str = ""
    api_key: str = ""
    sender_id: str = ""
    enabled: bool = True
    timeout_seconds: int = 15

    @classmethod
    def from_mapping(cls, data):
        data = data or {}
        return cls(
            provider=data.get("provider") or "demo",
            api_url=data.get("api_url") or "",
            api_key=data.get("api_key") or "",
            sender_id=data.get("sender_id") or "",
            enabled=bool(data.get("enabled", True)),
            timeout_seconds=int(data.get("timeout_seconds") or 15),
        )

    def validate(self):
        if not self.enabled:
            raise ValueError("سامانه ارسال پیام در تنظیمات غیرفعال است.")
        if self.provider == "generic_json":
            if not self.api_url:
                raise ValueError("آدرس API پیامک وارد نشده است.")
            if not self.api_key:
                raise ValueError("کلید API پیامک وارد نشده است.")
        return True
