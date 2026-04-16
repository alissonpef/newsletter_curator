from datetime import date, datetime, timezone

from ...app.types import RawEmail
from ...ports.imap_port import ImapPort
from ...ports.state_store_port import StateStorePort


class FetchNewEmailsUseCase:
    def __init__(self, imap_port: ImapPort, state_store: StateStorePort, logger) -> None:
        self._imap_port = imap_port
        self._state_store = state_store
        self._logger = logger

    def _max_uid(self, raw_emails: list[RawEmail]) -> str | None:
        if not raw_emails:
            return None

        numeric_uids: list[int] = []
        fallback_uids: list[str] = []
        for uid, _ in raw_emails:
            try:
                numeric_uids.append(int(uid))
            except (TypeError, ValueError):
                fallback_uids.append(str(uid))

        if numeric_uids:
            return str(max(numeric_uids))
        return max(fallback_uids) if fallback_uids else None

    def execute(
        self,
        run_id: str,
        mailbox: str,
        search_strategy: str,
        since: datetime | None,
        reference_date: date | None = None,
    ) -> list[RawEmail]:
        fetch_mode = "reference_date" if reference_date is not None else "incremental"
        last_uid = None
        if reference_date is None:
            checkpoint = self._state_store.get_last_checkpoint(mailbox) or {}
            last_uid = checkpoint.get("last_uid")

        self._logger.info(
            "fetching new emails",
            extra={
                "run_id": run_id,
                "mailbox": mailbox,
                "search_strategy": search_strategy,
                "last_uid": last_uid,
                "fetch_mode": fetch_mode,
                "reference_date": reference_date.isoformat() if reference_date else None,
            },
        )

        raw_emails = self._imap_port.fetch_new(
            mailbox=mailbox,
            search_strategy=search_strategy,
            since=since if reference_date is None else None,
            last_uid=last_uid,
            reference_date=reference_date,
        )

        if reference_date is None and raw_emails:
            max_uid = self._max_uid(raw_emails)
            self._state_store.save_checkpoint(
                mailbox,
                {
                    "last_uid": max_uid,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "run_id": run_id,
                },
            )

        self._logger.info(
            "fetched emails",
            extra={
                "run_id": run_id,
                "count": len(raw_emails),
                "fetch_mode": fetch_mode,
            },
        )
        return raw_emails
