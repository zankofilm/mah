# -*- coding: utf-8 -*-
"""Application service for selecting block members and reliable message delivery."""
from __future__ import annotations

from .message_api_settings import MessageAPISettings
from .message_sender import BlockMessage, MessageSender


class BlockMessagingService:
    def __init__(self, db):
        self.db = db

    def get_settings(self):
        return MessageAPISettings.from_mapping(self.db.get_message_api_settings())

    def get_recipients(self, block_id, scope="all"):
        return self.db.get_message_recipients(block_id, scope)

    def _deliver(self, campaign_id, message, recipients, settings, progress_callback=None):
        sender = MessageSender(settings)
        results = []
        total = len(recipients)
        for index, recipient in enumerate(recipients, start=1):
            if self.db.is_message_campaign_paused(campaign_id):
                break
            mobile = recipient.get("mobile")
            try:
                result = sender.send(mobile, message.text)
                self.db.record_message_delivery(
                    campaign_id, mobile, True,
                    provider_message_id=result.get("message_id"),
                    response_text=result.get("response"),
                )
                results.append({"recipient": recipient, "success": True, "result": result})
            except Exception as exc:
                self.db.record_message_delivery(campaign_id, mobile, False, error_text=str(exc))
                results.append({"recipient": recipient, "success": False, "error": str(exc)})
            if progress_callback:
                progress_callback(index, total, recipient, results[-1])
        summary = self.db.finish_message_campaign(campaign_id)
        summary.update({"campaign_id": campaign_id, "results": results})
        return summary

    def send_to_recipients(self, block_id, title, body, recipients, scope="all", priority="normal", progress_callback=None):
        settings = self.get_settings()
        settings.validate()
        message = BlockMessage(str(block_id), title, body, priority)
        campaign_id = self.db.create_message_campaign(
            block_id, title, body, scope, priority, settings.provider, recipients
        )
        return self._deliver(campaign_id, message, recipients, settings, progress_callback)

    def retry_campaign(self, campaign_id, progress_callback=None):
        campaign = self.db.get_message_campaign(campaign_id)
        if not campaign:
            raise ValueError("عملیات ارسال پیدا نشد.")
        self.db.retry_failed_message_deliveries(campaign_id)
        pending = self.db.get_pending_message_deliveries(campaign_id)
        if not pending:
            raise ValueError("پیام ناموفقی برای ارسال مجدد وجود ندارد.")
        settings = self.get_settings()
        settings.validate()
        message = BlockMessage(str(campaign.get("zone_id")), campaign.get("title") or "",
                               campaign.get("body") or "", campaign.get("priority") or "normal")
        recipients = [{"name": x.get("recipient_name"), "mobile": x.get("mobile")} for x in pending]
        return self._deliver(campaign_id, message, recipients, settings, progress_callback)

    def pause_campaign(self, campaign_id):
        return self.db.pause_message_campaign(campaign_id)

    def resume_campaign(self, campaign_id):
        return self.db.resume_message_campaign(campaign_id)
