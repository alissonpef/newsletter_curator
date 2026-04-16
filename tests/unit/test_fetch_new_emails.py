from datetime import date, datetime, timezone

from hermes.app.use_cases.fetch_new_emails import FetchNewEmailsUseCase


class DummyImapPort:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def fetch_new(self, **kwargs):
        self.calls.append(kwargs)
        return [("42", b"raw")]


class DummyStateStore:
    def __init__(self) -> None:
        self.saved: list[tuple[str, dict[str, object]]] = []
        self.last_checkpoint = {"last_uid": "41"}

    def get_last_checkpoint(self, mailbox: str):
        return self.last_checkpoint

    def save_checkpoint(self, mailbox: str, checkpoint: dict[str, object]) -> None:
        self.saved.append((mailbox, checkpoint))


class DummyLogger:
    def info(self, *args, **kwargs) -> None:
        return None


def test_execute_uses_incremental_checkpoint_by_default() -> None:
    imap_port = DummyImapPort()
    state_store = DummyStateStore()
    use_case = FetchNewEmailsUseCase(imap_port=imap_port, state_store=state_store, logger=DummyLogger())

    payload = use_case.execute(
        run_id="run-1",
        mailbox="INBOX",
        search_strategy="UID",
        since=datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc),
    )

    assert payload == [("42", b"raw")]
    assert imap_port.calls[0]["last_uid"] == "41"
    assert imap_port.calls[0]["reference_date"] is None
    assert state_store.saved[0][0] == "INBOX"
    assert state_store.saved[0][1]["last_uid"] == "42"


def test_execute_reference_date_mode_bypasses_checkpoint_updates() -> None:
    imap_port = DummyImapPort()
    state_store = DummyStateStore()
    use_case = FetchNewEmailsUseCase(imap_port=imap_port, state_store=state_store, logger=DummyLogger())

    use_case.execute(
        run_id="run-2",
        mailbox="INBOX",
        search_strategy="UID",
        since=datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc),
        reference_date=date(2026, 4, 14),
    )

    assert imap_port.calls[0]["last_uid"] is None
    assert imap_port.calls[0]["since"] is None
    assert imap_port.calls[0]["reference_date"] == date(2026, 4, 14)
    assert state_store.saved == []
