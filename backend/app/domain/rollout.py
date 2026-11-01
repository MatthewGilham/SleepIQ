"""Explicit owner-run candidate preparation, reviewed activation and nondestructive rollback."""

import argparse
import csv
import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.backup import create_daily, restore_isolated, verify
from app.db.coordinator import write_guard
from app.db.engine import open_engine
from app.db.migrate import upgrade
from app.domain.config import DERIVE, SCORE, WEIGHTED_DERIVE, WEIGHTED_SCORE
from app.domain.rebuild import rebuild
from app.domain.versions import ActivePair, active_pair, set_active

CANDIDATE_KEY = "derivation.candidate.v1"


def _open(data: Path, backups: Path) -> Engine:
    database = data / "sleepiq.sqlite3"
    for path in (data, data / "raw", database, backups):
        if path.is_symlink() or path.is_junction():
            raise ValueError("Regular owner-provisioned paths required")
    if not database.is_file() or not backups.is_dir():
        raise ValueError("Existing data store and backup directory required")
    return open_engine(database)


def _digest(conn: Connection, candidate: bool = False) -> str:
    digest = hashlib.sha256()
    queries = ["SELECT id,fingerprint,status FROM observations ORDER BY id"]
    if candidate:
        queries = [
            "SELECT * FROM nightly_metrics WHERE derivation_version='derive-2' ORDER BY wake_date",
            "SELECT * FROM nightly_scores WHERE score_version='score-3' ORDER BY wake_date",
        ]
    for query in queries:
        for row in conn.execute(text(query)):
            digest.update(json.dumps(tuple(row), separators=(",", ":")).encode())
            digest.update(b"\n")
    return digest.hexdigest()


def _snapshot(data: Path, backups: Path) -> str:
    # A unique root prevents create_daily from reusing an older same-day snapshot.
    checkpoint = uuid4().hex[:16]
    parent = backups / "hr"
    if parent.is_symlink() or parent.is_junction():
        raise ValueError("Regular recovery checkpoint directory required")
    root = parent / checkpoint
    root.mkdir(parents=True)
    snapshot = create_daily(data / "sleepiq.sqlite3", data / "raw", root, date.today())
    restore_isolated(snapshot, root / "restore-check")
    return checkpoint


def _review_file(conn: Connection, root: Path) -> str:
    review = root / "review.csv"
    with review.open("x", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "wake_date",
                "previous_hr_bpm",
                "candidate_hr_bpm",
                "method",
                "estimated_coverage",
                "previous_score",
                "candidate_score",
                "hrv_unchanged",
            ]
        )
        writer.writerows(
            conn.execute(
                text(
                    "SELECT n.wake_date,o.hr_mean,n.hr_mean,n.hr_method,n.hr_coverage,"
                    "s.overall,c.overall,n.hrv_mean IS o.hrv_mean FROM nightly_metrics n "
                    "JOIN nightly_metrics o ON o.wake_date=n.wake_date AND o.derivation_version='derive-1' "
                    "LEFT JOIN nightly_scores s ON s.wake_date=n.wake_date AND s.score_version='score-2' "
                    "LEFT JOIN nightly_scores c ON c.wake_date=n.wake_date AND c.score_version='score-3' "
                    "WHERE n.derivation_version='derive-2' ORDER BY n.wake_date"
                )
            )
        )
    return hashlib.sha256(review.read_bytes()).hexdigest()


def prepare(data: Path, backups: Path, *, confirm_individual_hr: bool) -> dict[str, Any]:
    if not confirm_individual_hr:
        raise ValueError("Confirm individual HR export semantics before preparing history")
    engine = _open(data, backups)
    try:
        with write_guard(data):
            with engine.connect() as conn:
                before = active_pair(conn)
                if before.derive != DERIVE.version:
                    raise ValueError("Weighted HR is already active")
            checkpoint = _snapshot(data, backups)
            upgrade(engine)  # Explicit command only; never called from application startup.
            with engine.begin() as conn:
                rebuild(conn, derive=WEIGHTED_DERIVE, score=WEIGHTED_SCORE)
                counts: dict[str | None, int] = dict(
                    conn.execute(
                        text(
                            "SELECT hr_method,count(*) FROM nightly_metrics "
                            "WHERE derivation_version='derive-2' GROUP BY hr_method"
                        )
                    ).all()
                )
                nights = sum(counts.values())
                if not nights:
                    raise ValueError("No recorded nights to review")
                record = {
                    "generation": before.generation,
                    "input_digest": _digest(conn),
                    "candidate_digest": _digest(conn, True),
                    "checkpoint": checkpoint,
                    "individual_points": True,
                    "review_token": uuid4().hex,
                    "review_sha256": _review_file(conn, backups / "hr" / checkpoint),
                }
                conn.execute(
                    text(
                        "INSERT INTO app_settings VALUES(:k,:v) "
                        "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json"
                    ),
                    {"k": CANDIDATE_KEY, "v": json.dumps(record, sort_keys=True)},
                )
                return {
                    "nights": nights,
                    "weighted": counts.get("time_weighted_linear", 0),
                    "fallback": counts.get("simple_mean_fallback", 0),
                    "missing": counts.get(None, 0),
                    "checkpoint": checkpoint,
                    "review_token": record["review_token"],
                }
    finally:
        engine.dispose()


def activate(data: Path, backups: Path, review_token: str) -> ActivePair:
    engine = _open(data, backups)
    try:
        with write_guard(data), engine.begin() as conn:
            raw = conn.scalar(
                text("SELECT value_json FROM app_settings WHERE key=:k"), {"k": CANDIDATE_KEY}
            )
            record = json.loads(raw) if raw else {}
            if not review_token or record.get("review_token") != review_token:
                raise ValueError("A prepared candidate and its reviewed token are required")
            current = active_pair(conn)
            if (
                current.derive != DERIVE.version
                or record.get("generation") != current.generation
                or record.get("individual_points") is not True
                or record.get("input_digest") != _digest(conn)
                or record.get("candidate_digest") != _digest(conn, True)
            ):
                raise ValueError(
                    "Candidate or inputs changed since preparation; prepare and review again"
                )
            checkpoint = record.get("checkpoint", "")
            if (
                not isinstance(checkpoint, str)
                or len(checkpoint) != 16
                or any(c not in "0123456789abcdef" for c in checkpoint)
            ):
                raise ValueError("Invalid recovery checkpoint")
            root = backups / "hr" / checkpoint
            if (
                root.is_symlink()
                or root.is_junction()
                or root.parent.is_symlink()
                or root.parent.is_junction()
            ):
                raise ValueError("Regular recovery checkpoint directory required")
            snapshots = list(root.glob("????-??-??/manifest.json"))
            if len(snapshots) != 1:
                raise ValueError("Verified pre-change snapshot required")
            verify(snapshots[0].parent)
            review = root / "review.csv"
            if (
                review.is_symlink()
                or not review.is_file()
                or hashlib.sha256(review.read_bytes()).hexdigest() != record.get("review_sha256")
            ):
                raise ValueError("Local review file changed; prepare and review again")
            return set_active(conn, True)
    finally:
        engine.dispose()


def rollback(data: Path, backups: Path) -> ActivePair:
    engine = _open(data, backups)
    try:
        with write_guard(data):
            _snapshot(data, backups)
            with engine.begin() as conn:
                # Include imports received since activation; weighted rows/raw records survive.
                rebuild(conn, derive=DERIVE, score=SCORE)
                return set_active(conn, False)
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "activate", "rollback", "status"))
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--backups", type=Path, required=True)
    parser.add_argument("--confirm-individual-hr", action="store_true")
    parser.add_argument("--review-token", default="")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            result = prepare(
                args.data_root, args.backups, confirm_individual_hr=args.confirm_individual_hr
            )
        elif args.action in ("activate", "rollback"):
            pair = (
                activate(args.data_root, args.backups, args.review_token)
                if args.action == "activate"
                else rollback(args.data_root, args.backups)
            )
            result = {"versions": pair.versions, "generation": pair.generation}
        else:
            engine = _open(args.data_root, args.backups)
            try:
                with engine.connect() as conn:
                    pair = active_pair(conn)
                result = {"versions": pair.versions, "generation": pair.generation}
            finally:
                engine.dispose()
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, sqlite3.Error, SQLAlchemyError, TimeoutError) as error:
        print(f"Weighted HR command failed ({type(error).__name__}); no activation reported.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
