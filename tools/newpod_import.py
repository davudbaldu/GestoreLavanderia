"""Stage NewPod exports in a private SQLite database; never alters source CSVs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS import_batches (
 id INTEGER PRIMARY KEY,
 archive TEXT NOT NULL CHECK(archive IN ('ospiti','divise')),
 kind TEXT NOT NULL CHECK(kind IN ('persone','tag','movimenti')),
 source_name TEXT NOT NULL,
 sha256 TEXT NOT NULL,
 encoding TEXT NOT NULL,
 imported_at TEXT NOT NULL,
 summary_json TEXT NOT NULL,
 UNIQUE(archive,kind,sha256)
);
CREATE TABLE IF NOT EXISTS source_records (
 id INTEGER PRIMARY KEY,
 batch_id INTEGER NOT NULL REFERENCES import_batches(id),
 source_row INTEGER NOT NULL,
 source_person_id TEXT,
 tag_id TEXT,
 person_name_key TEXT,
 incoming_date TEXT,
 outgoing_date TEXT,
 raw_json TEXT NOT NULL,
 UNIQUE(batch_id,source_row)
);
CREATE TABLE IF NOT EXISTS import_issues (
 id INTEGER PRIMARY KEY,
 batch_id INTEGER NOT NULL REFERENCES import_batches(id),
 source_row INTEGER NOT NULL,
 code TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS records_tag_idx ON source_records(tag_id);
CREATE INDEX IF NOT EXISTS records_person_idx ON source_records(source_person_id);
"""

def decode_csv(raw: bytes) -> tuple[str, str]:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    try:
        return raw.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("cp1252"), "windows-1252"

def clean(value: object) -> str:
    return str(value or "").strip()

def person_key(row: dict) -> str:
    return "|".join(" ".join(clean(row.get(k)).upper().split()) for k in ("Cognome", "Nome"))

def external_person_key(archive: str, source_id: str) -> str:
    return f"{archive}::{clean(source_id)}"

def date_only(value: object) -> str | None:
    text = clean(value)
    if not text:
        return None
    first = text.split()[0]
    for pattern in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(first, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError("invalid_date")

def detect_kind(headers: list[str]) -> str:
    if {"TAGID", "DataIngresso", "DataUscita"}.issubset(headers):
        return "movimenti"
    if {"Tag ID", "Struttura"}.issubset(headers):
        return "tag"
    if {"Cognome", "Nome", "Ingresso"}.issubset(headers):
        return "persone"
    raise ValueError("Intestazioni non riconosciute come report NewPod.")

def parse_report(raw: bytes) -> tuple[str, list[tuple[int, dict]], str, list[str]]:
    text, encoding = decode_csv(raw)
    try:
        dialect = csv.Sniffer().sniff(text[:16384], delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel()
        dialect.delimiter = ";"
    reader = csv.reader(io.StringIO(text, newline=""), dialect)
    try:
        headers = [h.strip().lstrip("\ufeff") for h in next(reader)]
    except StopIteration as exc:
        raise ValueError("CSV vuoto.") from exc
    if len(set(headers)) != len(headers):
        raise ValueError("Intestazioni duplicate.")
    kind, rows = detect_kind(headers), []
    for values in reader:
        line = reader.line_num
        if not any(clean(v) for v in values):
            continue
        if kind == "persone" and clean(values[0]).lower() == "lavanderia":
            continue
        if kind == "persone" and clean(values[0]).isdigit() and all(not clean(v) for v in values[2:]):
            continue
        if len(values) != len(headers):
            raise ValueError(f"Numero di colonne non valido alla riga {line}.")
        rows.append((line, dict(zip(headers, values))))
    return kind, rows, encoding, headers

def analyze(raw: bytes, archive: str) -> tuple[dict, list[tuple[int, dict]], list[tuple[int, str]], str]:
    if archive not in ("ospiti", "divise"):
        raise ValueError("Archivio non valido.")
    kind, rows, encoding, headers = parse_report(raw)
    tags, dates, seen = set(), [], set()
    identities = defaultdict(set)
    issues = []
    stats = {"archive": archive, "kind": kind, "rows": len(rows),
             "unique_tags": 0, "entries": 0, "exits": 0, "paired": 0,
             "entry_only": 0, "exit_only": 0, "min_date": None, "max_date": None}
    for line, row in rows:
        signature = tuple(row[h] for h in headers)
        if signature in seen:
            issues.append((line, "duplicate_row"))
        seen.add(signature)
        tag = clean(row.get("TAGID") or row.get("Tag ID")).upper()
        if tag:
            tags.add(tag)
        elif kind != "persone":
            issues.append((line, "tag_missing"))
        if kind == "movimenti":
            parsed = {}
            for key in ("DataIngresso", "DataUscita"):
                try:
                    parsed[key] = date_only(row.get(key))
                except ValueError:
                    issues.append((line, "invalid_date"))
                    parsed[key] = None
            incoming, outgoing = parsed["DataIngresso"], parsed["DataUscita"]
            if incoming:
                stats["entries"] += 1
                dates.append(incoming)
            if outgoing:
                stats["exits"] += 1
                dates.append(outgoing)
            if incoming and outgoing:
                stats["paired"] += 1
                if incoming > outgoing:
                    issues.append((line, "date_order"))
            elif incoming:
                stats["entry_only"] += 1
            elif outgoing:
                stats["exit_only"] += 1
            else:
                issues.append((line, "dates_missing"))
            if (bool(clean(row.get("DataIngresso"))) != (clean(row.get("Sporco")) == "1")
                    or bool(clean(row.get("DataUscita"))) != (clean(row.get("Pulito")) == "1")):
                issues.append((line, "flags"))
            sid = clean(row.get("CLIEID"))
            if sid:
                identities[external_person_key(archive, sid)].add(person_key(row))
    for names in identities.values():
        if len(names) > 1:
            issues.append((0, "identity_ambiguous"))
    stats.update(unique_tags=len(tags), technical_people=len(identities),
                 min_date=min(dates) if dates else None, max_date=max(dates) if dates else None,
                 issues=dict(Counter(code for _, code in issues)))
    return stats, rows, issues, encoding

def stage_file(source: Path, archive: str, database: Path) -> dict:
    raw = source.read_bytes()
    summary, rows, issues, encoding = analyze(raw, archive)
    fingerprint = hashlib.sha256(raw).hexdigest()
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        connection.executescript(SCHEMA)
        existing = connection.execute(
            "SELECT id FROM import_batches WHERE archive=? AND kind=? AND sha256=?",
            (archive, summary["kind"], fingerprint)).fetchone()
        if existing:
            return {"batch_id": existing[0], "already_imported": True, "summary": summary}
        with connection:
            cursor = connection.execute(
                "INSERT INTO import_batches(archive,kind,source_name,sha256,encoding,imported_at,summary_json) VALUES(?,?,?,?,?,?,?)",
                (archive, summary["kind"], source.name, fingerprint, encoding,
                 datetime.now(timezone.utc).isoformat(), json.dumps(summary, ensure_ascii=False)))
            batch_id = cursor.lastrowid
            for line, row in rows:
                sid = clean(row.get("CLIEID"))
                def safe_date(key):
                    try:
                        return date_only(row.get(key))
                    except ValueError:
                        return None
                connection.execute(
                    "INSERT INTO source_records(batch_id,source_row,source_person_id,tag_id,person_name_key,incoming_date,outgoing_date,raw_json) VALUES(?,?,?,?,?,?,?,?)",
                    (batch_id, line, external_person_key(archive, sid) if sid else None,
                     clean(row.get("TAGID") or row.get("Tag ID")).upper() or None,
                     person_key(row), safe_date("DataIngresso"), safe_date("DataUscita"),
                     json.dumps(row, ensure_ascii=False)))
            connection.executemany("INSERT INTO import_issues(batch_id,source_row,code) VALUES(?,?,?)",
                                   ((batch_id, line, code) for line, code in issues))
        return {"batch_id": batch_id, "already_imported": False, "summary": summary}
    finally:
        connection.close()

def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica e acquisizione privata dei report NewPod.")
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--archive", choices=("ospiti", "divise"), required=True)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    if not args.audit_only and args.db is None:
        parser.error("Indica --db oppure usa --audit-only.")
    repo = Path(__file__).resolve().parents[1]
    if args.db and args.db.resolve().is_relative_to(repo):
        parser.error("Il database deve essere fuori dal repository.")
    try:
        if args.audit_only:
            report = analyze(args.csv.read_bytes(), args.archive)[0]
        else:
            report = stage_file(args.csv, args.archive, args.db)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, csv.Error, sqlite3.Error) as exc:
        parser.exit(1, f"Importazione non completata: {exc}\n")

if __name__ == "__main__":
    raise SystemExit(main())
