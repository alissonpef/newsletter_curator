from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hermes.adapters.state.sqlite_state_store import SqliteStateStore


def _build_store(tmp_path) -> SqliteStateStore:
    return SqliteStateStore(
        sqlite_path=str(tmp_path / "state.sqlite"),
        checkpoints_json_path=str(tmp_path / "checkpoints.json"),
    )


def test_acquire_run_lock_reclaims_expired_lock(tmp_path) -> None:
    store = _build_store(tmp_path)
    run_key = "2026-04-15"
    expired = (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat()

    with store._connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO run_locks(run_key, acquired_at, heartbeat_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (run_key, expired, expired, expired),
        )
        conn.commit()

    assert store.acquire_run_lock(run_key) is True


def test_save_and_read_checkpoint_uses_sqlite_canonical_data(tmp_path) -> None:
    store = _build_store(tmp_path)
    checkpoint = {
        "last_uid": "123",
        "updated_at": datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc).isoformat(),
        "run_id": "run-1",
        "mailbox_state": "steady",
    }

    store.save_checkpoint("INBOX", checkpoint)
    loaded = store.get_last_checkpoint("INBOX")

    assert loaded is not None
    assert loaded["last_uid"] == "123"
    assert loaded["run_id"] == "run-1"
    assert loaded["mailbox_state"] == "steady"


def test_mark_processed_batch_persists_records(tmp_path) -> None:
    store = _build_store(tmp_path)

    store.mark_processed_batch(
        [
            (None, "hash-a", "run-1"),
            ("<msg@example.com>", "hash-b", "run-1"),
        ]
    )

    assert store.is_processed(None, "hash-a") is True
    assert store.is_processed("<msg@example.com>", "hash-b") is True
