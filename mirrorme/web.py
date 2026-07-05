from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .ime import input_method_status
from .ime_capture import capture_ime_commit
from .ime_sidecar import SidecarError
from .ime_sidecar import commit as ime_commit
from .ime_sidecar import compose as ime_compose
from .ime_sidecar import schema_info as ime_schema_info
from .store import DEFAULT_DB_PATH, CapturePausedError, EventStore


STATIC_DIR = Path(__file__).with_name("web_static")


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
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_static("index.html")
                return
            if parsed.path in {"/app.js", "/style.css"}:
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
                events = self.store.list_events(date=date, include_private=include_private)
                self._send_json([_event_to_json(event) for event in events])
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
                self._send_json(input_method_status())
                return
            if parsed.path == "/api/ime/schema":
                self._send_json(ime_schema_info())
                return
            self._send_json({"error": "Not found."}, status=404)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                payload = self._read_json()
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
            except (CapturePausedError, KeyError, TypeError, ValueError, SidecarError, json.JSONDecodeError) as exc:
                status = 409 if isinstance(exc, CapturePausedError) else 400
                self._send_json({"error": str(exc)}, status=status)
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


def _first(params: dict[str, list[str]], key: str, default: str | None = None) -> str | None:
    values = params.get(key)
    if not values:
        return default
    return values[0]


def _truthy(value: str | None) -> bool:
    return value in {"1", "true", "yes", "on"}


def _parse_tags(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [tag.strip() for tag in value.split(",") if tag.strip()]
    if isinstance(value, list):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    return []
