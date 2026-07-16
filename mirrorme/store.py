from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo

from .redaction import redact_text
from .composition import compose_events
from .summary import build_daily_summary
from .text_workbench import evaluate_text


DEFAULT_DB_PATH = Path(".mirrorme") / "mirrorme.db"
LOCAL_TZ = ZoneInfo("Asia/Shanghai")


class CapturePausedError(RuntimeError):
    """Raised when capture is paused and a write is attempted."""


@dataclass(frozen=True)
class TextEvent:
    id: str
    raw: str
    redacted: str
    created_at: str
    source_method: str
    source_app: str
    window_title: str | None
    project: str | None
    tags: list[str]
    is_private: bool


@dataclass(frozen=True)
class Memory:
    id: str
    kind: str
    content: str
    confidence: float
    source_event_ids: list[str]
    created_at: str
    updated_at: str
    status: str


@dataclass(frozen=True)
class ReviewCandidate:
    index: int
    key: str
    kind: str
    content: str
    confidence: float
    evidence_event_ids: list[str]
    review_status: str


@dataclass(frozen=True)
class DailySummaryRecord:
    id: str
    date: str
    version: int
    generator: str
    summary: dict[str, object]
    source_event_ids: list[str]
    created_at: str


@dataclass(frozen=True)
class StateAssessment:
    id: str
    date: str
    version: int
    source_event_ids: list[str]
    assessment: dict[str, object]
    created_at: str


@dataclass(frozen=True)
class CleanedDocument:
    id: str
    date: str
    version: int
    content: str
    source_event_ids: list[str]
    model: str
    prompt_hash: str
    status: str
    created_at: str


@dataclass(frozen=True)
class SearchResult:
    kind: str
    id: str
    score: int
    content: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class DoctorIssue:
    severity: str
    code: str
    table: str
    record_id: str
    message: str


class EventStore:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists text_events (
                    id text primary key,
                    raw text not null,
                    redacted text not null,
                    created_at text not null,
                    source_method text not null,
                    source_app text not null,
                    window_title text,
                    project text,
                    tags_json text not null,
                    is_private integer not null default 0
                )
                """
            )
            self._ensure_column(conn, "text_events", "window_title", "text")
            self._ensure_column(conn, "text_events", "project", "text")
            conn.execute(
                "create index if not exists idx_text_events_created_at on text_events(created_at)"
            )
            conn.execute(
                """
                create table if not exists memories (
                    id text primary key,
                    kind text not null,
                    content text not null,
                    confidence real not null,
                    source_event_ids_json text not null,
                    created_at text not null,
                    updated_at text not null,
                    status text not null default 'active'
                )
                """
            )
            conn.execute(
                """
                create table if not exists memory_reviews (
                    candidate_key text primary key,
                    status text not null,
                    memory_id text,
                    note text,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists daily_summaries (
                    id text primary key,
                    date text not null,
                    version integer not null,
                    generator text not null,
                    summary_json text not null,
                    source_event_ids_json text not null,
                    created_at text not null,
                    unique(date, version)
                )
                """
            )
            conn.execute(
                "create index if not exists idx_daily_summaries_date on daily_summaries(date)"
            )
            conn.execute(
                """
                create table if not exists state_assessments (
                    id text primary key,
                    date text not null,
                    version integer not null,
                    source_event_ids_json text not null,
                    assessment_json text not null,
                    created_at text not null,
                    unique(date, version)
                )
                """
            )
            conn.execute(
                "create index if not exists idx_state_assessments_date on state_assessments(date)"
            )
            conn.execute(
                """
                create table if not exists cleaned_documents (
                    id text primary key, date text not null, version integer not null,
                    content text not null, source_event_ids_json text not null,
                    model text not null, prompt_hash text not null, status text not null,
                    created_at text not null, unique(date, version)
                )
                """
            )
            conn.execute(
                """
                create table if not exists settings (
                    key text primary key,
                    value text not null,
                    updated_at text not null
                )
                """
            )

    def add_text(
        self,
        text: str,
        *,
        source_method: str = "manual",
        source_app: str = "cli",
        window_title: str | None = None,
        project: str | None = None,
        tags: list[str] | None = None,
        is_private: bool = False,
        force: bool = False,
        created_at: str | None = None,
    ) -> TextEvent:
        if self.is_capture_paused() and not force:
            raise CapturePausedError("Capture is paused. Resume capture or pass force=True.")

        event_created_at = normalize_created_at(created_at)
        event_id = self._new_event_id(event_created_at)
        event = TextEvent(
            id=event_id,
            raw=text,
            redacted=redact_text(text),
            created_at=event_created_at,
            source_method=source_method,
            source_app=source_app,
            window_title=window_title,
            project=project,
            tags=tags or [],
            is_private=is_private,
        )
        with self._connect() as conn:
            conn.execute(
                """
                insert into text_events (
                    id, raw, redacted, created_at, source_method, source_app,
                    window_title, project, tags_json, is_private
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.raw,
                    event.redacted,
                    event.created_at,
                    event.source_method,
                    event.source_app,
                    event.window_title,
                    event.project,
                    json.dumps(event.tags, ensure_ascii=False),
                    1 if event.is_private else 0,
                ),
            )
        return event

    def list_by_date(
        self,
        date: str | None = None,
        *,
        include_private: bool = True,
        limit: int | None = None,
    ) -> list[TextEvent]:
        date = date or datetime.now(LOCAL_TZ).date().isoformat()
        query = "select * from text_events where substr(created_at, 1, 10) = ?"
        args: list[object] = [date]
        if not include_private:
            query += " and is_private = 0"
        query += " order by created_at desc" if limit is not None else " order by created_at asc"
        if limit is not None:
            query += " limit ?"
            args.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, args).fetchall()
        if limit is not None:
            rows.reverse()
        return [self._row_to_event(row) for row in rows]

    def list_events(
        self,
        *,
        date: str | None = None,
        include_private: bool = True,
        limit: int | None = None,
    ) -> list[TextEvent]:
        if date:
            return self.list_by_date(date, include_private=include_private, limit=limit)
        query = "select * from text_events"
        args: list[object] = []
        if not include_private:
            query += " where is_private = 0"
        query += " order by created_at desc" if limit is not None else " order by created_at asc"
        if limit is not None:
            query += " limit ?"
            args.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, args).fetchall()
        if limit is not None:
            rows.reverse()
        return [self._row_to_event(row) for row in rows]

    def get_event(self, event_id: str) -> TextEvent | None:
        with self._connect() as conn:
            row = conn.execute("select * from text_events where id = ?", (event_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_event(row)

    def update_event(
        self,
        event_id: str,
        *,
        raw: str | None = None,
        source_method: str | None = None,
        source_app: str | None = None,
        window_title: str | None = None,
        project: str | None = None,
        tags: list[str] | None = None,
        is_private: bool | None = None,
    ) -> TextEvent | None:
        current = self.get_event(event_id)
        if current is None:
            return None

        updated_raw = raw if raw is not None else current.raw
        updated = TextEvent(
            id=current.id,
            raw=updated_raw,
            redacted=redact_text(updated_raw) if raw is not None else current.redacted,
            created_at=current.created_at,
            source_method=source_method if source_method is not None else current.source_method,
            source_app=source_app if source_app is not None else current.source_app,
            window_title=window_title if window_title is not None else current.window_title,
            project=project if project is not None else current.project,
            tags=tags if tags is not None else current.tags,
            is_private=is_private if is_private is not None else current.is_private,
        )
        with self._connect() as conn:
            conn.execute(
                """
                update text_events set
                    raw = ?,
                    redacted = ?,
                    source_method = ?,
                    source_app = ?,
                    window_title = ?,
                    project = ?,
                    tags_json = ?,
                    is_private = ?
                where id = ?
                """,
                (
                    updated.raw,
                    updated.redacted,
                    updated.source_method,
                    updated.source_app,
                    updated.window_title,
                    updated.project,
                    json.dumps(updated.tags, ensure_ascii=False),
                    1 if updated.is_private else 0,
                    updated.id,
                ),
            )
        return updated

    def daily_summary(self, date: str | None = None) -> dict[str, object]:
        date = date or datetime.now(LOCAL_TZ).date().isoformat()
        events = self.list_by_date(date, include_private=False)
        return build_daily_summary(date, events)

    def daily_report(self, date: str | None = None, *, include_private: bool = False) -> str:
        date = date or datetime.now(LOCAL_TZ).date().isoformat()
        events = self.list_by_date(date, include_private=include_private)
        public_summary = self.daily_summary(date)
        saved_summaries = self.list_daily_summary_records(date)
        day_event_ids = {event.id for event in events}
        memories = [
            memory
            for memory in self.list_memories(status=None)
            if day_event_ids.intersection(memory.source_event_ids)
        ]

        lines = [
            f"# MirrorMe Daily Report: {date}",
            "",
            "## Overview",
            f"- Events: {len(events)}",
            f"- Public events summarized: {public_summary['event_count']}",
            f"- Saved summaries: {len(saved_summaries)}",
            f"- Related memories: {len(memories)}",
            f"- Private events included: {include_private}",
            "",
            "## Topics",
            *self._report_list(public_summary["topics"]),
            "",
            "## Summary",
            str(public_summary["summary"]),
            "",
            "## Decisions",
            *self._report_items(public_summary["decisions"]),
            "",
            "## Commitments",
            *self._report_items(public_summary["commitments"]),
            "",
            "## Open Questions",
            *self._report_items(public_summary["open_questions"]),
            "",
            "## Memory Candidates",
            *self._report_memory_candidates(public_summary["memory_candidates"]),
            "",
            "## Related Memories",
            *self._report_memories(memories),
            "",
            "## Events",
            *self._report_events(events),
            "",
            "## Saved Summary Versions",
            *self._report_summary_records(saved_summaries),
        ]
        return "\n".join(lines).rstrip() + "\n"

    def daily_overview(self, date: str | None = None, *, include_private: bool = False) -> dict[str, object]:
        date = date or datetime.now(LOCAL_TZ).date().isoformat()
        events = self.list_by_date(date, include_private=include_private)
        public_summary = self.daily_summary(date)
        saved_summaries = self.list_daily_summary_records(date)
        pending_candidates = self.review_candidates(date)
        day_event_ids = {event.id for event in events}
        active_memories = [
            memory
            for memory in self.list_memories(status="active")
            if day_event_ids.intersection(memory.source_event_ids)
        ]
        project_counts = Counter(event.project for event in events if event.project)
        tag_counts: Counter[str] = Counter()
        for event in events:
            tag_counts.update(event.tags)

        return {
            "date": date,
            "include_private": include_private,
            "events": {
                "total": len(events),
                "public": len([event for event in events if not event.is_private]),
                "private": len([event for event in events if event.is_private]),
                "projects": dict(project_counts.most_common()),
                "tags": dict(tag_counts.most_common()),
            },
            "summary": public_summary,
            "saved_summaries": [self._summary_record_to_dict(record) for record in saved_summaries],
            "pending_memory_candidates": [
                self._review_candidate_to_dict(candidate)
                for candidate in pending_candidates
            ],
            "active_memories": [self._memory_to_dict(memory) for memory in active_memories],
            "capture_paused": self.is_capture_paused(),
            "state_assessments": [
                self._state_assessment_to_dict(record)
                for record in self.list_state_assessments(date)
            ],
        }

    def save_daily_state_assessment(
        self,
        date: str | None = None,
        *,
        include_private: bool = False,
    ) -> StateAssessment:
        date = date or datetime.now(LOCAL_TZ).date().isoformat()
        events = self.list_by_date(date, include_private=include_private)
        composed_events = compose_events(events)
        text = "\n".join(event.redacted.strip() for event in composed_events if event.redacted.strip())
        assessment = evaluate_text(text)
        assessment["input_scope"] = "包含私密事件" if include_private else "仅公开事件"
        assessment["source_event_count"] = len(events)
        version = self._next_state_assessment_version(date)
        created_at = datetime.now(LOCAL_TZ).isoformat(timespec="seconds")
        record = StateAssessment(
            id=f"state_{date.replace('-', '')}_{version:03d}",
            date=date,
            version=version,
            source_event_ids=[event.id for event in events],
            assessment=assessment,
            created_at=created_at,
        )
        with self._connect() as conn:
            conn.execute(
                """
                insert into state_assessments (
                    id, date, version, source_event_ids_json, assessment_json, created_at
                ) values (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.date,
                    record.version,
                    json.dumps(record.source_event_ids, ensure_ascii=False),
                    json.dumps(record.assessment, ensure_ascii=False),
                    record.created_at,
                ),
            )
        return record

    def save_cleaned_document(self, *, date: str, content: str, source_event_ids: list[str], model: str, prompt: str) -> CleanedDocument:
        with self._connect() as conn:
            version = int(conn.execute("select coalesce(max(version), 0) + 1 from cleaned_documents where date = ?", (date,)).fetchone()[0])
            created_at = datetime.now(LOCAL_TZ).isoformat(timespec="seconds")
            record = CleanedDocument(f"clean_{date.replace('-', '')}_{version:03d}", date, version, content, source_event_ids, model, sha256(prompt.encode("utf-8")).hexdigest(), "draft", created_at)
            conn.execute("insert into cleaned_documents (id,date,version,content,source_event_ids_json,model,prompt_hash,status,created_at) values (?,?,?,?,?,?,?,?,?)", (record.id, record.date, record.version, record.content, json.dumps(record.source_event_ids, ensure_ascii=False), record.model, record.prompt_hash, record.status, record.created_at))
        return record

    def accept_cleaned_document(self, document_id: str) -> tuple[CleanedDocument, StateAssessment] | None:
        with self._connect() as conn:
            row = conn.execute("select * from cleaned_documents where id = ?", (document_id,)).fetchone()
            if row is None:
                return None
            conn.execute("update cleaned_documents set status = 'accepted' where id = ?", (document_id,))
        document = self._row_to_cleaned_document({**dict(row), "status": "accepted"})
        assessment = evaluate_text(document.content)
        assessment["input_scope"] = "已接受清洗文本"
        assessment["source_event_count"] = len(document.source_event_ids)
        with self._connect() as conn:
            version = int(conn.execute("select coalesce(max(version), 0) + 1 from state_assessments where date = ?", (document.date,)).fetchone()[0])
            created_at = datetime.now(LOCAL_TZ).isoformat(timespec="seconds")
            state = StateAssessment(f"state_{document.date.replace('-', '')}_{version:03d}", document.date, version, document.source_event_ids, assessment, created_at)
            conn.execute("insert into state_assessments (id,date,version,source_event_ids_json,assessment_json,created_at) values (?,?,?,?,?,?)", (state.id, state.date, state.version, json.dumps(state.source_event_ids, ensure_ascii=False), json.dumps(state.assessment, ensure_ascii=False), state.created_at))
        return document, state

    def list_state_assessments(
        self,
        date: str | None = None,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        latest_per_day: bool = False,
        limit: int | None = None,
    ) -> list[StateAssessment]:
        query = "select * from state_assessments"
        args: list[object] = []
        clauses: list[str] = []
        if date:
            clauses.append("date = ?")
            args.append(date)
        if start_date:
            clauses.append("date >= ?")
            args.append(start_date)
        if end_date:
            clauses.append("date <= ?")
            args.append(end_date)
        if clauses:
            query += " where " + " and ".join(clauses)
        query += " order by date desc, version desc" if limit is not None else " order by date asc, version asc"
        if limit is not None:
            query += " limit ?"
            args.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, args).fetchall()
        records = [self._row_to_state_assessment(row) for row in rows]
        if latest_per_day:
            latest: dict[str, StateAssessment] = {}
            for record in records:
                latest[record.date] = record
            records = list(latest.values())
        if limit is not None:
            records.reverse()
        return records

    def list_cleaned_documents(self, date: str) -> list[CleanedDocument]:
        with self._connect() as conn:
            rows = conn.execute("select * from cleaned_documents where date = ? order by version desc", (date,)).fetchall()
        return [self._row_to_cleaned_document(row) for row in rows]

    def save_daily_summary(
        self,
        date: str | None = None,
        *,
        generator: str = "rule-based-v1",
    ) -> DailySummaryRecord:
        date = date or datetime.now(LOCAL_TZ).date().isoformat()
        summary = self.daily_summary(date)
        source_event_ids = list(summary["source_event_ids"])
        version = self._next_summary_version(date)
        created_at = datetime.now(LOCAL_TZ).isoformat(timespec="seconds")
        record_id = f"sum_{date.replace('-', '')}_{version:03d}"
        record = DailySummaryRecord(
            id=record_id,
            date=date,
            version=version,
            generator=generator,
            summary=summary,
            source_event_ids=source_event_ids,
            created_at=created_at,
        )
        with self._connect() as conn:
            conn.execute(
                """
                insert into daily_summaries (
                    id, date, version, generator, summary_json,
                    source_event_ids_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.date,
                    record.version,
                    record.generator,
                    json.dumps(record.summary, ensure_ascii=False),
                    json.dumps(record.source_event_ids, ensure_ascii=False),
                    record.created_at,
                ),
            )
        return record

    def get_daily_summary_record(
        self,
        date: str | None = None,
        *,
        version: int | None = None,
    ) -> DailySummaryRecord | None:
        date = date or datetime.now(LOCAL_TZ).date().isoformat()
        if version is None:
            query = "select * from daily_summaries where date = ? order by version desc limit 1"
            args: tuple[object, ...] = (date,)
        else:
            query = "select * from daily_summaries where date = ? and version = ?"
            args = (date, version)
        with self._connect() as conn:
            row = conn.execute(query, args).fetchone()
        if row is None:
            return None
        return self._row_to_daily_summary_record(row)

    def list_daily_summary_records(self, date: str | None = None) -> list[DailySummaryRecord]:
        query = "select * from daily_summaries"
        args: list[object] = []
        if date:
            query += " where date = ?"
            args.append(date)
        query += " order by date asc, version asc"
        with self._connect() as conn:
            rows = conn.execute(query, args).fetchall()
        return [self._row_to_daily_summary_record(row) for row in rows]

    def _next_state_assessment_version(self, date: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "select coalesce(max(version), 0) + 1 from state_assessments where date = ?",
                (date,),
            ).fetchone()
        return int(row[0])

    def review_candidates(
        self,
        date: str | None = None,
        *,
        include_reviewed: bool = False,
    ) -> list[ReviewCandidate]:
        summary = self.daily_summary(date)
        review_statuses = self._review_statuses()
        candidates: list[ReviewCandidate] = []
        for candidate in summary["memory_candidates"]:
            key = candidate_key(candidate)
            status = review_statuses.get(key, "pending")
            if status != "pending" and not include_reviewed:
                continue
            candidates.append(
                ReviewCandidate(
                    index=len(candidates) + 1,
                    key=key,
                    kind=str(candidate["kind"]),
                    content=str(candidate["content"]),
                    confidence=float(candidate["confidence"]),
                    evidence_event_ids=list(candidate["evidence_event_ids"]),
                    review_status=status,
                )
            )
        return candidates

    def accept_candidate(
        self,
        index: int,
        *,
        date: str | None = None,
        content: str | None = None,
    ) -> Memory:
        candidate = self._candidate_by_index(index, date=date)
        memory = self.add_memory(
            kind=candidate.kind,
            content=content or candidate.content,
            confidence=candidate.confidence,
            source_event_ids=candidate.evidence_event_ids,
        )
        self._record_review(candidate.key, "accepted", memory_id=memory.id)
        return memory

    def reject_candidate(self, index: int, *, date: str | None = None, note: str | None = None) -> ReviewCandidate:
        candidate = self._candidate_by_index(index, date=date)
        self._record_review(candidate.key, "rejected", note=note)
        return candidate

    def add_memory(
        self,
        *,
        kind: str,
        content: str,
        confidence: float,
        source_event_ids: list[str],
        status: str = "active",
    ) -> Memory:
        now = datetime.now(LOCAL_TZ).isoformat(timespec="seconds")
        memory_id = self._new_memory_id(now)
        memory = Memory(
            id=memory_id,
            kind=kind,
            content=content,
            confidence=confidence,
            source_event_ids=source_event_ids,
            created_at=now,
            updated_at=now,
            status=status,
        )
        with self._connect() as conn:
            conn.execute(
                """
                insert into memories (
                    id, kind, content, confidence, source_event_ids_json,
                    created_at, updated_at, status
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory.id,
                    memory.kind,
                    memory.content,
                    memory.confidence,
                    json.dumps(memory.source_event_ids, ensure_ascii=False),
                    memory.created_at,
                    memory.updated_at,
                    memory.status,
                ),
            )
        return memory

    def list_memories(self, *, status: str | None = "active") -> list[Memory]:
        query = "select * from memories"
        args: list[object] = []
        if status:
            query += " where status = ?"
            args.append(status)
        query += " order by created_at asc"
        with self._connect() as conn:
            rows = conn.execute(query, args).fetchall()
        return [self._row_to_memory(row) for row in rows]

    def get_memory(self, memory_id: str) -> Memory | None:
        with self._connect() as conn:
            row = conn.execute("select * from memories where id = ?", (memory_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_memory(row)

    def update_memory(
        self,
        memory_id: str,
        *,
        kind: str | None = None,
        content: str | None = None,
        confidence: float | None = None,
        source_event_ids: list[str] | None = None,
        status: str | None = None,
    ) -> Memory | None:
        current = self.get_memory(memory_id)
        if current is None:
            return None

        updated = Memory(
            id=current.id,
            kind=kind if kind is not None else current.kind,
            content=content if content is not None else current.content,
            confidence=confidence if confidence is not None else current.confidence,
            source_event_ids=source_event_ids if source_event_ids is not None else current.source_event_ids,
            created_at=current.created_at,
            updated_at=datetime.now(LOCAL_TZ).isoformat(timespec="seconds"),
            status=status if status is not None else current.status,
        )
        with self._connect() as conn:
            conn.execute(
                """
                update memories set
                    kind = ?,
                    content = ?,
                    confidence = ?,
                    source_event_ids_json = ?,
                    updated_at = ?,
                    status = ?
                where id = ?
                """,
                (
                    updated.kind,
                    updated.content,
                    updated.confidence,
                    json.dumps(updated.source_event_ids, ensure_ascii=False),
                    updated.updated_at,
                    updated.status,
                    updated.id,
                ),
            )
        return updated

    def delete_event(self, event_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute("select id from text_events where id = ?", (event_id,)).fetchone()
            if row is None:
                return 0
            conn.execute("delete from text_events where id = ?", (event_id,))
            self._archive_memories_referencing_event(conn, event_id)
            self._delete_summaries_referencing_event(conn, event_id)
            self._delete_state_assessments_referencing_event(conn, event_id)
        return 1

    def delete_events_by_date(self, date: str) -> int:
        events = self.list_by_date(date)
        deleted = 0
        with self._connect() as conn:
            for event in events:
                conn.execute("delete from text_events where id = ?", (event.id,))
                self._archive_memories_referencing_event(conn, event.id)
                deleted += 1
            conn.execute("delete from daily_summaries where date = ?", (date,))
            conn.execute("delete from state_assessments where date = ?", (date,))
        return deleted

    def delete_events_by_tag(self, tag: str) -> int:
        events = self.list_by_tag(tag)
        deleted = 0
        affected_dates = {event.created_at[:10] for event in events}
        with self._connect() as conn:
            for event in events:
                conn.execute("delete from text_events where id = ?", (event.id,))
                self._archive_memories_referencing_event(conn, event.id)
                self._delete_summaries_referencing_event(conn, event.id)
                self._delete_state_assessments_referencing_event(conn, event.id)
                deleted += 1
            for date in affected_dates:
                conn.execute("delete from daily_summaries where date = ?", (date,))
        return deleted

    def list_by_tag(self, tag: str) -> list[TextEvent]:
        with self._connect() as conn:
            rows = conn.execute("select * from text_events order by created_at asc").fetchall()
        return [event for event in (self._row_to_event(row) for row in rows) if tag in event.tags]

    def delete_daily_summary(self, date: str, *, version: int | None = None) -> int:
        with self._connect() as conn:
            if version is None:
                cursor = conn.execute("delete from daily_summaries where date = ?", (date,))
            else:
                cursor = conn.execute(
                    "delete from daily_summaries where date = ? and version = ?",
                    (date, version),
                )
        return int(cursor.rowcount)

    def archive_memory(self, memory_id: str) -> int:
        return self._set_memory_status(memory_id, "archived")

    def restore_memory(self, memory_id: str) -> int:
        return self._set_memory_status(memory_id, "active")

    def delete_memory(self, memory_id: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute("delete from memories where id = ?", (memory_id,))
            conn.execute("update memory_reviews set memory_id = null where memory_id = ?", (memory_id,))
        return int(cursor.rowcount)

    def purge_all(self) -> None:
        with self._connect() as conn:
            conn.execute("delete from memory_reviews")
            conn.execute("delete from memories")
            conn.execute("delete from daily_summaries")
            conn.execute("delete from state_assessments")
            conn.execute("delete from text_events")
            conn.execute("delete from settings")

    def pause_capture(self) -> None:
        self._set_setting("capture_paused", "true")

    def resume_capture(self) -> None:
        self._set_setting("capture_paused", "false")

    def is_capture_paused(self) -> bool:
        return self._get_setting("capture_paused", default="false") == "true"

    def export_data(
        self,
        *,
        date: str | None = None,
        include_private: bool = False,
        include_raw: bool = False,
    ) -> dict[str, object]:
        events = self.list_events(date=date, include_private=include_private)
        summaries = self.list_daily_summary_records(date)
        return {
            "schema_version": 1,
            "exported_at": datetime.now(LOCAL_TZ).isoformat(timespec="seconds"),
            "filters": {
                "date": date,
                "include_private": include_private,
                "include_raw": include_raw,
            },
            "capture_paused": self.is_capture_paused(),
            "events": [self._event_to_dict(event, include_raw=include_raw) for event in events],
            "daily_summaries": [self._summary_record_to_dict(record) for record in summaries],
            "state_assessments": [
                self._state_assessment_to_dict(record) for record in self.list_state_assessments(date)
            ],
            "memories": [self._memory_to_dict(memory) for memory in self.list_memories(status=None)],
        }

    def import_data(self, data: dict[str, object], *, replace: bool = False) -> dict[str, int]:
        if int(data.get("schema_version", 0)) != 1:
            raise ValueError("Unsupported import schema_version.")

        counts = {
            "events_inserted": 0,
            "events_updated": 0,
            "events_skipped": 0,
            "summaries_inserted": 0,
            "summaries_updated": 0,
            "summaries_skipped": 0,
            "memories_inserted": 0,
            "memories_updated": 0,
            "memories_skipped": 0,
        }
        with self._connect() as conn:
            for event in data.get("events", []):
                action = self._import_event(conn, event, replace=replace)
                counts[f"events_{action}"] += 1
            for summary in data.get("daily_summaries", []):
                action = self._import_daily_summary(conn, summary, replace=replace)
                counts[f"summaries_{action}"] += 1
            for memory in data.get("memories", []):
                action = self._import_memory(conn, memory, replace=replace)
                counts[f"memories_{action}"] += 1

        if data.get("capture_paused") is True:
            self.pause_capture()
        elif data.get("capture_paused") is False:
            self.resume_capture()
        return counts

    def search(
        self,
        query: str,
        *,
        include_private: bool = False,
        include_archived_memories: bool = False,
        limit: int = 20,
    ) -> list[SearchResult]:
        needle = query.casefold().strip()
        if not needle:
            return []

        results: list[SearchResult] = []
        for event in self.list_events(include_private=include_private):
            score = self._score_event(event, needle)
            if score > 0:
                results.append(
                    SearchResult(
                        kind="event",
                        id=event.id,
                        score=score,
                        content=event.redacted,
                        metadata={
                            "created_at": event.created_at,
                            "source_app": event.source_app,
                            "project": event.project,
                            "tags": event.tags,
                            "is_private": event.is_private,
                        },
                    )
                )

        memory_status = None if include_archived_memories else "active"
        for memory in self.list_memories(status=memory_status):
            score = self._score_memory(memory, needle)
            if score > 0:
                results.append(
                    SearchResult(
                        kind="memory",
                        id=memory.id,
                        score=score,
                        content=memory.content,
                        metadata={
                            "created_at": memory.created_at,
                            "kind": memory.kind,
                            "status": memory.status,
                            "source_event_ids": memory.source_event_ids,
                        },
                    )
                )

        results.sort(key=lambda result: (-result.score, str(result.metadata.get("created_at", "")), result.id))
        return results[:limit]

    def stats(self) -> dict[str, object]:
        events = self.list_events(include_private=True)
        memories = self.list_memories(status=None)
        summaries = self.list_daily_summary_records()
        events_by_date = Counter(event.created_at[:10] for event in events)
        events_by_project = Counter(event.project for event in events if event.project)
        events_by_tag: Counter[str] = Counter()
        for event in events:
            events_by_tag.update(event.tags)
        memories_by_status = Counter(memory.status for memory in memories)
        memories_by_kind = Counter(memory.kind for memory in memories)

        today = datetime.now(LOCAL_TZ).date().isoformat()
        return {
            "capture_paused": self.is_capture_paused(),
            "events": {
                "total": len(events),
                "public": len([event for event in events if not event.is_private]),
                "private": len([event for event in events if event.is_private]),
                "by_date": dict(sorted(events_by_date.items())),
                "by_project": dict(events_by_project.most_common()),
                "by_tag": dict(events_by_tag.most_common()),
            },
            "daily_summaries": {
                "total": len(summaries),
                "by_date": dict(Counter(record.date for record in summaries).most_common()),
            },
            "memories": {
                "total": len(memories),
                "by_status": dict(memories_by_status.most_common()),
                "by_kind": dict(memories_by_kind.most_common()),
            },
            "review": {
                "today_pending": len(self.review_candidates(today)),
            },
        }

    def timeline(
        self,
        *,
        start: str | None = None,
        end: str | None = None,
        include_empty: bool = False,
    ) -> list[dict[str, object]]:
        events = self.list_events(include_private=True)
        summaries = self.list_daily_summary_records()
        dates = {event.created_at[:10] for event in events}
        dates.update(record.date for record in summaries)
        if start:
            dates.add(start)
        if end:
            dates.add(end)
        if not dates:
            return []

        start_date = parse_date(start or min(dates))
        end_date = parse_date(end or max(dates))
        if end_date < start_date:
            raise ValueError("timeline end date must be on or after start date.")

        summaries_by_date: dict[str, list[DailySummaryRecord]] = {}
        for record in summaries:
            summaries_by_date.setdefault(record.date, []).append(record)

        rows: list[dict[str, object]] = []
        for day in _date_range(start_date, end_date):
            date_text = day.isoformat()
            day_events = [event for event in events if event.created_at[:10] == date_text]
            day_summaries = summaries_by_date.get(date_text, [])
            if not include_empty and not day_events and not day_summaries:
                continue

            project_counts = Counter(event.project for event in day_events if event.project)
            tag_counts: Counter[str] = Counter()
            for event in day_events:
                tag_counts.update(event.tags)

            rows.append(
                {
                    "date": date_text,
                    "events": len(day_events),
                    "public_events": len([event for event in day_events if not event.is_private]),
                    "private_events": len([event for event in day_events if event.is_private]),
                    "projects": dict(project_counts.most_common()),
                    "tags": dict(tag_counts.most_common()),
                    "saved_summary_versions": [record.version for record in day_summaries],
                    "latest_summary_id": day_summaries[-1].id if day_summaries else None,
                    "pending_memory_candidates": len(self.review_candidates(date_text)),
                }
            )
        return rows

    def projects(self, *, include_private: bool = False) -> list[dict[str, object]]:
        events = [event for event in self.list_events(include_private=True) if event.project]
        if not include_private:
            events = [event for event in events if not event.is_private]
        if not events:
            return []

        summaries = self.list_daily_summary_records()
        memories = self.list_memories(status="active")
        rows: list[dict[str, object]] = []
        for project in sorted({str(event.project) for event in events}):
            project_events = [event for event in events if event.project == project]
            event_ids = {event.id for event in project_events}
            dates = sorted({event.created_at[:10] for event in project_events})
            tag_counts: Counter[str] = Counter()
            for event in project_events:
                tag_counts.update(event.tags)

            related_summaries = [
                record
                for record in summaries
                if event_ids.intersection(record.source_event_ids)
            ]
            related_memories = [
                memory
                for memory in memories
                if event_ids.intersection(memory.source_event_ids)
            ]
            rows.append(
                {
                    "project": project,
                    "events": len(project_events),
                    "public_events": len([event for event in project_events if not event.is_private]),
                    "private_events": len([event for event in project_events if event.is_private]),
                    "first_event_at": min(event.created_at for event in project_events),
                    "last_event_at": max(event.created_at for event in project_events),
                    "active_days": len(dates),
                    "tags": dict(tag_counts.most_common()),
                    "saved_summaries": len(related_summaries),
                    "active_memories": len(related_memories),
                    "pending_memory_candidates": self._pending_candidates_for_event_ids(dates, event_ids),
                }
            )
        rows.sort(key=lambda row: (str(row["last_event_at"]), str(row["project"])), reverse=True)
        return rows

    def tags(self, *, include_private: bool = False) -> list[dict[str, object]]:
        events = [event for event in self.list_events(include_private=True) if event.tags]
        if not include_private:
            events = [event for event in events if not event.is_private]
        if not events:
            return []

        summaries = self.list_daily_summary_records()
        memories = self.list_memories(status="active")
        tags = sorted({tag for event in events for tag in event.tags})
        rows: list[dict[str, object]] = []
        for tag in tags:
            tag_events = [event for event in events if tag in event.tags]
            event_ids = {event.id for event in tag_events}
            dates = sorted({event.created_at[:10] for event in tag_events})
            project_counts = Counter(event.project for event in tag_events if event.project)
            related_summaries = [
                record
                for record in summaries
                if event_ids.intersection(record.source_event_ids)
            ]
            related_memories = [
                memory
                for memory in memories
                if event_ids.intersection(memory.source_event_ids)
            ]
            rows.append(
                {
                    "tag": tag,
                    "events": len(tag_events),
                    "public_events": len([event for event in tag_events if not event.is_private]),
                    "private_events": len([event for event in tag_events if event.is_private]),
                    "first_event_at": min(event.created_at for event in tag_events),
                    "last_event_at": max(event.created_at for event in tag_events),
                    "active_days": len(dates),
                    "projects": dict(project_counts.most_common()),
                    "saved_summaries": len(related_summaries),
                    "active_memories": len(related_memories),
                    "pending_memory_candidates": self._pending_candidates_for_event_ids(dates, event_ids),
                }
            )
        rows.sort(key=lambda row: (int(row["events"]), str(row["last_event_at"]), str(row["tag"])), reverse=True)
        return rows

    def doctor(self) -> dict[str, object]:
        issues: list[DoctorIssue] = []
        with self._connect() as conn:
            events = conn.execute("select * from text_events").fetchall()
            memories = conn.execute("select * from memories").fetchall()
            summaries = conn.execute("select * from daily_summaries").fetchall()
            reviews = conn.execute("select * from memory_reviews").fetchall()

        event_ids = {str(row["id"]) for row in events}
        private_event_ids = {str(row["id"]) for row in events if bool(row["is_private"])}
        memory_ids = {str(row["id"]) for row in memories}

        for row in events:
            event_id = str(row["id"])
            self._doctor_timestamp(issues, "text_events", event_id, "created_at", row["created_at"])
            self._doctor_json_list(issues, "text_events", event_id, "tags_json", row["tags_json"])
            if not str(row["raw"]).strip():
                issues.append(
                    DoctorIssue("warning", "blank_raw", "text_events", event_id, "Event raw content is blank.")
                )
            if not str(row["redacted"]).strip():
                issues.append(
                    DoctorIssue(
                        "warning",
                        "blank_redacted",
                        "text_events",
                        event_id,
                        "Event redacted content is blank.",
                    )
                )

        for row in memories:
            memory_id = str(row["id"])
            self._doctor_timestamp(issues, "memories", memory_id, "created_at", row["created_at"])
            self._doctor_timestamp(issues, "memories", memory_id, "updated_at", row["updated_at"])
            if str(row["status"]) not in {"active", "archived"}:
                issues.append(
                    DoctorIssue(
                        "error",
                        "invalid_status",
                        "memories",
                        memory_id,
                        f"Memory status is not active or archived: {row['status']}",
                    )
                )
            source_event_ids = self._doctor_json_list(
                issues,
                "memories",
                memory_id,
                "source_event_ids_json",
                row["source_event_ids_json"],
            )
            for event_id in source_event_ids:
                if event_id not in event_ids:
                    issues.append(
                        DoctorIssue(
                            "error",
                            "missing_source_event",
                            "memories",
                            memory_id,
                            f"Memory references missing event {event_id}.",
                        )
                    )
            if not str(row["content"]).strip():
                issues.append(
                    DoctorIssue("warning", "blank_content", "memories", memory_id, "Memory content is blank.")
                )

        for row in summaries:
            summary_id = str(row["id"])
            self._doctor_timestamp(issues, "daily_summaries", summary_id, "created_at", row["created_at"])
            summary_json = self._doctor_json_object(
                issues,
                "daily_summaries",
                summary_id,
                "summary_json",
                row["summary_json"],
            )
            source_event_ids = self._doctor_json_list(
                issues,
                "daily_summaries",
                summary_id,
                "source_event_ids_json",
                row["source_event_ids_json"],
            )
            if summary_json and str(summary_json.get("date", row["date"])) != str(row["date"]):
                issues.append(
                    DoctorIssue(
                        "error",
                        "summary_date_mismatch",
                        "daily_summaries",
                        summary_id,
                        "Summary JSON date does not match record date.",
                    )
                )
            for event_id in source_event_ids:
                if event_id not in event_ids:
                    issues.append(
                        DoctorIssue(
                            "error",
                            "missing_source_event",
                            "daily_summaries",
                            summary_id,
                            f"Saved summary references missing event {event_id}.",
                        )
                    )
                elif event_id in private_event_ids:
                    issues.append(
                        DoctorIssue(
                            "error",
                            "private_event_in_summary",
                            "daily_summaries",
                            summary_id,
                            f"Saved summary references private event {event_id}.",
                        )
                    )

        for row in reviews:
            candidate_key_value = str(row["candidate_key"])
            self._doctor_timestamp(issues, "memory_reviews", candidate_key_value, "created_at", row["created_at"])
            self._doctor_timestamp(issues, "memory_reviews", candidate_key_value, "updated_at", row["updated_at"])
            status = str(row["status"])
            if status not in {"pending", "accepted", "rejected"}:
                issues.append(
                    DoctorIssue(
                        "error",
                        "invalid_status",
                        "memory_reviews",
                        candidate_key_value,
                        f"Review status is not pending, accepted, or rejected: {status}",
                    )
                )
            memory_id = row["memory_id"]
            if status == "accepted" and (not memory_id or str(memory_id) not in memory_ids):
                issues.append(
                    DoctorIssue(
                        "error",
                        "missing_review_memory",
                        "memory_reviews",
                        candidate_key_value,
                        "Accepted review does not point to an existing memory.",
                    )
                )

        issue_dicts = [self._doctor_issue_to_dict(issue) for issue in issues]
        return {
            "ok": not any(issue.severity == "error" for issue in issues),
            "issue_count": len(issues),
            "error_count": len([issue for issue in issues if issue.severity == "error"]),
            "warning_count": len([issue for issue in issues if issue.severity == "warning"]),
            "counts": {
                "events": len(events),
                "memories": len(memories),
                "daily_summaries": len(summaries),
                "memory_reviews": len(reviews),
            },
            "issues": issue_dicts,
        }

    @staticmethod
    def _report_list(values: object) -> list[str]:
        items = [str(value) for value in values] if isinstance(values, list) else []
        if not items:
            return ["- None"]
        return [f"- {item}" for item in items]

    @staticmethod
    def _report_items(values: object) -> list[str]:
        if not isinstance(values, list) or not values:
            return ["- None"]
        items: list[str] = []
        for value in values:
            if isinstance(value, dict):
                items.append(f"- {value.get('content', '')}")
            else:
                items.append(f"- {value}")
        return items

    @staticmethod
    def _report_memory_candidates(values: object) -> list[str]:
        if not isinstance(values, list) or not values:
            return ["- None"]
        items: list[str] = []
        for value in values:
            if not isinstance(value, dict):
                items.append(f"- {value}")
                continue
            evidence = ",".join(str(event_id) for event_id in value.get("evidence_event_ids", []))
            items.append(
                f"- [{value.get('kind', 'unknown')} {float(value.get('confidence', 0.0)):.2f}] "
                f"{value.get('content', '')} source={evidence}"
            )
        return items

    @staticmethod
    def _report_memories(memories: list[Memory]) -> list[str]:
        if not memories:
            return ["- None"]
        return [
            f"- [{memory.status}] {memory.kind} ({memory.confidence:.2f}) "
            f"{memory.content} source={','.join(memory.source_event_ids)}"
            for memory in memories
        ]

    @staticmethod
    def _report_events(events: list[TextEvent]) -> list[str]:
        if not events:
            return ["- None"]
        items: list[str] = []
        for event in events:
            context = [event.source_app]
            if event.project:
                context.append(f"project={event.project}")
            if event.tags:
                context.append(f"tags={','.join(event.tags)}")
            if event.window_title:
                context.append(f"title={event.window_title}")
            private = " private" if event.is_private else ""
            items.append(
                f"- {event.created_at[11:19]} {event.id}{private} "
                f"[{' '.join(context)}]: {event.redacted}"
            )
        return items

    @staticmethod
    def _report_summary_records(records: list[DailySummaryRecord]) -> list[str]:
        if not records:
            return ["- None"]
        return [
            f"- v{record.version} {record.id} {record.generator} "
            f"events={len(record.source_event_ids)} created_at={record.created_at}"
            for record in records
        ]

    @staticmethod
    def _doctor_timestamp(
        issues: list[DoctorIssue],
        table: str,
        record_id: str,
        column: str,
        value: object,
    ) -> None:
        try:
            datetime.fromisoformat(str(value))
        except ValueError:
            issues.append(
                DoctorIssue(
                    "error",
                    "invalid_timestamp",
                    table,
                    record_id,
                    f"{column} is not a valid ISO timestamp: {value}",
                )
            )

    @staticmethod
    def _doctor_json_list(
        issues: list[DoctorIssue],
        table: str,
        record_id: str,
        column: str,
        value: object,
    ) -> list[str]:
        try:
            parsed = json.loads(str(value))
        except json.JSONDecodeError:
            issues.append(
                DoctorIssue(
                    "error",
                    "invalid_json",
                    table,
                    record_id,
                    f"{column} is not valid JSON.",
                )
            )
            return []
        if not isinstance(parsed, list):
            issues.append(
                DoctorIssue(
                    "error",
                    "invalid_json_type",
                    table,
                    record_id,
                    f"{column} should be a JSON list.",
                )
            )
            return []
        return [str(item) for item in parsed]

    @staticmethod
    def _doctor_json_object(
        issues: list[DoctorIssue],
        table: str,
        record_id: str,
        column: str,
        value: object,
    ) -> dict[str, object]:
        try:
            parsed = json.loads(str(value))
        except json.JSONDecodeError:
            issues.append(
                DoctorIssue(
                    "error",
                    "invalid_json",
                    table,
                    record_id,
                    f"{column} is not valid JSON.",
                )
            )
            return {}
        if not isinstance(parsed, dict):
            issues.append(
                DoctorIssue(
                    "error",
                    "invalid_json_type",
                    table,
                    record_id,
                    f"{column} should be a JSON object.",
                )
            )
            return {}
        return parsed

    @staticmethod
    def _doctor_issue_to_dict(issue: DoctorIssue) -> dict[str, str]:
        return {
            "severity": issue.severity,
            "code": issue.code,
            "table": issue.table,
            "record_id": issue.record_id,
            "message": issue.message,
        }

    def _new_event_id(self, created_at: str) -> str:
        compact = (
            created_at.replace("-", "")
            .replace(":", "")
            .replace("+", "_")
            .replace("T", "_")
        )
        with self._connect() as conn:
            count = conn.execute(
                "select count(*) from text_events where substr(created_at, 1, 19) = ?",
                (created_at[:19],),
            ).fetchone()[0]
        return f"evt_{compact}_{count + 1:03d}"

    def _new_memory_id(self, created_at: str) -> str:
        compact = (
            created_at.replace("-", "")
            .replace(":", "")
            .replace("+", "_")
            .replace("T", "_")
        )
        with self._connect() as conn:
            count = conn.execute(
                "select count(*) from memories where substr(created_at, 1, 19) = ?",
                (created_at[:19],),
            ).fetchone()[0]
        return f"mem_{compact}_{count + 1:03d}"

    def _next_summary_version(self, date: str) -> int:
        with self._connect() as conn:
            version = conn.execute(
                "select coalesce(max(version), 0) + 1 from daily_summaries where date = ?",
                (date,),
            ).fetchone()[0]
        return int(version)

    def _pending_candidates_for_event_ids(self, dates: list[str], event_ids: set[str]) -> int:
        count = 0
        for date in dates:
            for candidate in self.review_candidates(date):
                if event_ids.intersection(candidate.evidence_event_ids):
                    count += 1
        return count

    def _candidate_by_index(self, index: int, *, date: str | None) -> ReviewCandidate:
        candidates = self.review_candidates(date)
        if index < 1 or index > len(candidates):
            raise ValueError(f"No pending memory candidate at index {index}.")
        return candidates[index - 1]

    def _review_statuses(self) -> dict[str, str]:
        with self._connect() as conn:
            rows = conn.execute("select candidate_key, status from memory_reviews").fetchall()
        return {row["candidate_key"]: row["status"] for row in rows}

    def _record_review(
        self,
        candidate_key_value: str,
        status: str,
        *,
        memory_id: str | None = None,
        note: str | None = None,
    ) -> None:
        now = datetime.now(LOCAL_TZ).isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                insert into memory_reviews (
                    candidate_key, status, memory_id, note, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?)
                on conflict(candidate_key) do update set
                    status = excluded.status,
                    memory_id = excluded.memory_id,
                    note = excluded.note,
                    updated_at = excluded.updated_at
                """,
                (candidate_key_value, status, memory_id, note, now, now),
            )

    def _set_setting(self, key: str, value: str) -> None:
        now = datetime.now(LOCAL_TZ).isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                insert into settings (key, value, updated_at) values (?, ?, ?)
                on conflict(key) do update set
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )

    def _get_setting(self, key: str, *, default: str) -> str:
        with self._connect() as conn:
            row = conn.execute("select value from settings where key = ?", (key,)).fetchone()
        if row is None:
            return default
        return str(row["value"])

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
        columns = {row["name"] for row in conn.execute(f"pragma table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"alter table {table} add column {column} {column_type}")

    def _set_memory_status(self, memory_id: str, status: str) -> int:
        now = datetime.now(LOCAL_TZ).isoformat(timespec="seconds")
        with self._connect() as conn:
            cursor = conn.execute(
                "update memories set status = ?, updated_at = ? where id = ?",
                (status, now, memory_id),
            )
        return int(cursor.rowcount)

    def _archive_memories_referencing_event(self, conn: sqlite3.Connection, event_id: str) -> None:
        now = datetime.now(LOCAL_TZ).isoformat(timespec="seconds")
        rows = conn.execute("select id, source_event_ids_json from memories where status = 'active'").fetchall()
        for row in rows:
            source_event_ids = json.loads(row["source_event_ids_json"])
            if event_id in source_event_ids:
                conn.execute(
                    "update memories set status = 'archived', updated_at = ? where id = ?",
                    (now, row["id"]),
                )

    def _delete_summaries_referencing_event(self, conn: sqlite3.Connection, event_id: str) -> None:
        rows = conn.execute("select id, source_event_ids_json from daily_summaries").fetchall()
        for row in rows:
            source_event_ids = json.loads(row["source_event_ids_json"])
            if event_id in source_event_ids:
                conn.execute("delete from daily_summaries where id = ?", (row["id"],))

    def _delete_state_assessments_referencing_event(self, conn: sqlite3.Connection, event_id: str) -> None:
        rows = conn.execute("select id, source_event_ids_json from state_assessments").fetchall()
        for row in rows:
            source_event_ids = json.loads(row["source_event_ids_json"])
            if event_id in source_event_ids:
                conn.execute("delete from state_assessments where id = ?", (row["id"],))

    def _import_event(self, conn: sqlite3.Connection, event: object, *, replace: bool) -> str:
        event_data = dict(event)
        event_id = str(event_data["id"])
        exists = conn.execute("select 1 from text_events where id = ?", (event_id,)).fetchone() is not None
        if exists and not replace:
            return "skipped"

        content = dict(event_data.get("content", {}))
        redacted = str(content.get("redacted", ""))
        raw = str(content.get("raw", redacted))
        source = dict(event_data.get("source", {}))
        values = (
            event_id,
            raw,
            redacted,
            str(event_data["created_at"]),
            str(source.get("method", "import")),
            str(source.get("app", "import")),
            source.get("window_title"),
            event_data.get("project"),
            json.dumps(list(event_data.get("tags", [])), ensure_ascii=False),
            1 if bool(event_data.get("is_private", False)) else 0,
        )
        conn.execute(
            """
            insert into text_events (
                id, raw, redacted, created_at, source_method, source_app,
                window_title, project, tags_json, is_private
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(id) do update set
                raw = excluded.raw,
                redacted = excluded.redacted,
                created_at = excluded.created_at,
                source_method = excluded.source_method,
                source_app = excluded.source_app,
                window_title = excluded.window_title,
                project = excluded.project,
                tags_json = excluded.tags_json,
                is_private = excluded.is_private
            """,
            values,
        )
        return "updated" if exists else "inserted"

    def _import_daily_summary(self, conn: sqlite3.Connection, record: object, *, replace: bool) -> str:
        record_data = dict(record)
        record_id = str(record_data["id"])
        existing = conn.execute(
            "select id from daily_summaries where id = ? or (date = ? and version = ?)",
            (record_id, str(record_data["date"]), int(record_data["version"])),
        ).fetchone()
        exists = existing is not None
        if exists and not replace:
            return "skipped"

        values = (
            record_id,
            str(record_data["date"]),
            int(record_data["version"]),
            str(record_data.get("generator", "import")),
            json.dumps(record_data.get("summary", {}), ensure_ascii=False),
            json.dumps(list(record_data.get("source_event_ids", [])), ensure_ascii=False),
            str(record_data["created_at"]),
        )
        if exists:
            conn.execute("delete from daily_summaries where id = ?", (existing["id"],))
        conn.execute(
            """
            insert into daily_summaries (
                id, date, version, generator, summary_json,
                source_event_ids_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        return "updated" if exists else "inserted"

    def _import_memory(self, conn: sqlite3.Connection, memory: object, *, replace: bool) -> str:
        memory_data = dict(memory)
        memory_id = str(memory_data["id"])
        exists = conn.execute("select 1 from memories where id = ?", (memory_id,)).fetchone() is not None
        if exists and not replace:
            return "skipped"

        values = (
            memory_id,
            str(memory_data["kind"]),
            str(memory_data["content"]),
            float(memory_data["confidence"]),
            json.dumps(list(memory_data.get("source_event_ids", [])), ensure_ascii=False),
            str(memory_data["created_at"]),
            str(memory_data.get("updated_at", memory_data["created_at"])),
            str(memory_data.get("status", "active")),
        )
        conn.execute(
            """
            insert into memories (
                id, kind, content, confidence, source_event_ids_json,
                created_at, updated_at, status
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(id) do update set
                kind = excluded.kind,
                content = excluded.content,
                confidence = excluded.confidence,
                source_event_ids_json = excluded.source_event_ids_json,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at,
                status = excluded.status
            """,
            values,
        )
        return "updated" if exists else "inserted"

    @staticmethod
    def _score_event(event: TextEvent, needle: str) -> int:
        score = 0
        fields = [
            (event.redacted, 5),
            (event.project or "", 4),
            (" ".join(event.tags), 3),
            (event.source_app, 2),
            (event.window_title or "", 2),
        ]
        for value, weight in fields:
            if needle in value.casefold():
                score += weight
        return score

    @staticmethod
    def _score_memory(memory: Memory, needle: str) -> int:
        score = 0
        fields = [
            (memory.content, 6),
            (memory.kind, 3),
            (memory.status, 1),
        ]
        for value, weight in fields:
            if needle in value.casefold():
                score += weight
        return score

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> TextEvent:
        return TextEvent(
            id=row["id"],
            raw=row["raw"],
            redacted=row["redacted"],
            created_at=row["created_at"],
            source_method=row["source_method"],
            source_app=row["source_app"],
            window_title=row["window_title"],
            project=row["project"],
            tags=json.loads(row["tags_json"]),
            is_private=bool(row["is_private"]),
        )

    @staticmethod
    def _row_to_memory(row: sqlite3.Row) -> Memory:
        return Memory(
            id=row["id"],
            kind=row["kind"],
            content=row["content"],
            confidence=float(row["confidence"]),
            source_event_ids=json.loads(row["source_event_ids_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            status=row["status"],
        )

    @staticmethod
    def _row_to_daily_summary_record(row: sqlite3.Row) -> DailySummaryRecord:
        return DailySummaryRecord(
            id=row["id"],
            date=row["date"],
            version=int(row["version"]),
            generator=row["generator"],
            summary=json.loads(row["summary_json"]),
            source_event_ids=json.loads(row["source_event_ids_json"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_state_assessment(row: sqlite3.Row) -> StateAssessment:
        return StateAssessment(
            id=row["id"],
            date=row["date"],
            version=int(row["version"]),
            source_event_ids=json.loads(row["source_event_ids_json"]),
            assessment=json.loads(row["assessment_json"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_cleaned_document(row: sqlite3.Row | dict[str, object]) -> CleanedDocument:
        return CleanedDocument(
            id=str(row["id"]), date=str(row["date"]), version=int(row["version"]),
            content=str(row["content"]), source_event_ids=json.loads(str(row["source_event_ids_json"])),
            model=str(row["model"]), prompt_hash=str(row["prompt_hash"]), status=str(row["status"]), created_at=str(row["created_at"]),
        )

    @staticmethod
    def _event_to_dict(event: TextEvent, *, include_raw: bool) -> dict[str, object]:
        content: dict[str, object] = {"redacted": event.redacted}
        if include_raw:
            content["raw"] = event.raw
        return {
            "id": event.id,
            "created_at": event.created_at,
            "source": {
                "method": event.source_method,
                "app": event.source_app,
                "window_title": event.window_title,
            },
            "project": event.project,
            "tags": event.tags,
            "is_private": event.is_private,
            "content": content,
        }

    @staticmethod
    def _memory_to_dict(memory: Memory) -> dict[str, object]:
        return {
            "id": memory.id,
            "kind": memory.kind,
            "content": memory.content,
            "confidence": memory.confidence,
            "source_event_ids": memory.source_event_ids,
            "created_at": memory.created_at,
            "updated_at": memory.updated_at,
            "status": memory.status,
        }

    @staticmethod
    def _summary_record_to_dict(record: DailySummaryRecord) -> dict[str, object]:
        return {
            "id": record.id,
            "date": record.date,
            "version": record.version,
            "generator": record.generator,
            "created_at": record.created_at,
            "source_event_ids": record.source_event_ids,
            "summary": record.summary,
        }

    @staticmethod
    def _state_assessment_to_dict(record: StateAssessment) -> dict[str, object]:
        return {
            "id": record.id,
            "date": record.date,
            "version": record.version,
            "source_event_ids": record.source_event_ids,
            "assessment": record.assessment,
            "created_at": record.created_at,
        }

    @staticmethod
    def _review_candidate_to_dict(candidate: ReviewCandidate) -> dict[str, object]:
        return {
            "index": candidate.index,
            "key": candidate.key,
            "kind": candidate.kind,
            "content": candidate.content,
            "confidence": candidate.confidence,
            "evidence_event_ids": candidate.evidence_event_ids,
            "review_status": candidate.review_status,
        }


def candidate_key(candidate: dict[str, object]) -> str:
    payload = json.dumps(
        {
            "kind": candidate["kind"],
            "content": candidate["content"],
            "evidence_event_ids": candidate["evidence_event_ids"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def normalize_created_at(created_at: str | None) -> str:
    if created_at is None:
        return datetime.now(LOCAL_TZ).isoformat(timespec="seconds")
    try:
        parsed = datetime.fromisoformat(created_at)
    except ValueError as exc:
        raise ValueError("created_at must be an ISO datetime or date.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=LOCAL_TZ)
    return parsed.isoformat(timespec="seconds")


def parse_date(value: str) -> Date:
    try:
        return Date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must be in YYYY-MM-DD format.") from exc


def _date_range(start: Date, end: Date) -> list[Date]:
    days = (end - start).days
    return [start + timedelta(days=offset) for offset in range(days + 1)]
