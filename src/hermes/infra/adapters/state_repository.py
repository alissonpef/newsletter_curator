import sqlite3
import json
import os
from hermes.core.interfaces import StateRepositoryPort


class SqliteStateRepository(StateRepositoryPort):
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    date_ref TEXT PRIMARY KEY,
                    data TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS digests (
                    date_ref TEXT PRIMARY KEY,
                    data TEXT
                )
            """)
            conn.commit()

    def get_job(self, date_ref: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data FROM jobs WHERE date_ref = ?", (date_ref,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    def save_job(self, date_ref: str, job: dict):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO jobs (date_ref, data) VALUES (?, ?)",
                (date_ref, json.dumps(job)),
            )
            conn.commit()

    def get_digest(self, date_ref: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data FROM digests WHERE date_ref = ?", (date_ref,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    def save_digest(self, date_ref: str, digest: dict):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO digests (date_ref, data) VALUES (?, ?)",
                (date_ref, json.dumps(digest)),
            )
            conn.commit()
