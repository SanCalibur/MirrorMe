from __future__ import annotations

import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .ime import input_method_status
from .composition import compose_events
from .ime_bridge import drain_system_ime_queue, system_ime_queue_health
from .ime_capture import capture_ime_commit
from .ime_sidecar import SidecarError
from .ime_sidecar import commit as ime_commit
from .ime_sidecar import compose as ime_compose
from .ime_sidecar import schema_info as ime_schema_info
from .llm_cleaner import LlmCleaningError, clean_text_with_llm
from .llm_observer import LlmObservationError, observe_text_with_llm
from .llm_diary import write_diary_with_llm
from .observation_quality import apply_quality_gate, assess_observation_input
from .store import DEFAULT_DB_PATH, CapturePausedError, EventStore
from .text_workbench import process_text


STATIC_DIR = Path(__file__).parents[1] / "frontend" / "dist"


def run_server(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    handler = create_handler(db_path)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"MirrorMe web UI running at http://{host}:{port}", flush=True)
    server.serve_forever()


def create_handler(db_path: Path) -> type[BaseHTTPRequestHandler]:
    class MirrorMeHandler(BaseHTTPRequestHandler):
        store = EventStore(db_path)

        def do_GET(self) -> None:
            drain_system_ime_queue(self.store)
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/state", "/capture", "/analysis", "/diary", "/review", "/showcase", "/settings"}:
                self._send_static("index.html")
                return
            if parsed.path.startswith("/assets/"):
                self._send_static(parsed.path.lstrip("/"))
                return
            if parsed.path == "/api/daily":
                params = parse_qs(parsed.query)
                date = _first(params, "date")
                include_private = _truthy(_first(params, "include_private"))
                self._send_json(self.store.daily_overview(date, include_private=include_private))
                return
            if parsed.path == "/api/events":
                params = parse_qs(parsed.query)
                date = _first(params, "date")
                include_private = _truthy(_first(params, "include_private", "1"))
                events = self.store.list_events(
                    date=date,
                    include_private=include_private,
                    limit=_positive_int(_first(params, "limit")),
                )
                self._send_json([_event_to_json(event) for event in events])
                return
            if parsed.path == "/api/state-assessments":
                params = parse_qs(parsed.query)
                records = self.store.list_state_assessments(
                    _first(params, "date"),
                    start_date=_first(params, "start_date"),
                    end_date=_first(params, "end_date"),
                    method=_first(params, "method"),
                    latest_per_day=_truthy(_first(params, "latest_per_day")),
                    limit=_positive_int(_first(params, "limit")),
                )
                self._send_json([_state_assessment_to_json(record, feedback=self.store.get_assessment_feedback(record.id)) for record in records])
                return
            if parsed.path == "/api/diaries":
                diary = self.store.get_daily_diary(_first(parse_qs(parsed.query), "date") or datetime.now(LOCAL_TZ).date().isoformat())
                self._send_json(_daily_diary_to_json(diary) if diary else None)
                return
            if parsed.path == "/api/weekly-review":
                self._send_json(self.store.weekly_review(_first(parse_qs(parsed.query), "end_date")))
                return
            if parsed.path == "/api/actions":
                week_start = _first(parse_qs(parsed.query), "week_start")
                if not week_start:
                    self._send_json({"error": "week_start is required."}, status=400)
                    return
                self._send_json([_action_item_to_json(item) for item in self.store.list_action_items(week_start)])
                return
            if parsed.path == "/api/projects":
                params = parse_qs(parsed.query)
                include_private = _truthy(_first(params, "include_private"))
                self._send_json(self.store.projects(include_private=include_private))
                return
            if parsed.path == "/api/tags":
                params = parse_qs(parsed.query)
                include_private = _truthy(_first(params, "include_private"))
                self._send_json(self.store.tags(include_private=include_private))
                return
            if parsed.path == "/api/ime/status":
                status = input_method_status()
                status["system_capture"] = {**self.store.system_ime_capture_health(), **system_ime_queue_health()}
                self._send_json(status)
                return
            if parsed.path == "/api/ime/schema":
                self._send_json(ime_schema_info())
                return
            if parsed.path == "/api/export":
                params = parse_qs(parsed.query)
                self._send_json(
                    self.store.export_data(
                        date=_first(params, "date"),
                        include_private=_truthy(_first(params, "include_private")),
                        include_raw=_truthy(_first(params, "include_raw")),
                    )
                )
                return
            self._send_json({"error": "Not found."}, status=404)

        def do_POST(self) -> None:
            drain_system_ime_queue(self.store)
            parsed = urlparse(self.path)
            try:
                payload = self._read_json()
                if parsed.path == "/api/capture/pause":
                    self.store.pause_capture()
                    self._send_json({"capture_paused": True})
                    return
                if parsed.path == "/api/capture/resume":
                    self.store.resume_capture()
                    self._send_json({"capture_paused": False})
                    return
                if parsed.path == "/api/summary/save":
                    record = self.store.save_daily_summary(payload.get("date") or None)
                    self._send_json(_summary_record_to_json(record), status=201)
                    return
                if parsed.path == "/api/events":
                    event = self.store.add_text(
                        str(payload.get("text", "")),
                        source_method=str(payload.get("method", "web")),
                        source_app=str(payload.get("app", "MirrorMe Web")),
                        window_title=payload.get("window_title") or None,
                        project=payload.get("project") or None,
                        tags=_parse_tags(payload.get("tags")),
                        is_private=bool(payload.get("is_private", False)),
                        force=bool(payload.get("force", False)),
                        created_at=payload.get("created_at") or None,
                    )
                    self._send_json(_event_to_json(event), status=201)
                    return
                if parsed.path == "/api/text-workbench/process":
                    self._send_json(
                        process_text(
                            str(payload.get("text", "")),
                            replacements=str(payload.get("replacements", "")),
                            deduplicate=bool(payload.get("deduplicate", True)),
                        )
                    )
                    return
                if parsed.path == "/api/text-workbench/llm-clean":
                    cleaned = clean_text_with_llm(
                        text=str(payload.get("text", "")),
                        api_url=str(payload.get("api_url", "")),
                        api_key=str(payload.get("api_key", "")),
                        model=str(payload.get("model", "")),
                        prompt=str(payload.get("prompt", "")),
                    )
                    self._send_json({"output": cleaned})
                    return
                if parsed.path == "/api/daily/llm-clean":
                    date = str(payload.get("date", "")) or None
                    events = self.store.list_by_date(date, include_private=False)
                    composed_events = compose_events(events)
                    source_text = "\n".join(f"[{event.created_at[11:19]}] {event.redacted}" for event in composed_events if event.redacted.strip())
                    cleaned = clean_text_with_llm(text=source_text, api_url=str(payload.get("api_url", "")), api_key=str(payload.get("api_key", "")), model=str(payload.get("model", "")), prompt=str(payload.get("prompt", "")))
                    document = self.store.save_cleaned_document(date=date or datetime.now().date().isoformat(), content=cleaned, source_event_ids=[event.id for event in events], model=str(payload.get("model", "")), prompt=str(payload.get("prompt", "")))
                    self._send_json({"document": _cleaned_document_to_json(document), "source_event_count": len(events), "composed_event_count": len(composed_events), "output": cleaned})
                    return
                if parsed.path == "/api/diaries/generate":
                    date = str(payload.get("date", "")) or datetime.now(LOCAL_TZ).date().isoformat()
                    document = self.store.latest_accepted_cleaned_document(date)
                    if document is None:
                        self._send_json({"error": "请先接受当天的清洗文本，再生成日记。"}, status=422)
                        return
                    content = write_diary_with_llm(text=document.content, api_url=str(payload.get("api_url", "")), api_key=str(payload.get("api_key", "")), model=str(payload.get("model", "")), prompt=str(payload.get("prompt", "")))
                    diary = self.store.save_daily_diary(date=date, content=content, cleaned_document_id=document.id, model=str(payload.get("model", "")), prompt=str(payload.get("prompt", "")), source="llm")
                    self._send_json(_daily_diary_to_json(diary), status=201)
                    return
                if parsed.path == "/api/diaries":
                    diary = self.store.save_daily_diary(date=str(payload.get("date", "")) or datetime.now(LOCAL_TZ).date().isoformat(), content=str(payload.get("content", "")), source="manual")
                    self._send_json(_daily_diary_to_json(diary))
                    return
                if parsed.path == "/api/actions":
                    action = self.store.create_action_item(
                        week_start=str(payload.get("week_start", "")),
                        title=str(payload.get("title", "")),
                        source=str(payload.get("source", "manual")),
                    )
                    self._send_json(_action_item_to_json(action), status=201)
                    return
                if parsed.path.startswith("/api/actions/") and parsed.path.endswith("/toggle"):
                    action_id = parsed.path.removeprefix("/api/actions/").removesuffix("/toggle").rstrip("/")
                    action = self.store.toggle_action_item(action_id, bool(payload.get("completed", False)))
                    if action is None:
                        self._send_json({"error": "Action not found."}, status=404)
                        return
                    self._send_json(_action_item_to_json(action))
                    return
                if parsed.path.startswith("/api/cleaned-documents/") and parsed.path.endswith("/accept"):
                    document_id = parsed.path.removeprefix("/api/cleaned-documents/").removesuffix("/accept").rstrip("/")
                    accepted = self.store.accept_cleaned_document(document_id)
                    if accepted is None:
                        self._send_json({"error": "Cleaned document not found."}, status=404)
                        return
                    self._send_json({"document": _cleaned_document_to_json(accepted)})
                    return
                if parsed.path.startswith("/api/state-assessments/") and parsed.path.endswith("/feedback"):
                    assessment_id = parsed.path.removeprefix("/api/state-assessments/").removesuffix("/feedback").rstrip("/")
                    feedback = self.store.save_assessment_feedback(assessment_id, str(payload.get("verdict", "")), note=str(payload.get("note", "")))
                    self._send_json({"assessment_id": assessment_id, "feedback": feedback})
                    return
                if parsed.path == "/api/state-assessments/llm":
                    document = self.store.get_cleaned_document(str(payload.get("document_id", "")))
                    if document is None:
                        self._send_json({"error": "Cleaned document not found."}, status=404)
                        return
                    quality = assess_observation_input(document.content, len(document.source_event_ids))
                    if not quality["can_observe"]:
                        self._send_json({"error": "样本不足，暂不生成 LLM 观察。", "quality": quality}, status=422)
                        return
                    observation = observe_text_with_llm(
                        text=document.content,
                        api_url=str(payload.get("api_url", "")),
                        api_key=str(payload.get("api_key", "")),
                        model=str(payload.get("model", "")),
                        prompt=str(payload.get("prompt", "")),
                    )
                    observation = apply_quality_gate(observation, quality)
                    record = self.store.save_llm_state_assessment(document, observation)
                    self._send_json(_state_assessment_to_json(record), status=201)
                    return
                if parsed.path == "/api/state-assessments/llm/batch":
                    existing_dates = {record.date for record in self.store.list_state_assessments(method="llm")}
                    processed: list[dict[str, object]] = []
                    skipped: list[str] = []
                    failed: list[dict[str, str]] = []
                    for date in self.store.event_dates(include_private=False):
                        if date in existing_dates:
                            skipped.append(date)
                            continue
                        try:
                            events = self.store.list_by_date(date, include_private=False)
                            composed_events = compose_events(events)
                            source_text = "\n".join(f"[{event.created_at[11:19]}] {event.redacted}" for event in composed_events if event.redacted.strip())
                            if not source_text:
                                skipped.append(date)
                                continue
                            cleaned = clean_text_with_llm(text=source_text, api_url=str(payload.get("api_url", "")), api_key=str(payload.get("api_key", "")), model=str(payload.get("model", "")), prompt=str(payload.get("cleaning_prompt", "")))
                            document = self.store.save_cleaned_document(date=date, content=cleaned, source_event_ids=[event.id for event in events], model=str(payload.get("model", "")), prompt=str(payload.get("cleaning_prompt", "")))
                            accepted = self.store.accept_cleaned_document(document.id)
                            if accepted is None:
                                raise ValueError("无法接受刚生成的清洗文本。")
                            quality = assess_observation_input(accepted.content, len(accepted.source_event_ids))
                            if not quality["can_observe"]:
                                skipped.append(date)
                                continue
                            observation = observe_text_with_llm(text=accepted.content, api_url=str(payload.get("api_url", "")), api_key=str(payload.get("api_key", "")), model=str(payload.get("model", "")), prompt=str(payload.get("prompt", "")))
                            observation = apply_quality_gate(observation, quality)
                            record = self.store.save_llm_state_assessment(accepted, observation)
                            processed.append({"date": date, "document_id": document.id, "assessment_id": record.id})
                        except (ValueError, LlmCleaningError, LlmObservationError) as exc:
                            failed.append({"date": date, "error": str(exc)})
                    self._send_json({"processed": processed, "skipped": skipped, "failed": failed})
                    return
                if parsed.path == "/api/state-assessments/daily":
                    record = self.store.save_daily_state_assessment(
                        payload.get("date") or None,
                        include_private=bool(payload.get("include_private", False)),
                    )
                    self._send_json(_state_assessment_to_json(record), status=201)
                    return
                if parsed.path == "/api/review/accept":
                    memory = self.store.accept_candidate(
                        int(payload["index"]),
                        date=payload.get("date") or None,
                        content=payload.get("content") or None,
                    )
                    self._send_json(
                        {
                            "id": memory.id,
                            "kind": memory.kind,
                            "content": memory.content,
                            "source_event_ids": memory.source_event_ids,
                        }
                    )
                    return
                if parsed.path == "/api/review/reject":
                    candidate = self.store.reject_candidate(
                        int(payload["index"]),
                        date=payload.get("date") or None,
                        note=payload.get("note") or None,
                    )
                    self._send_json({"rejected": candidate.key, "content": candidate.content})
                    return
                if parsed.path == "/api/ime/compose":
                    self._send_json(ime_compose(str(payload.get("text", ""))))
                    return
                if parsed.path == "/api/ime/commit":
                    self._send_json(
                        ime_commit(
                            str(payload.get("text", "")),
                            candidate_index=int(payload.get("candidate_index", 1)),
                        )
                    )
                    return
                if parsed.path == "/api/ime/capture":
                    self._send_json(
                        capture_ime_commit(
                            self.store,
                            str(payload.get("text", "")),
                            candidate_index=int(payload.get("candidate_index", 1)),
                            source_app=str(payload.get("app", "MirrorMe IME")),
                            window_title=payload.get("window_title") or None,
                            project=payload.get("project") or None,
                            tags=_parse_tags(payload.get("tags")),
                            is_private=bool(payload.get("is_private", False)),
                            force=bool(payload.get("force", False)),
                            created_at=payload.get("created_at") or None,
                        ),
                        status=201,
                    )
                    return
            except (CapturePausedError, KeyError, TypeError, ValueError, SidecarError, LlmCleaningError, LlmObservationError, json.JSONDecodeError) as exc:
                status = 409 if isinstance(exc, CapturePausedError) else 400
                self._send_json({"error": str(exc)}, status=status)
                return
            self._send_json({"error": "Not found."}, status=404)

        def do_DELETE(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/events/"):
                event_id = parsed.path.removeprefix("/api/events/").strip()
                if not event_id:
                    self._send_json({"error": "Missing event id."}, status=400)
                    return
                deleted = self.store.delete_event(event_id)
                self._send_json({"deleted_events": deleted}, status=200 if deleted else 404)
                return
            self._send_json({"error": "Not found."}, status=404)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _read_json(self) -> dict[str, object]:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def _send_json(self, payload: object, *, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_static(self, filename: str) -> None:
            path = STATIC_DIR / filename
            if not path.is_file():
                self._send_json({"error": "Not found."}, status=404)
                return
            content_type = {
                ".html": "text/html; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
            }.get(path.suffix, "application/octet-stream")
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return MirrorMeHandler


def _event_to_json(event: object) -> dict[str, object]:
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


def _summary_record_to_json(record: object) -> dict[str, object]:
    return {
        "id": record.id,
        "date": record.date,
        "version": record.version,
        "generator": record.generator,
        "created_at": record.created_at,
        "source_event_ids": record.source_event_ids,
        "summary": record.summary,
    }


def _state_assessment_to_json(record: object, *, feedback: dict[str, str | None] | None = None) -> dict[str, object]:
    result = {
        "id": record.id,
        "date": record.date,
        "version": record.version,
        "source_event_ids": record.source_event_ids,
        "assessment": record.assessment,
        "created_at": record.created_at,
    }
    if feedback is not None:
        result["feedback"] = feedback
    return result


def _cleaned_document_to_json(record: object) -> dict[str, object]:
    return {"id": record.id, "date": record.date, "version": record.version, "content": record.content, "source_event_ids": record.source_event_ids, "model": record.model, "prompt_hash": record.prompt_hash, "status": record.status, "created_at": record.created_at}


def _daily_diary_to_json(record: object) -> dict[str, object]:
    return {"date": record.date, "content": record.content, "cleaned_document_id": record.cleaned_document_id, "model": record.model, "prompt_hash": record.prompt_hash, "source": record.source, "created_at": record.created_at, "updated_at": record.updated_at}


def _action_item_to_json(record: object) -> dict[str, object]:
    return {"id": record.id, "week_start": record.week_start, "title": record.title, "source": record.source, "completed_at": record.completed_at, "created_at": record.created_at, "updated_at": record.updated_at}


def _first(params: dict[str, list[str]], key: str, default: str | None = None) -> str | None:
    values = params.get(key)
    if not values:
        return default
    return values[0]


def _truthy(value: str | None) -> bool:
    return value in {"1", "true", "yes", "on"}


def _positive_int(value: str | None) -> int | None:
    if value is None:
        return None
    parsed = int(value)
    if parsed < 1:
        raise ValueError("limit must be a positive integer.")
    return parsed


def _parse_tags(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [tag.strip() for tag in value.split(",") if tag.strip()]
    if isinstance(value, list):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    return []
