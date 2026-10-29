"""Self-contained verified daily backups. Caller must pause import/raw-file writes."""

import hashlib
import json
import os
import re
import shutil
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path, PurePosixPath
from uuid import uuid4

FORMAT = "sleepiq-backup-v1"


def _regular(path: Path) -> None:
    if path.is_symlink() or path.is_junction():
        raise ValueError("Links and junctions are not allowed in backup data")


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _readonly(path: Path, *, immutable: bool = False) -> sqlite3.Connection:
    query = "?mode=ro" + ("&immutable=1" if immutable else "")
    return sqlite3.connect(path.resolve().as_uri() + query, uri=True, timeout=5)


def _check_database(path: Path) -> None:
    with closing(_readonly(path, immutable=True)) as database:
        if database.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("Backup database failed integrity check")
        if database.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Backup database failed foreign-key check")


def _files(root: Path) -> list[Path]:
    _regular(root)
    result = []
    for path in root.rglob("*"):
        _regular(path)
        if path.is_file():
            result.append(path)
    return sorted(result)


def verify(snapshot: Path) -> dict[str, str]:
    """Validate format, exact inventory, path safety, hashes and SQLite integrity."""
    _regular(snapshot)
    _regular(snapshot / "manifest.json")
    payload = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        raise ValueError("Unsupported backup format")
    day = payload.get("day")
    if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
        raise ValueError("Invalid backup date")
    entries = payload.get("files")
    if not isinstance(entries, dict) or "database.sqlite3" not in entries:
        raise ValueError("Backup inventory missing")
    hashes: dict[str, str] = {}
    for name, digest in entries.items():
        if not isinstance(name, str) or not isinstance(digest, str):
            raise TypeError("Invalid manifest entry")
        relative = PurePosixPath(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or "\\" in name
            or ":" in name
            or relative.as_posix() != name
            or not (
                name == "database.sqlite3" or (name.startswith("raw/") and name.endswith(".json"))
            )
            or not re.fullmatch("[0-9a-f]{64}", digest)
        ):
            raise ValueError("Unsafe manifest entry")
        path = snapshot / name
        if not path.resolve().is_relative_to(snapshot.resolve()):
            raise ValueError("Manifest escapes backup")
        hashes[name] = digest
    inventory = {p.relative_to(snapshot).as_posix() for p in _files(snapshot)}
    if inventory != set(hashes) | {"manifest.json"}:
        raise ValueError("Backup inventory mismatch")
    for name, digest in hashes.items():
        if _digest(snapshot / name) != digest:
            raise ValueError("Backup checksum mismatch")
    _check_database(snapshot / "database.sqlite3")
    return hashes


def _delete_verified(snapshot: Path, backup_root: Path) -> None:
    """Delete only a verified owned snapshot directly under the designated root."""
    _regular(backup_root)
    if snapshot.resolve().parent != backup_root.resolve():
        raise ValueError("Retention target is outside backup folder")
    hashes = verify(snapshot)
    # No recursive delete: unknown files and links cause validation failure.
    for name in hashes:
        (snapshot / name).unlink()
    (snapshot / "manifest.json").unlink()
    for path in sorted(snapshot.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir():
            path.rmdir()
    snapshot.rmdir()


def create_daily(database: Path, raw: Path, backups: Path, day: date) -> Path:
    """Create at most one successful snapshot per date; preserve failures for inspection.

    Directories must already be provisioned privately. Importer must hold off writes
    until this function returns so database references and immutable raw files agree.
    """
    for path in (database, raw, backups):
        _regular(path)
    if not database.is_file() or not raw.is_dir() or not backups.is_dir():
        raise ValueError("Database and provisioned raw/backup folders required")
    if (
        backups.resolve().is_relative_to(raw.resolve())
        or raw.resolve().is_relative_to(backups.resolve())
        or database.resolve().is_relative_to(backups.resolve())
    ):
        raise ValueError("Source and backup locations must be separate")
    destination = backups / day.isoformat()
    if destination.exists():
        verify(destination)
        return destination
    stage = backups / (".pending-" + uuid4().hex)
    stage.mkdir()
    (stage / "raw").mkdir()
    with (
        closing(_readonly(database)) as source,
        closing(sqlite3.connect(stage / "database.sqlite3")) as target_database,
    ):
        source.backup(target_database)
    hashes = {"database.sqlite3": _digest(stage / "database.sqlite3")}
    originals = _files(raw)
    for original in originals:
        if original.suffix != ".json":
            raise ValueError("Raw backup source may contain only JSON exports")
        name = "raw/" + original.relative_to(raw).as_posix()
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        before = _digest(original)
        shutil.copyfile(original, target)
        if _digest(target) != before or _digest(original) != before:
            raise ValueError("Raw export changed during backup")
        hashes[name] = before
    if originals != _files(raw):
        raise ValueError("Raw inventory changed during backup")
    manifest = {"format": FORMAT, "day": day.isoformat(), "files": hashes}
    (stage / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    for path in _files(stage):
        with path.open("r+b") as stream:
            os.fsync(stream.fileno())
    verify(stage)
    stage.rename(destination)  # publish on same filesystem only after verification
    successful = []
    for path in backups.iterdir():
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.name) and path.is_dir():
            try:
                verify(path)
            except (ValueError, TypeError, OSError, sqlite3.Error):
                continue  # never delete malformed/unknown snapshots
            successful.append(path)
    for expired in sorted(successful)[:-14]:
        _delete_verified(expired, backups)
    return destination


def restore_isolated(snapshot: Path, destination: Path) -> Path:
    """Restore into a new directory; never merge into or overwrite an existing target."""
    hashes = verify(snapshot)
    _regular(destination)
    if destination.exists() or destination.resolve().is_relative_to(snapshot.resolve()):
        raise ValueError("Restore requires a new isolated destination")
    if not destination.parent.is_dir():
        raise ValueError("Restore parent directory must already exist")
    stage = destination.parent / (".restore-" + uuid4().hex)
    stage.mkdir()
    (stage / "raw").mkdir()
    for name in hashes:
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(snapshot / name, target)
    shutil.copyfile(snapshot / "manifest.json", stage / "manifest.json")
    verify(stage)
    stage.rename(destination)
    return destination
