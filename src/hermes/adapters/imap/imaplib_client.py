from __future__ import annotations

import imaplib
import re
from datetime import date, datetime, timedelta

from ...core.errors import ImapFetchError
from ...infra.retries import io_retry


_UID_HEADER_PATTERN = re.compile(r"UID\s+(\d+)", flags=re.IGNORECASE)


class ImaplibClient:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_ssl: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_ssl = use_ssl

    def _create_client(self):
        if self._use_ssl:
            return imaplib.IMAP4_SSL(self._host, self._port)
        return imaplib.IMAP4(self._host, self._port)

    def _build_search_terms(
        self,
        search_strategy: str,
        since: datetime | None,
        last_uid: str | None,
        reference_date: date | None = None,
    ) -> tuple[str, ...]:
        if reference_date is not None:
            next_day = reference_date + timedelta(days=1)
            return (
                "SINCE",
                reference_date.strftime("%d-%b-%Y"),
                "BEFORE",
                next_day.strftime("%d-%b-%Y"),
            )

        strategy = search_strategy.upper().strip()

        if strategy == "UID" and last_uid:
            try:
                start_uid = str(int(last_uid) + 1)
            except ValueError:
                start_uid = last_uid
            return ("UID", f"{start_uid}:*")

        if since is not None:
            return ("SINCE", since.strftime("%d-%b-%Y"))

        return ("ALL",)

    def fetch_new(
        self,
        mailbox: str,
        search_strategy: str,
        since: datetime | None,
        last_uid: str | None,
        reference_date: date | None = None,
    ) -> list[tuple[str, bytes]]:
        try:
            return self._fetch_new_with_retry(
                mailbox=mailbox,
                search_strategy=search_strategy,
                since=since,
                last_uid=last_uid,
                reference_date=reference_date,
            )
        except Exception as exc:
            raise ImapFetchError("imap fetch_new failed") from exc

    @io_retry()
    def _fetch_new_with_retry(
        self,
        mailbox: str,
        search_strategy: str,
        since: datetime | None,
        last_uid: str | None,
        reference_date: date | None = None,
    ) -> list[tuple[str, bytes]]:
        try:
            with self._create_client() as client:
                login_status, _ = client.login(self._username, self._password)
                if login_status != "OK":
                    raise ConnectionError("imap login failed")

                select_status, _ = client.select(mailbox, readonly=True)
                if select_status != "OK":
                    raise ConnectionError(f"unable to select mailbox: {mailbox}")

                terms = self._build_search_terms(
                    search_strategy=search_strategy,
                    since=since,
                    last_uid=last_uid,
                    reference_date=reference_date,
                )
                search_status, search_data = client.uid("search", None, *terms)
                if search_status != "OK" or not search_data:
                    return []

                uid_values = [
                    uid.decode("utf-8", errors="ignore")
                    for uid in search_data[0].split()
                    if uid
                ]
                items: list[tuple[str, bytes]] = []

                for uid_batch in self._iter_uid_batches(uid_values):
                    message_set = ",".join(uid_batch)
                    fetched = self._fetch_uid_batch(client, message_set=message_set)
                    items.extend(fetched)

                if not items:
                    return []

                items.sort(key=lambda item: int(item[0]) if item[0].isdigit() else item[0])
                return items
        except Exception as exc:
            raise ConnectionError("imap fetch_new failed") from exc

    def _iter_uid_batches(self, uid_values: list[str], batch_size: int = 25):
        for index in range(0, len(uid_values), batch_size):
            yield uid_values[index : index + batch_size]

    def _fetch_uid_batch(self, client, message_set: str) -> list[tuple[str, bytes]]:
        fetch_status, fetch_data = client.uid("fetch", message_set, "(UID RFC822)")
        if fetch_status != "OK" or not fetch_data:
            return []

        items: list[tuple[str, bytes]] = []
        for payload in fetch_data:
            if not isinstance(payload, tuple) or len(payload) < 2:
                continue

            header = payload[0]
            raw = payload[1]
            if not isinstance(raw, bytes):
                continue

            header_text = ""
            if isinstance(header, bytes):
                header_text = header.decode("utf-8", errors="ignore")
            elif isinstance(header, str):
                header_text = header

            match = _UID_HEADER_PATTERN.search(header_text)
            if match is None:
                continue

            uid_value = match.group(1)
            items.append((uid_value, raw))
        return items
