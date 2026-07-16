from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


SYSTEM_IME_GROUP_GAP_SECONDS = 8


class ComposableEvent(Protocol):
    id: str
    redacted: str
    created_at: str
    source_method: str
    source_app: str
    project: str | None
    tags: list[str]
    is_private: bool


@dataclass(frozen=True)
class ComposedEvent:
    id: str
    source_event_ids: list[str]
    redacted: str
    created_at: str
    last_created_at: str
    source_method: str
    source_app: str
    project: str | None
    tags: list[str]
    is_private: bool


def compose_events(events: list[ComposableEvent]) -> list[ComposableEvent | ComposedEvent]:
    composed: list[ComposableEvent | ComposedEvent] = []
    for event in events:
        previous = composed[-1] if composed else None
        if isinstance(previous, ComposedEvent) and _can_append(previous, event):
            composed[-1] = ComposedEvent(
                id=previous.id,
                source_event_ids=[*previous.source_event_ids, event.id],
                redacted=_join_text(previous.redacted, event.redacted),
                created_at=previous.created_at,
                last_created_at=event.created_at,
                source_method=previous.source_method,
                source_app=previous.source_app,
                project=previous.project,
                tags=previous.tags,
                is_private=previous.is_private,
            )
            continue
        if event.source_method == "system_ime_commit":
            composed.append(
                ComposedEvent(
                    id=event.id,
                    source_event_ids=[event.id],
                    redacted=event.redacted,
                    created_at=event.created_at,
                    last_created_at=event.created_at,
                    source_method=event.source_method,
                    source_app=event.source_app,
                    project=event.project,
                    tags=event.tags,
                    is_private=event.is_private,
                )
            )
        else:
            composed.append(event)
    return composed


def source_event_ids(event: ComposableEvent | ComposedEvent) -> list[str]:
    if isinstance(event, ComposedEvent):
        return event.source_event_ids
    return [event.id]


def _can_append(previous: ComposedEvent, event: ComposableEvent) -> bool:
    if event.source_method != "system_ime_commit" or previous.source_app != event.source_app:
        return False
    if previous.project != event.project or previous.is_private != event.is_private:
        return False
    if re.search(r"[.!?。！？]$", previous.redacted):
        return False
    return _seconds_between(previous.last_created_at, event.created_at) <= SYSTEM_IME_GROUP_GAP_SECONDS


def _join_text(previous: str, next_text: str) -> str:
    if re.search(r"[A-Za-z0-9]$", previous) and re.match(r"[A-Za-z0-9]", next_text):
        return f"{previous} {next_text}"
    return f"{previous}{next_text}"


def _seconds_between(start: str, end: str) -> float:
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
