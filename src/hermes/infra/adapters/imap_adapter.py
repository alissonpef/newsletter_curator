from __future__ import annotations

import contextlib
import email
import imaplib
from datetime import datetime, timedelta
from email.header import decode_header
from email.message import Message

from bs4 import BeautifulSoup

from hermes.core.interfaces import EmailPort


class ImapAdapter(EmailPort):
    def __init__(
        self,
        host,
        port,
        user,
        password,
        use_ssl,
        mailbox,
        search_strategy,
        allowed_senders,
    ):
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.use_ssl = str(use_ssl).lower() == "true"
        self.mailbox = mailbox
        self.search_strategy = str(search_strategy or "").strip().upper() or "SINCE"
        self.allowed_senders = [
            sender.strip().lower() for sender in str(allowed_senders).split(",") if sender.strip()
        ]

    def _build_search_queries(self, search_date: str) -> list[str]:
        next_date = (datetime.strptime(search_date, "%d-%b-%Y") + timedelta(days=1)).strftime(
            "%d-%b-%Y"
        )
        strategy = self.search_strategy

        if strategy == "ON":
            return [f"(ON {search_date})"]

        return [f"(SINCE {search_date} BEFORE {next_date})", f"(ON {search_date})"]

    def _decode_header_value(self, value: str | None) -> str:
        if not value:
            return ""

        parts = []
        for part, encoding in decode_header(value):
            if isinstance(part, bytes):
                parts.append(part.decode(encoding or "utf-8", errors="ignore"))
            else:
                parts.append(part)
        return "".join(parts).strip()

    def _normalize_sender(self, sender: str) -> str:
        sender_email = sender
        if "<" in sender and ">" in sender:
            sender_email = sender.split("<", 1)[1].split(">", 1)[0]
        return sender_email.lower().strip()

    def _extract_html_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        for image in soup.find_all("img"):
            image.decompose()

        for anchor in soup.find_all("a"):
            text = anchor.get_text(" ", strip=True)
            anchor.replace_with(text if text else "")

        text = soup.get_text(separator="\n")
        return "\n".join(line.strip() for line in text.splitlines() if line.strip())

    def _extract_message_text(self, msg: Message) -> str:
        if msg.is_multipart():
            html_part = None
            text_part = None
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))
                if "attachment" in disposition.lower():
                    continue
                if content_type == "text/html":
                    html_part = part
                elif content_type == "text/plain":
                    text_part = part

            best_part = html_part or text_part
            if not best_part:
                return ""

            payload = best_part.get_payload(decode=True) or b""
            text = payload.decode(best_part.get_content_charset() or "utf-8", errors="ignore")
            if best_part.get_content_type() == "text/html":
                return self._extract_html_text(text)
            return text

        payload = msg.get_payload(decode=True) or b""
        text = payload.decode(msg.get_content_charset() or "utf-8", errors="ignore")
        if msg.get_content_type() == "text/html":
            return self._extract_html_text(text)
        return text

    def _build_search_query(self, date_ref: str) -> str:
        date_obj = datetime.strptime(date_ref, "%Y-%m-%d")
        start_date = date_obj.strftime("%d-%b-%Y")
        next_date = (date_obj + timedelta(days=1)).strftime("%d-%b-%Y")

        strategy = (self.search_strategy or "").strip().upper()
        if strategy == "ON":
            return f"(ON {start_date})"

        return f"(SINCE {start_date} BEFORE {next_date})"

    def fetch_emails(self, date_ref: str) -> list[dict[str, str]]:
        mail = (
            imaplib.IMAP4_SSL(self.host, self.port)
            if self.use_ssl
            else imaplib.IMAP4(self.host, self.port)
        )
        try:
            mail.login(self.user, self.password)
            mail.select(self.mailbox)

            date_obj = datetime.strptime(date_ref, "%Y-%m-%d")
            search_date = date_obj.strftime("%d-%b-%Y")

            message_ids: list[bytes] = []
            for query in self._build_search_queries(search_date):
                status, messages = mail.search(None, query)
                if status != "OK":
                    continue
                message_ids = [message_id for message_id in messages[0].split() if message_id]
                if message_ids:
                    break

            if not message_ids:
                return []

            results: list[dict[str, str]] = []
            seen_ids = set()
            for email_id in message_ids:
                if email_id in seen_ids:
                    continue
                seen_ids.add(email_id)

                response_status, msg_data = mail.fetch(email_id, "(RFC822)")
                if response_status != "OK":
                    continue

                for response_part in msg_data:
                    if not isinstance(response_part, tuple):
                        continue

                    msg = email.message_from_bytes(response_part[1])
                    sender = self._decode_header_value(msg.get("From"))
                    if not sender:
                        continue

                    sender_email = self._normalize_sender(sender)
                    if self.allowed_senders and sender_email not in self.allowed_senders:
                        continue

                    content = self._extract_message_text(msg).strip()
                    if not content:
                        continue

                    results.append(
                        {
                            "sender": sender_email,
                            "subject": self._decode_header_value(msg.get("Subject")),
                            "content": content,
                        }
                    )

            return results
        finally:
            with contextlib.suppress(Exception):
                mail.logout()
