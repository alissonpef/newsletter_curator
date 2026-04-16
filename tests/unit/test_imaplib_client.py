from datetime import date, datetime, timezone

from hermes.adapters.imap.imaplib_client import ImaplibClient


def test_build_search_terms_uses_exact_date_window_when_reference_date_is_present() -> None:
    client = ImaplibClient(host="imap.example.com", port=993, username="user", password="pass")

    terms = client._build_search_terms(
        search_strategy="UID",
        since=datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
        last_uid="99",
        reference_date=date(2026, 4, 15),
    )

    assert terms == ("SINCE", "15-Apr-2026", "BEFORE", "16-Apr-2026")


def test_build_search_terms_preserves_incremental_uid_search_without_reference_date() -> None:
    client = ImaplibClient(host="imap.example.com", port=993, username="user", password="pass")

    terms = client._build_search_terms(
        search_strategy="UID",
        since=None,
        last_uid="99",
    )

    assert terms == ("UID", "100:*")
