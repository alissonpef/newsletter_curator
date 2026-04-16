import hashlib
from datetime import date
from email.utils import parseaddr

from .entities import EmailItem


def build_content_hash(body_text: str) -> str:
    normalized = " ".join(body_text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def should_skip_email(
    message_id: str | None,
    content_hash: str,
    processed_message_ids: set[str],
    processed_hashes: set[str],
) -> bool:
    if message_id and message_id in processed_message_ids:
        return True
    return content_hash in processed_hashes


def is_promotional_noise(
    sender: str,
    subject: str,
    body_text: str,
    negative_keywords: list[str],
) -> bool:
    if not negative_keywords:
        return False

    haystack = f"{sender}\n{subject}\n{body_text}".lower()
    return any(keyword.lower() in haystack for keyword in negative_keywords if keyword)


def normalize_sender_email(sender: str) -> str:
    _, address = parseaddr(sender)
    normalized = address.strip().lower()
    if normalized:
        return normalized
    return sender.strip().lower()


def is_allowed_sender(sender: str, allowed_senders: list[str]) -> bool:
    if not allowed_senders:
        return True

    sender_email = normalize_sender_email(sender)
    allowed = {candidate.strip().lower() for candidate in allowed_senders if candidate.strip()}
    return sender_email in allowed


def resolve_namespace(date_ref: date) -> str:
    return f"daily::{date_ref.isoformat()}"


def estimate_tokens(text: str) -> int:
    if not text.strip():
        return 0

    words = len(text.split())
    return max(1, (words * 4) // 3)
