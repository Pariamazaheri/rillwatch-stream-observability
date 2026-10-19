"""Transactional local journal: raw payload and classification commit together."""

import base64
import csv
import json
import sqlite3
from pathlib import Path

from .validation import FIELDS, parse


class Store:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY, source TEXT NOT NULL, epoch TEXT NOT NULL,
          sequence INTEGER NOT NULL, received REAL NOT NULL, raw BLOB NOT NULL,
          record TEXT, errors TEXT NOT NULL, status TEXT NOT NULL,
          UNIQUE(source, epoch, sequence));
        CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        """)

    def ingest(self, source, epoch, sequence, received, raw, frame_error=None):
        record, errors = parse(raw)
        if frame_error:
            errors = [frame_error] + errors
        status = "bad" if errors else "clean"
        serialized = json.dumps(record, allow_nan=False) if not errors else None
        with self.db:
            cursor = self.db.execute(
                "INSERT OR IGNORE INTO events(source,epoch,sequence,received,raw,record,errors,status) VALUES(?,?,?,?,?,?,?,?)",
                (
                    source,
                    epoch,
                    sequence,
                    received,
                    raw,
                    serialized,
                    json.dumps(errors),
                    status,
                ),
            )
            if cursor.rowcount == 0:
                existing = self.db.execute(
                    "SELECT raw FROM events WHERE source=? AND epoch=? AND sequence=?",
                    (source, epoch, sequence),
                ).fetchone()
                if existing is None or existing[0] != raw:
                    raise ValueError("Event identity collision with different payload")
        return cursor.rowcount == 1, record, errors

    def append(self, table, payload):
        if table not in ("alerts", "reports"):
            raise ValueError("Invalid sink")
        with self.db:
            self.db.execute(
                f"INSERT INTO {table}(payload) VALUES(?)",
                (json.dumps(payload, allow_nan=False),),
            )

    def counts(self):
        return dict(
            self.db.execute("SELECT status,COUNT(*) FROM events GROUP BY status")
        )

    def export(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        for status, name in [
            ("clean", "clean_readings.csv"),
            ("bad", "bad_readings.csv"),
        ]:
            columns = [
                "event_id",
                "source",
                "epoch",
                "sequence",
                "received",
                *FIELDS,
                "payload_json",
                "errors",
                "raw_base64",
            ]
            with (directory / name).open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                for row in self.db.execute(
                    "SELECT id,source,epoch,sequence,received,record,errors,raw FROM events WHERE status=? ORDER BY id",
                    (status,),
                ):
                    record = json.loads(row[5]) if row[5] else {}
                    writer.writerow(
                        (
                            *row[:5],
                            *(record.get(key) for key in FIELDS),
                            *row[5:-1],
                            base64.b64encode(row[-1]).decode(),
                        )
                    )
        for table, name in [
            ("reports", "real_time_reports.csv"),
            ("alerts", "model_drift_alerts.csv"),
        ]:
            rows = [
                json.loads(row[0])
                for row in self.db.execute(f"SELECT payload FROM {table} ORDER BY id")
            ]
            keys = list(dict.fromkeys(k for row in rows for k in row)) or ["status"]
            with (directory / name).open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(rows)

    def close(self):
        self.db.close()
