from __future__ import annotations

import json
import os
import time
from pathlib import Path
from threading import Lock

from .store import CapturePausedError, EventStore


QUEUE_FILENAME = "mirrorme-ime-commits.ndjson"
SYSTEM_IME_TAGS = ["ime", "committed", "system"]
PROCESSING_RECOVERY_SECONDS = 60
_DRAIN_LOCK = Lock()


def default_system_ime_queue_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Rime" / QUEUE_FILENAME
    return Path.home() / ".rime" / QUEUE_FILENAME


def drain_system_ime_queue(
    store: EventStore,
    *,
    queue_path: Path | None = None,
) -> dict[str, int]:
    """Atomically consume committed Rime text written by the local Lua bridge."""
    with _DRAIN_LOCK:
        return _drain_system_ime_queue(store, queue_path=queue_path)


def _drain_system_ime_queue(
    store: EventStore,
    *,
    queue_path: Path | None = None,
) -> dict[str, int]:
    queue = queue_path or default_system_ime_queue_path()
    processing = queue.with_suffix(queue.suffix + ".processing")
    claimed = _claim_queue(queue, processing)
    if claimed is None:
        return {"captured": 0, "discarded": 0, "paused": 0}

    captured = 0
    discarded = 0
    paused = 0
    try:
        for line in claimed.read_text(encoding="utf-8").splitlines():
            commit = _committed_text(line)
            if commit is None:
                discarded += 1
                continue
            text, created_at = commit
            try:
                store.add_text(
                    text,
                    source_method="system_ime_commit",
                    source_app="MirrorMe Pinyin (Weasel)",
                    tags=SYSTEM_IME_TAGS,
                    created_at=created_at,
                )
            except CapturePausedError:
                paused += 1
            else:
                captured += 1
    finally:
        claimed.unlink(missing_ok=True)
    return {"captured": captured, "discarded": discarded, "paused": paused}


def _claim_queue(queue: Path, processing: Path) -> Path | None:
    if processing.exists():
        age_seconds = time.time() - processing.stat().st_mtime
        if age_seconds < PROCESSING_RECOVERY_SECONDS:
            return None
        return processing
    try:
        queue.replace(processing)
    except (FileNotFoundError, PermissionError):
        # Weasel may still hold the append-only queue open. Leave it untouched
        # and let a later manual request consume the complete batch.
        return None
    return processing


def _committed_text(line: str) -> tuple[str, str | None] | None:
    try:
        payload = json.loads(line.lstrip("\ufeff"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or payload.get("version") != 1:
        return None
    text = payload.get("text")
    if not isinstance(text, str):
        return None
    text = text.strip()
    if not text:
        return None
    created_at = payload.get("created_at")
    return text, created_at if isinstance(created_at, str) else None
