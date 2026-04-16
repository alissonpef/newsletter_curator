from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime

from ...app.types import RawEmail
from ...core.entities import EmailItem
from ...core.policies import (
    build_content_hash,
    is_allowed_sender,
    is_promotional_noise,
    should_skip_email,
)
from ...ports.state_store_port import StateStorePort


class ParseAndCleanUseCase:
    def __init__(self, normalizer, link_extractor, state_store: StateStorePort, logger) -> None:
        self._normalizer = normalizer
        self._link_extractor = link_extractor
        self._state_store = state_store
        self._logger = logger

    def _extract_text(self, raw_bytes: bytes) -> tuple[str | None, str, str, datetime, str]:
        message = BytesParser(policy=policy.default).parsebytes(raw_bytes)

        message_id = (message.get("Message-ID") or "").strip() or None
        sender = (message.get("From") or "").strip()
        subject = (message.get("Subject") or "").strip()

        date_header = message.get("Date")
        if date_header:
            try:
                received_at = parsedate_to_datetime(date_header)
                if received_at.tzinfo is None:
                    received_at = received_at.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                received_at = datetime.now(timezone.utc)
        else:
            received_at = datetime.now(timezone.utc)

        text_parts: list[str] = []
        html_parts: list[str] = []

        if message.is_multipart():
            for part in message.walk():
                if part.is_multipart():
                    continue

                content_disposition = part.get_content_disposition()
                if content_disposition == "attachment":
                    continue

                content_type = part.get_content_type()
                try:
                    payload = part.get_content()
                except KeyError:
                    continue
                if not isinstance(payload, str):
                    continue

                if content_type == "text/plain":
                    text_parts.append(payload)
                elif content_type == "text/html":
                    html_parts.append(payload)
        else:
            payload = message.get_content()
            if isinstance(payload, str):
                if message.get_content_type() == "text/html":
                    html_parts.append(payload)
                else:
                    text_parts.append(payload)

        body_text = "\n".join(text_parts).strip()
        if not body_text and html_parts:
            merged_html = "\n".join(html_parts)
            body_text = re.sub(r"<[^>]+>", " ", merged_html)

        return message_id, sender, subject, received_at, body_text

    def _is_for_reference_date(self, received_at: datetime, date_ref: date) -> bool:
        if received_at.tzinfo is None:
            return received_at.date() == date_ref
        return received_at.astimezone().date() == date_ref

    def execute(
        self,
        run_id: str,
        date_ref: date,
        raw_emails: list[RawEmail],
        negative_keywords: list[str],
        allowed_senders: list[str],
        include_previously_processed: bool = True,
    ) -> list[EmailItem]:
        processed_message_ids: set[str] = set()
        processed_hashes: set[str] = set()
        parsed_items: list[EmailItem] = []
        processed_to_persist: list[tuple[str | None, str, str]] = []
        skipped_by_date = 0
        skipped_by_sender = 0
        failed_to_parse = 0
        has_allowed_senders = any(candidate.strip() for candidate in allowed_senders)

        for uid, raw_bytes in raw_emails:
            try:
                message_id, sender, subject, received_at, body_text = self._extract_text(raw_bytes)

                if not self._is_for_reference_date(received_at=received_at, date_ref=date_ref):
                    skipped_by_date += 1
                    continue

                if not is_allowed_sender(sender=sender, allowed_senders=allowed_senders):
                    skipped_by_sender += 1
                    continue

                normalized_body = self._normalizer.normalize_email_text(body_text)
                content_hash = build_content_hash(normalized_body)

                if should_skip_email(
                    message_id=message_id,
                    content_hash=content_hash,
                    processed_message_ids=processed_message_ids,
                    processed_hashes=processed_hashes,
                ):
                    continue

                if not include_previously_processed and self._state_store.is_processed(
                    message_id,
                    content_hash,
                ):
                    continue

                if not has_allowed_senders and is_promotional_noise(
                    sender=sender,
                    subject=subject,
                    body_text=normalized_body,
                    negative_keywords=negative_keywords,
                ):
                    continue

                email_id = hashlib.sha256(
                    f"{uid}:{message_id or ''}:{content_hash}".encode("utf-8")
                ).hexdigest()
                links = self._link_extractor.extract_links(normalized_body)

                item = EmailItem(
                    id=email_id,
                    message_id=message_id or f"missing-{email_id}",
                    uid=uid,
                    sender=sender,
                    subject=subject,
                    received_at=received_at,
                    body_text=normalized_body,
                    links=links,
                )
                parsed_items.append(item)

                if message_id:
                    processed_message_ids.add(message_id)
                processed_hashes.add(content_hash)
                processed_to_persist.append((message_id, content_hash, run_id))
            except Exception:
                failed_to_parse += 1
                self._logger.exception("failed to parse email", extra={"run_id": run_id, "uid": uid})

        if processed_to_persist:
            self._state_store.mark_processed_batch(processed_to_persist)

        self._logger.info(
            "parsed and cleaned emails",
            extra={
                "run_id": run_id,
                "count": len(parsed_items),
                "skipped_by_date": skipped_by_date,
                "skipped_by_sender": skipped_by_sender,
                "failed_to_parse": failed_to_parse,
            },
        )
        return parsed_items
