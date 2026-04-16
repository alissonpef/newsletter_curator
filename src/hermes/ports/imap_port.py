from datetime import date, datetime
from typing import Protocol


class ImapPort(Protocol):
    def fetch_new(
        self,
        mailbox: str,
        search_strategy: str,
        since: datetime | None,
        last_uid: str | None,
        reference_date: date | None = None,
    ) -> list[tuple[str, bytes]]: ...
