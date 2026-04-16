from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class SqliteStateStore:
    _DEFAULT_LOCK_TTL_SECONDS = 4 * 60 * 60

    def __init__(self, sqlite_path: str, checkpoints_json_path: str) -> None:
        self._sqlite_path = Path(sqlite_path)
        self._checkpoints_json_path = Path(checkpoints_json_path)
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._checkpoints_json_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()
        self._migrate_legacy_checkpoints_to_sqlite()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def _now_iso(self) -> str:
        return self._now_utc().isoformat()

    def _parse_iso(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _ensure_column(self, conn: sqlite3.Connection, table_name: str, column_name: str, ddl: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")}
        if column_name not in columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_locks (
                    run_key TEXT PRIMARY KEY,
                    acquired_at TEXT NOT NULL,
                    heartbeat_at TEXT,
                    expires_at TEXT
                )
                """
            )
            self._ensure_column(conn, "run_locks", "heartbeat_at", "TEXT")
            self._ensure_column(conn, "run_locks", "expires_at", "TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_items (
                    message_key TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (message_key, content_hash)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    date_ref TEXT NOT NULL,
                    status TEXT NOT NULL,
                    checkpoint TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    error TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mailbox_checkpoints (
                    mailbox TEXT PRIMARY KEY,
                    last_uid TEXT,
                    updated_at TEXT NOT NULL,
                    run_id TEXT,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _read_checkpoints(self) -> dict[str, Any]:
        if not self._checkpoints_json_path.exists():
            return {"mailboxes": {}}

        raw = self._checkpoints_json_path.read_text(encoding="utf-8")
        parsed = json.loads(raw or "{}")
        if "mailboxes" not in parsed:
            parsed["mailboxes"] = {}
        return parsed

    def _write_checkpoints(self, payload: dict[str, Any]) -> None:
        self._checkpoints_json_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _migrate_legacy_checkpoints_to_sqlite(self) -> None:
        legacy_payload = self._read_checkpoints()
        mailboxes = legacy_payload.get("mailboxes", {})
        if not isinstance(mailboxes, dict) or not mailboxes:
            return

        with self._connect() as conn:
            for mailbox, checkpoint in mailboxes.items():
                if not isinstance(checkpoint, dict):
                    continue

                existing = conn.execute(
                    "SELECT 1 FROM mailbox_checkpoints WHERE mailbox = ? LIMIT 1",
                    (str(mailbox),),
                ).fetchone()
                if existing is not None:
                    continue

                payload = dict(checkpoint)
                payload.setdefault("updated_at", self._now_iso())
                serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                conn.execute(
                    """
                    INSERT INTO mailbox_checkpoints(mailbox, last_uid, updated_at, run_id, payload_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(mailbox),
                        payload.get("last_uid"),
                        str(payload.get("updated_at") or self._now_iso()),
                        payload.get("run_id"),
                        serialized,
                    ),
                )
            conn.commit()

    def _sync_sqlite_checkpoints_to_json(self) -> None:
        payload: dict[str, Any] = {"mailboxes": {}}
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT mailbox, payload_json FROM mailbox_checkpoints ORDER BY mailbox ASC"
            ).fetchall()

        for row in rows:
            mailbox = str(row["mailbox"])
            raw_payload = row["payload_json"]
            checkpoint: dict[str, Any] = {}
            if isinstance(raw_payload, str):
                try:
                    parsed = json.loads(raw_payload)
                    if isinstance(parsed, dict):
                        checkpoint = parsed
                except json.JSONDecodeError:
                    checkpoint = {}
            payload["mailboxes"][mailbox] = checkpoint

        self._write_checkpoints(payload)

    def _purge_stale_locks(self, conn: sqlite3.Connection) -> None:
        now = self._now_utc()
        rows = conn.execute("SELECT run_key, expires_at FROM run_locks").fetchall()
        stale_keys: list[str] = []
        for row in rows:
            expires_at = self._parse_iso(str(row["expires_at"]) if row["expires_at"] else None)
            if expires_at is None or expires_at <= now:
                stale_keys.append(str(row["run_key"]))

        for run_key in stale_keys:
            conn.execute("DELETE FROM run_locks WHERE run_key = ?", (run_key,))

    def _lock_expiry_iso(self, ttl_seconds: int | None = None) -> str:
        ttl = int(ttl_seconds) if ttl_seconds is not None else self._DEFAULT_LOCK_TTL_SECONDS
        ttl = max(60, ttl)
        return (self._now_utc() + timedelta(seconds=ttl)).isoformat()

    def acquire_run_lock(self, run_key: str) -> bool:
        now = self._now_iso()
        expires_at = self._lock_expiry_iso()
        with self._connect() as conn:
            self._purge_stale_locks(conn)
            existing = conn.execute(
                "SELECT run_key FROM run_locks WHERE run_key = ? LIMIT 1",
                (run_key,),
            ).fetchone()
            if existing is not None:
                return False

            conn.execute(
                """
                INSERT INTO run_locks(run_key, acquired_at, heartbeat_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (run_key, now, now, expires_at),
            )
            conn.commit()
            return True

    def refresh_run_lock(self, run_key: str) -> bool:
        now = self._now_iso()
        expires_at = self._lock_expiry_iso()
        with self._connect() as conn:
            updated = conn.execute(
                """
                UPDATE run_locks
                SET heartbeat_at = ?, expires_at = ?
                WHERE run_key = ?
                """,
                (now, expires_at, run_key),
            )
            conn.commit()
            return updated.rowcount > 0

    def release_run_lock(self, run_key: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM run_locks WHERE run_key = ?", (run_key,))
            conn.commit()

    def get_last_checkpoint(self, mailbox: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json, last_uid, updated_at, run_id
                FROM mailbox_checkpoints
                WHERE mailbox = ?
                LIMIT 1
                """,
                (mailbox,),
            ).fetchone()

        if row is None:
            return None

        raw_payload = row["payload_json"]
        payload: dict[str, Any] = {}
        if isinstance(raw_payload, str):
            try:
                parsed = json.loads(raw_payload)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                payload = {}

        if "last_uid" not in payload:
            payload["last_uid"] = row["last_uid"]
        if "updated_at" not in payload:
            payload["updated_at"] = row["updated_at"]
        if "run_id" not in payload:
            payload["run_id"] = row["run_id"]
        return payload

    def save_checkpoint(self, mailbox: str, checkpoint: dict[str, Any]) -> None:
        payload = dict(checkpoint)
        payload.setdefault("updated_at", self._now_iso())
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mailbox_checkpoints(mailbox, last_uid, updated_at, run_id, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(mailbox) DO UPDATE SET
                    last_uid = excluded.last_uid,
                    updated_at = excluded.updated_at,
                    run_id = excluded.run_id,
                    payload_json = excluded.payload_json
                """,
                (
                    mailbox,
                    payload.get("last_uid"),
                    str(payload.get("updated_at") or self._now_iso()),
                    payload.get("run_id"),
                    serialized,
                ),
            )
            conn.commit()

    def export_checkpoints_json(self) -> None:
        self._sync_sqlite_checkpoints_to_json()

    def is_processed(self, message_id: str | None, content_hash: str) -> bool:
        message_key = message_id or ""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_items WHERE message_key = ? AND content_hash = ? LIMIT 1",
                (message_key, content_hash),
            ).fetchone()
            return row is not None

    def mark_processed(self, message_id: str | None, content_hash: str, run_id: str) -> None:
        self.mark_processed_batch([(message_id, content_hash, run_id)])

    def mark_processed_batch(self, records: list[tuple[str | None, str, str]]) -> None:
        if not records:
            return

        rows = [
            (message_id or "", content_hash, run_id, self._now_iso())
            for message_id, content_hash, run_id in records
        ]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO processed_items(message_key, content_hash, run_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()

    def start_run(self, run_id: str, date_ref: date) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs(run_id, date_ref, status, checkpoint, started_at, finished_at, error)
                VALUES (?, ?, ?, ?, ?, NULL, NULL)
                """,
                (run_id, date_ref.isoformat(), "running", "started", self._now_iso()),
            )
            conn.commit()

    def update_run_status(self, run_id: str, status: str, checkpoint: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE runs SET status = ?, checkpoint = ? WHERE run_id = ?",
                (status, checkpoint, run_id),
            )
            conn.commit()

    def finish_run(self, run_id: str, status: str, error: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = ?, finished_at = ?, error = ?
                WHERE run_id = ?
                """,
                (status, self._now_iso(), error, run_id),
            )
            conn.commit()

    def get_missed_run_dates(self, days_back: int) -> list[date]:
        today = datetime.now(timezone.utc).astimezone().date()
        if days_back <= 0:
            return []

        all_dates = [today - timedelta(days=offset) for offset in range(days_back)]
        all_dates.reverse()

        start = all_dates[0].isoformat()
        end = all_dates[-1].isoformat()

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT date_ref
                FROM runs
                WHERE date_ref BETWEEN ? AND ?
                  AND status = 'succeeded'
                """,
                (start, end),
            ).fetchall()

        completed = {row["date_ref"] for row in rows}
        return [day for day in all_dates if day.isoformat() not in completed]

    def list_runs(
        self,
        limit: int = 100,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT run_id, date_ref, status, checkpoint, started_at, finished_at, error
            FROM runs
            WHERE 1 = 1
        """
        params: list[Any] = []

        if date_from is not None:
            query += " AND date_ref >= ?"
            params.append(date_from.isoformat())
        if date_to is not None:
            query += " AND date_ref <= ?"
            params.append(date_to.isoformat())

        query += " ORDER BY date_ref DESC, started_at DESC LIMIT ?"
        params.append(int(limit))

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [dict(row) for row in rows]
