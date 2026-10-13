"""Parameterized SQLite persistence with transaction and ownership boundaries."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class DuplicateConflict(Exception):
    pass


class Store:
    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = data_dir / "aerzen.sqlite3"
        self.initialize()
        os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self):
        with self.connect() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS leads (
                  id TEXT PRIMARY KEY, owner_hash TEXT NOT NULL, nonce TEXT NOT NULL UNIQUE,
                  payload_hash TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL,
                  policy_version TEXT NOT NULL, consent_at INTEGER NOT NULL, created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS orders (
                  id TEXT PRIMARY KEY, owner_hash TEXT NOT NULL, nonce TEXT NOT NULL UNIQUE,
                  payload_hash TEXT NOT NULL, buyer TEXT NOT NULL, items TEXT NOT NULL,
                  total_kopecks INTEGER NOT NULL CHECK(total_kopecks > 0),
                  status TEXT NOT NULL DEFAULT 'awaiting_payment' CHECK(status IN ('awaiting_payment','paid','cancelled')),
                  seller_snapshot TEXT NOT NULL, policy_version TEXT NOT NULL, created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rate_buckets (
                  id INTEGER PRIMARY KEY, key TEXT NOT NULL, time INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS rate_time ON rate_buckets(time);
            """)

    def consume_rate(self, key: str, limit: int, window: int) -> bool:
        now = int(time.time())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM rate_buckets WHERE time < ?", (now - window,))
            count = db.execute("SELECT COUNT(*) FROM rate_buckets WHERE key = ? AND time >= ?", (key, now-window)).fetchone()[0]
            if count >= limit:
                return False
            db.execute("INSERT INTO rate_buckets(key,time) VALUES(?,?)", (key, now))
        return True

    def save_lead(self, data: dict) -> tuple[dict, bool]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM leads WHERE nonce = ?", (data["nonce"],)).fetchone()
            if row:
                if row["owner_hash"] != data["owner_hash"] or row["payload_hash"] != data["payload_hash"]:
                    raise DuplicateConflict()
                return dict(row), False
            db.execute("INSERT INTO leads VALUES(?,?,?,?,?,?,?,?,?)", (
                data["id"], data["owner_hash"], data["nonce"], data["payload_hash"], data["kind"],
                json.dumps(data["payload"], ensure_ascii=False), data["policy_version"], data["created_at"], data["created_at"]))
            return data, True

    def save_order(self, data: dict) -> tuple[dict, bool]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM orders WHERE nonce = ?", (data["nonce"],)).fetchone()
            if row:
                if row["owner_hash"] != data["owner_hash"] or row["payload_hash"] != data["payload_hash"]:
                    raise DuplicateConflict()
                return dict(row), False
            db.execute("""INSERT INTO orders(id,owner_hash,nonce,payload_hash,buyer,items,total_kopecks,status,seller_snapshot,policy_version,created_at)
                          VALUES(?,?,?,?,?,?,?,'awaiting_payment',?,?,?)""", (
                data["id"],data["owner_hash"],data["nonce"],data["payload_hash"],json.dumps(data["buyer"],ensure_ascii=False),
                json.dumps(data["items"],ensure_ascii=False),data["total_kopecks"],json.dumps(data["seller_snapshot"],ensure_ascii=False),
                data["policy_version"],data["created_at"]))
            return data, True

    def order_for_owner(self, public_id: str, owner_hash: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM orders WHERE id=? AND owner_hash=?", (public_id,owner_hash)).fetchone()
        if not row:
            return None
        value = dict(row)
        for key in ("buyer", "items", "seller_snapshot"):
            value[key] = json.loads(value[key])
        return value
