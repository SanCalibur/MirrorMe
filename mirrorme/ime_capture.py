from __future__ import annotations

from .ime_sidecar import DEFAULT_SCHEMA
from .ime_sidecar import commit as ime_commit
from .store import EventStore, TextEvent


DEFAULT_IME_TAGS = ["ime", "committed"]


def capture_ime_commit(
    store: EventStore,
    text: str,
    *,
    candidate_index: int = 1,
    schema: str = DEFAULT_SCHEMA,
    source_app: str = "MirrorMe IME",
    window_title: str | None = None,
    project: str | None = None,
    tags: list[str] | None = None,
    is_private: bool = False,
    force: bool = False,
    created_at: str | None = None,
) -> dict[str, object]:
    composition = ime_commit(text, candidate_index=candidate_index, schema=schema)
    committed = str(composition.get("committed") or "").strip()
    if not committed:
        raise ValueError("IME commit did not produce committed text.")

    event = store.add_text(
        committed,
        source_method="ime_commit",
        source_app=source_app,
        window_title=window_title,
        project=project,
        tags=_capture_tags(tags),
        is_private=is_private,
        force=force,
        created_at=created_at,
    )
    return {
        "composition": composition,
        "event": _event_payload(event),
        "analysis": _analysis_payload(store, event),
    }


def _capture_tags(tags: list[str] | None) -> list[str]:
    merged: list[str] = []
    for tag in [*DEFAULT_IME_TAGS, *(tags or [])]:
        cleaned = tag.strip()
        if cleaned and cleaned not in merged:
            merged.append(cleaned)
    return merged


def _event_payload(event: TextEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "created_at": event.created_at,
        "source_method": event.source_method,
        "source_app": event.source_app,
        "window_title": event.window_title,
        "project": event.project,
        "tags": event.tags,
        "is_private": event.is_private,
        "redacted": event.redacted,
    }


def _analysis_payload(store: EventStore, event: TextEvent) -> dict[str, object]:
    date = event.created_at[:10]
    overview = store.daily_overview(date, include_private=False)
    summary = dict(overview["summary"])
    return {
        "date": date,
        "event_count": summary["event_count"],
        "summary": summary["summary"],
        "topics": summary["topics"],
        "source_event_ids": summary["source_event_ids"],
        "pending_memory_candidates": overview["pending_memory_candidates"],
    }
