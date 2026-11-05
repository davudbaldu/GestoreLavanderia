"""Durable read transport, independent of reader SDKs and printer drivers.

This preserves observations during outages; it does not assign cabinet slots
without the server and is not an offline sorting engine. Store the database
outside the public site/repository. Credentials belong to the caller, not here.
"""
from __future__ import annotations
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

class ReadOutbox:
    def __init__(self, path: str | Path):
        self.path = str(path)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('''CREATE TABLE IF NOT EXISTS observations(
                seq INTEGER PRIMARY KEY, id TEXT NOT NULL UNIQUE,
                session_id TEXT NOT NULL, kind TEXT NOT NULL,
                payload TEXT NOT NULL, result TEXT,
                attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT)''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def enqueue(self, session_id: str, kind: str, tag: str, observed_at: str | None = None, metadata: dict | None = None) -> str:
        uuid.UUID(session_id)
        if kind not in ('sporco', 'pulito') or not isinstance(tag, str) or len(tag) > 256:
            raise ValueError('Invalid observation envelope')
        if metadata is not None and (not isinstance(metadata, dict) or len(json.dumps(metadata).encode('utf-8')) > 4096):
            raise ValueError('Invalid reader metadata')
        event_id = str(uuid.uuid4())
        payload = {'id': event_id, 'tag': tag,
                   'observed_at': observed_at or datetime.now(timezone.utc).isoformat()}
        if metadata is not None:
            payload['metadata'] = metadata
        with self.connect() as db:
            db.execute('INSERT INTO observations(id,session_id,kind,payload) VALUES(?,?,?,?)',
                       (event_id, session_id, kind, json.dumps(payload)))
        return event_id

    def pending(self) -> int:
        with self.connect() as db:
            return db.execute('SELECT count(*) FROM observations WHERE result IS NULL').fetchone()[0]

    def sync_once(self, send) -> int:
        """Call send(session_id, events); acknowledge only exact server event IDs.

        One worker per outbox is expected. Multiple workers may retransmit the
        same IDs, which the server must treat idempotently. A rejected logical
        read (unknown tag, duplicate, wrong client) is an acknowledged outcome,
        not a network failure to retry forever.
        """
        with self.connect() as db:
            rows = db.execute('SELECT seq,id,session_id,kind,payload FROM observations WHERE result IS NULL ORDER BY seq LIMIT 500').fetchall()
        if not rows:
            return 0
        first = rows[0]
        batch = []
        for row in rows:
            if row[2:4] != first[2:4] or (first[3] == 'pulito' and batch):
                break
            batch.append(row)
        ids = {row[1] for row in batch}
        try:
            results = send(first[2], [json.loads(row[4]) for row in batch])
            if not isinstance(results, list) or len(results) != len(batch) or {r.get('id') for r in results if isinstance(r, dict)} != ids:
                raise ValueError('Server acknowledgement does not match the sent observations')
            if any(not isinstance(r.get('outcome'), str) for r in results):
                raise ValueError('Server acknowledgement lacks the read outcome')
        except Exception as exc:
            with self.connect() as db:
                db.executemany('UPDATE observations SET attempts=attempts+1,last_error=? WHERE id=?',
                               [(str(exc)[:1000], row[1]) for row in batch])
            raise
        with self.connect() as db:
            db.executemany('UPDATE observations SET result=?,attempts=attempts+1,last_error=NULL WHERE id=?',
                           [(json.dumps(result), result['id']) for result in results])
        return len(batch)
