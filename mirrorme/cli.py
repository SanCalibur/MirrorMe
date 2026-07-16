from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from .ime_bridge import drain_system_ime_queue
from .redaction import redact_text
from .store import DEFAULT_DB_PATH, LOCAL_TZ, CapturePausedError, EventStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MirrorMe local text capture")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite database path")

    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="capture one text output event")
    add_parser.add_argument("text", help="text to capture")
    add_parser.add_argument("--tag", action="append", default=[], help="tag for this event")
    add_parser.add_argument("--private", action="store_true", help="exclude this event from summaries")
    add_parser.add_argument("--force", action="store_true", help="capture even when capture is paused")
    add_parser.add_argument("--method", default="manual", help="capture method")
    add_parser.add_argument("--app", default="cli", help="source application")
    add_parser.add_argument("--window-title", help="source window or document title")
    add_parser.add_argument("--project", help="project or workspace label")
    add_parser.add_argument("--created-at", help="ISO datetime or date for historical backfill")

    ingest_parser = subparsers.add_parser("ingest", help="capture text from a file or stdin")
    ingest_parser.add_argument("path", nargs="?", type=Path, help="UTF-8 text file to capture")
    ingest_parser.add_argument("--stdin", action="store_true", help="read text from standard input")
    ingest_parser.add_argument("--split-paragraphs", action="store_true", help="capture each blank-line-separated paragraph")
    ingest_parser.add_argument("--tag", action="append", default=[], help="tag for captured events")
    ingest_parser.add_argument("--private", action="store_true", help="exclude captured events from summaries")
    ingest_parser.add_argument("--force", action="store_true", help="capture even when capture is paused")
    ingest_parser.add_argument("--method", help="capture method; defaults to file or stdin")
    ingest_parser.add_argument("--app", default="cli", help="source application")
    ingest_parser.add_argument("--window-title", help="source window or document title")
    ingest_parser.add_argument("--project", help="project or workspace label")
    ingest_parser.add_argument("--created-at", help="ISO datetime or date for historical backfill")

    list_parser = subparsers.add_parser("list", help="list captured entries by date")
    list_parser.add_argument("--date", help="date in YYYY-MM-DD format")
    list_parser.add_argument("--raw", action="store_true", help="show raw content instead of redacted content")

    summary_parser = subparsers.add_parser("summary", help="generate or read a structured daily summary")
    summary_parser.add_argument("--date", help="date in YYYY-MM-DD format")
    summary_parser.add_argument("--save", action="store_true", help="save a newly generated summary version")
    summary_parser.add_argument("--stored", action="store_true", help="read the latest saved summary version")
    summary_parser.add_argument("--version", type=int, help="read a specific saved summary version")

    report_parser = subparsers.add_parser("report", help="generate a human-readable daily Markdown report")
    report_parser.add_argument("--date", help="date in YYYY-MM-DD format")
    report_parser.add_argument("--include-private", action="store_true", help="include private events")
    report_parser.add_argument("--output", type=Path, help="write Markdown report to this path")

    daily_parser = subparsers.add_parser("daily", aliases=["today"], help="show a daily review dashboard")
    daily_parser.add_argument("--date", help="date in YYYY-MM-DD format")
    daily_parser.add_argument("--include-private", action="store_true", help="include private events")
    daily_parser.add_argument("--json", action="store_true", help="print structured JSON")

    summaries_parser = subparsers.add_parser("summaries", help="list saved daily summary records")
    summaries_parser.add_argument("--date", help="date in YYYY-MM-DD format")

    review_parser = subparsers.add_parser("review", help="list pending memory candidates")
    review_parser.add_argument("--date", help="date in YYYY-MM-DD format")
    review_parser.add_argument("--all", action="store_true", help="include accepted and rejected candidates")

    accept_parser = subparsers.add_parser("accept", help="accept a memory candidate by review index")
    accept_parser.add_argument("index", type=int, help="candidate index from the review command")
    accept_parser.add_argument("--date", help="date in YYYY-MM-DD format")
    accept_parser.add_argument("--content", help="edited memory content")

    reject_parser = subparsers.add_parser("reject", help="reject a memory candidate by review index")
    reject_parser.add_argument("index", type=int, help="candidate index from the review command")
    reject_parser.add_argument("--date", help="date in YYYY-MM-DD format")
    reject_parser.add_argument("--note", help="optional rejection note")

    memories_parser = subparsers.add_parser("memories", help="list accepted long-term memories")
    memories_parser.add_argument("--status", default="active", help="memory status, or 'all'")

    event_parser = subparsers.add_parser("event", help="manage one captured event")
    event_subparsers = event_parser.add_subparsers(dest="event_command", required=True)

    event_show_parser = event_subparsers.add_parser("show", help="show one event")
    event_show_parser.add_argument("event_id")

    event_update_parser = event_subparsers.add_parser("update", help="update one event")
    event_update_parser.add_argument("event_id")
    event_update_parser.add_argument("--raw")
    event_update_parser.add_argument("--method")
    event_update_parser.add_argument("--app")
    event_update_parser.add_argument("--window-title")
    event_update_parser.add_argument("--project")
    event_update_parser.add_argument("--tag", action="append", dest="tags")
    privacy_group = event_update_parser.add_mutually_exclusive_group()
    privacy_group.add_argument("--private", action="store_true")
    privacy_group.add_argument("--public", action="store_true")

    event_delete_parser = event_subparsers.add_parser("delete", help="delete one event")
    event_delete_parser.add_argument("event_id")

    memory_parser = subparsers.add_parser("memory", help="manage one long-term memory")
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command", required=True)

    memory_show_parser = memory_subparsers.add_parser("show", help="show one memory")
    memory_show_parser.add_argument("memory_id")

    memory_update_parser = memory_subparsers.add_parser("update", help="update one memory")
    memory_update_parser.add_argument("memory_id")
    memory_update_parser.add_argument("--kind")
    memory_update_parser.add_argument("--content")
    memory_update_parser.add_argument("--confidence", type=float)
    memory_update_parser.add_argument("--status")
    memory_update_parser.add_argument("--source-event-id", action="append", dest="source_event_ids")

    memory_subparsers.add_parser("archive", help="archive one memory").add_argument("memory_id")
    memory_subparsers.add_parser("restore", help="restore one archived memory").add_argument("memory_id")
    memory_subparsers.add_parser("delete", help="delete one memory").add_argument("memory_id")

    delete_parser = subparsers.add_parser("delete", help="delete or archive local data")
    delete_subparsers = delete_parser.add_subparsers(dest="delete_command", required=True)

    delete_event_parser = delete_subparsers.add_parser("event", help="delete one captured event")
    delete_event_parser.add_argument("event_id")

    delete_date_parser = delete_subparsers.add_parser("date", help="delete all events and saved summaries for a date")
    delete_date_parser.add_argument("date", help="date in YYYY-MM-DD format")

    delete_tag_parser = delete_subparsers.add_parser("tag", help="delete all events with a tag")
    delete_tag_parser.add_argument("tag")

    delete_summary_parser = delete_subparsers.add_parser("summary", help="delete saved daily summary records")
    delete_summary_parser.add_argument("date", help="date in YYYY-MM-DD format")
    delete_summary_parser.add_argument("--version", type=int, help="delete only one summary version")

    delete_memory_parser = delete_subparsers.add_parser("memory", help="delete one memory record")
    delete_memory_parser.add_argument("memory_id")

    archive_memory_parser = delete_subparsers.add_parser("archive-memory", help="archive one memory record")
    archive_memory_parser.add_argument("memory_id")

    purge_parser = delete_subparsers.add_parser("purge", help="delete all local MirrorMe records")
    purge_parser.add_argument("--yes", action="store_true", help="confirm full local data deletion")

    subparsers.add_parser("pause", help="pause text capture")
    subparsers.add_parser("resume", help="resume text capture")
    subparsers.add_parser("status", help="show capture status")
    subparsers.add_parser("stats", help="show local data statistics")
    subparsers.add_parser("doctor", help="check local data health")

    timeline_parser = subparsers.add_parser("timeline", help="show daily capture activity over a date range")
    timeline_parser.add_argument("--start", help="start date in YYYY-MM-DD format")
    timeline_parser.add_argument("--end", help="end date in YYYY-MM-DD format")
    timeline_parser.add_argument("--include-empty", action="store_true", help="include dates with no activity")
    timeline_parser.add_argument("--json", action="store_true", help="print structured JSON")

    projects_parser = subparsers.add_parser("projects", help="summarize captured output by project")
    projects_parser.add_argument("--include-private", action="store_true", help="include private events")
    projects_parser.add_argument("--json", action="store_true", help="print structured JSON")

    tags_parser = subparsers.add_parser("tags", help="summarize captured output by tag")
    tags_parser.add_argument("--include-private", action="store_true", help="include private events")
    tags_parser.add_argument("--json", action="store_true", help="print structured JSON")

    export_parser = subparsers.add_parser("export", help="export local data as JSON")
    export_parser.add_argument("--date", help="date in YYYY-MM-DD format")
    export_parser.add_argument("--include-private", action="store_true", help="include private events")
    export_parser.add_argument("--include-raw", action="store_true", help="include raw event content")
    export_parser.add_argument("--output", type=Path, help="write JSON export to this path")

    backup_parser = subparsers.add_parser("backup", help="write a timestamped local JSON backup")
    backup_parser.add_argument("--date", help="date in YYYY-MM-DD format")
    backup_parser.add_argument("--dir", type=Path, default=Path(".mirrorme") / "backups", help="backup directory")
    backup_parser.add_argument("--output", type=Path, help="write backup to this exact path")
    backup_parser.add_argument("--redacted-only", action="store_true", help="exclude private events and raw content")

    import_parser = subparsers.add_parser("import", help="import a MirrorMe JSON export")
    import_parser.add_argument("path", type=Path, help="JSON export path")
    import_parser.add_argument("--replace", action="store_true", help="replace existing records with matching ids")

    search_parser = subparsers.add_parser("search", help="search local events and memories")
    search_parser.add_argument("query")
    search_parser.add_argument("--include-private", action="store_true", help="include private events")
    search_parser.add_argument("--all-memories", action="store_true", help="include archived memories")
    search_parser.add_argument("--limit", type=int, default=20)

    redact_parser = subparsers.add_parser("redact", help="preview sensitive-data redaction")
    redact_parser.add_argument("text", help="text to redact")

    serve_parser = subparsers.add_parser("serve", help="run the local MirrorMe web UI")
    serve_parser.add_argument("--host", default="127.0.0.1", help="host to bind")
    serve_parser.add_argument("--port", type=int, default=8765, help="port to bind")

    ime_parser = subparsers.add_parser("ime", help="inspect Chinese input method integration")
    ime_subparsers = ime_parser.add_subparsers(dest="ime_command", required=True)
    ime_subparsers.add_parser("status", help="show selected input method engine and capture policy")
    ime_subparsers.add_parser("engines", help="list reviewed input method engine candidates")
    ime_subparsers.add_parser("probe", help="probe local librime native adapter configuration")
    ime_subparsers.add_parser("compliance", help="check input method commercial bundling readiness")
    ime_compose_parser = ime_subparsers.add_parser("compose", help="compose input through the sidecar protocol stub")
    ime_compose_parser.add_argument("text", help="phonetic input to compose")
    ime_commit_parser = ime_subparsers.add_parser("commit", help="commit a sidecar candidate")
    ime_commit_parser.add_argument("text", help="phonetic input to commit")
    ime_commit_parser.add_argument("--candidate", type=int, default=1, help="1-based candidate index")
    ime_verify_parser = ime_subparsers.add_parser("verify", help="smoke-test the configured sidecar")
    ime_verify_parser.add_argument("text", nargs="?", default="ni hao", help="phonetic input to verify")
    ime_verify_parser.add_argument("--candidate", type=int, default=1, help="1-based candidate index")
    ime_verify_parser.add_argument(
        "--require-native",
        action="store_true",
        help="fail unless the configured sidecar confirms it is backed by librime",
    )
    ime_capture_parser = ime_subparsers.add_parser("capture", help="commit a candidate and capture it for analysis")
    ime_capture_parser.add_argument("text", help="phonetic input to commit and capture")
    ime_capture_parser.add_argument("--candidate", type=int, default=1, help="1-based candidate index")
    ime_capture_parser.add_argument("--tag", action="append", default=[], help="tag for the captured event")
    ime_capture_parser.add_argument("--private", action="store_true", help="exclude the captured event from summaries")
    ime_capture_parser.add_argument("--force", action="store_true", help="capture even when capture is paused")
    ime_capture_parser.add_argument("--app", default="MirrorMe IME", help="source application")
    ime_capture_parser.add_argument("--window-title", help="source window or document title")
    ime_capture_parser.add_argument("--project", help="project or workspace label")
    ime_capture_parser.add_argument("--created-at", help="ISO datetime or date for historical backfill")
    ime_subparsers.add_parser("drain", help="store committed text from the local system IME queue")
    ime_subparsers.add_parser("schema", help="show sidecar schema metadata")
    ime_subparsers.add_parser("sidecar", help="run the built-in JSON-stdio IME sidecar")

    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = build_parser().parse_args(argv)

    if args.command == "redact":
        print(redact_text(args.text))
        return 0

    if args.command == "ime":
        from .ime import input_method_status
        from .ime_capture import capture_ime_commit
        from .ime_compliance import compliance_report
        from .ime_sidecar import SidecarError, commit, compose, schema_info, verify_sidecar

        status = input_method_status()
        if args.ime_command == "sidecar":
            return _ime_sidecar_stdio()
        if args.ime_command == "status":
            print(json.dumps(status, ensure_ascii=False, indent=2))
            return 0
        if args.ime_command == "engines":
            print(json.dumps(status["engines"], ensure_ascii=False, indent=2))
            return 0
        if args.ime_command == "probe":
            print(json.dumps(status["native_adapter"], ensure_ascii=False, indent=2))
            return 0
        if args.ime_command == "compliance":
            print(json.dumps(compliance_report(), ensure_ascii=False, indent=2))
            return 0
        if args.ime_command == "compose":
            try:
                composition = compose(args.text)
            except SidecarError as exc:
                print(json.dumps({"error": str(exc)}, ensure_ascii=False))
                return 1
            print(json.dumps(composition, ensure_ascii=False, indent=2))
            return 0
        if args.ime_command == "commit":
            try:
                committed = commit(args.text, candidate_index=args.candidate)
            except (SidecarError, ValueError) as exc:
                print(json.dumps({"error": str(exc)}, ensure_ascii=False))
                return 1
            print(json.dumps(committed, ensure_ascii=False, indent=2))
            return 0
        if args.ime_command == "verify":
            try:
                report = verify_sidecar(
                    args.text,
                    candidate_index=args.candidate,
                    require_native=args.require_native,
                )
            except (SidecarError, ValueError) as exc:
                print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
                return 1
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        if args.ime_command == "capture":
            try:
                payload = capture_ime_commit(
                    EventStore(args.db),
                    args.text,
                    candidate_index=args.candidate,
                    source_app=args.app,
                    window_title=args.window_title,
                    project=args.project,
                    tags=args.tag,
                    is_private=args.private,
                    force=args.force,
                    created_at=args.created_at,
                )
            except (CapturePausedError, SidecarError, ValueError) as exc:
                output = {"error": str(exc)}
                if isinstance(exc, CapturePausedError):
                    output["capture_paused"] = True
                print(json.dumps(output, ensure_ascii=False))
                return 1
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        if args.ime_command == "drain":
            print(json.dumps(drain_system_ime_queue(EventStore(args.db)), ensure_ascii=False))
            return 0
        if args.ime_command == "schema":
            try:
                schema = schema_info()
            except SidecarError as exc:
                print(json.dumps({"error": str(exc)}, ensure_ascii=False))
                return 1
            print(json.dumps(schema, ensure_ascii=False, indent=2))
            return 0

    if args.command == "serve":
        from .web import run_server

        run_server(db_path=args.db, host=args.host, port=args.port)
        return 0

    store = EventStore(args.db)
    drain_system_ime_queue(store)

    if args.command == "add":
        try:
            event = store.add_text(
                args.text,
                source_method=args.method,
                source_app=args.app,
                window_title=args.window_title,
                project=args.project,
                tags=args.tag,
                is_private=args.private,
                force=args.force,
                created_at=args.created_at,
            )
        except (CapturePausedError, ValueError) as exc:
            payload = {"error": str(exc)}
            if isinstance(exc, CapturePausedError):
                payload["capture_paused"] = True
            print(json.dumps(payload, ensure_ascii=False))
            return 1
        print(
            json.dumps(
                {
                    "id": event.id,
                    "created_at": event.created_at,
                    "source_app": event.source_app,
                    "project": event.project,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "ingest":
        try:
            source_text, source_method, window_title = _read_ingest_source(args)
            chunks = _split_ingest_text(source_text, split_paragraphs=args.split_paragraphs)
            if not chunks:
                print(json.dumps({"error": "No text to ingest."}, ensure_ascii=False))
                return 1
            events = [
                store.add_text(
                    chunk,
                    source_method=args.method or source_method,
                    source_app=args.app,
                    window_title=args.window_title or window_title,
                    project=args.project,
                    tags=args.tag,
                    is_private=args.private,
                    force=args.force,
                    created_at=args.created_at,
                )
                for chunk in chunks
            ]
        except (CapturePausedError, ValueError) as exc:
            payload = {"error": str(exc)}
            if isinstance(exc, CapturePausedError):
                payload["capture_paused"] = True
            print(json.dumps(payload, ensure_ascii=False))
            return 1
        print(
            json.dumps(
                {
                    "captured": len(events),
                    "ids": [event.id for event in events],
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "pause":
        store.pause_capture()
        print(json.dumps({"capture_paused": True}, ensure_ascii=False))
        return 0

    if args.command == "resume":
        store.resume_capture()
        print(json.dumps({"capture_paused": False}, ensure_ascii=False))
        return 0

    if args.command == "status":
        print(json.dumps({"capture_paused": store.is_capture_paused()}, ensure_ascii=False))
        return 0

    if args.command == "stats":
        print(json.dumps(store.stats(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "doctor":
        report = store.doctor()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    if args.command == "timeline":
        try:
            rows = store.timeline(start=args.start, end=args.end, include_empty=args.include_empty)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
            return 1
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
            return 0
        for row in rows:
            print(_timeline_row(row))
        return 0

    if args.command == "projects":
        rows = store.projects(include_private=args.include_private)
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
            return 0
        for row in rows:
            print(_project_row(row))
        return 0

    if args.command == "tags":
        rows = store.tags(include_private=args.include_private)
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
            return 0
        for row in rows:
            print(_tag_row(row))
        return 0

    if args.command == "export":
        exported = store.export_data(
            date=args.date,
            include_private=args.include_private,
            include_raw=args.include_raw,
        )
        payload = json.dumps(exported, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload + "\n", encoding="utf-8")
            print(json.dumps({"output": str(args.output), "events": len(exported["events"])}, ensure_ascii=False))
            return 0
        print(payload)
        return 0

    if args.command == "backup":
        include_private = not args.redacted_only
        include_raw = not args.redacted_only
        exported = store.export_data(
            date=args.date,
            include_private=include_private,
            include_raw=include_raw,
        )
        output_path = args.output or args.dir / _backup_filename(args.date)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(exported, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(output_path),
                    "events": len(exported["events"]),
                    "include_private": include_private,
                    "include_raw": include_raw,
                    "doctor_ok": store.doctor()["ok"],
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "import":
        data = json.loads(args.path.read_text(encoding="utf-8"))
        counts = store.import_data(data, replace=args.replace)
        print(json.dumps(counts, ensure_ascii=False))
        return 0

    if args.command == "search":
        results = store.search(
            args.query,
            include_private=args.include_private,
            include_archived_memories=args.all_memories,
            limit=args.limit,
        )
        for result in results:
            print(f"{result.kind} {result.score} {result.id}: {result.content}")
        return 0

    if args.command == "list":
        events = store.list_by_date(args.date)
        for event in events:
            content = event.raw if args.raw else event.redacted
            private_mark = " private" if event.is_private else ""
            context = _event_context(event)
            print(f"{event.created_at} {event.id}{private_mark}{context}: {content}")
        return 0

    if args.command == "summary":
        if args.save:
            record = store.save_daily_summary(args.date)
            print(_summary_record_json(record))
            return 0
        if args.stored or args.version is not None:
            record = store.get_daily_summary_record(args.date, version=args.version)
            if record is None:
                print(json.dumps({"error": "No saved summary found."}, ensure_ascii=False))
                return 1
            print(_summary_record_json(record))
            return 0
        print(json.dumps(store.daily_summary(args.date), ensure_ascii=False, indent=2))
        return 0

    if args.command == "report":
        report = store.daily_report(args.date, include_private=args.include_private)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report, encoding="utf-8")
            print(json.dumps({"output": str(args.output)}, ensure_ascii=False))
            return 0
        print(report, end="")
        return 0

    if args.command in {"daily", "today"}:
        overview = store.daily_overview(args.date, include_private=args.include_private)
        if args.json:
            print(json.dumps(overview, ensure_ascii=False, indent=2))
            return 0
        print(_daily_overview_text(overview), end="")
        return 0

    if args.command == "summaries":
        for record in store.list_daily_summary_records(args.date):
            print(
                f"{record.date} v{record.version} {record.id} "
                f"{record.generator} events={len(record.source_event_ids)} "
                f"created_at={record.created_at}"
            )
        return 0

    if args.command == "review":
        candidates = store.review_candidates(args.date, include_reviewed=args.all)
        for candidate in candidates:
            print(
                f"{candidate.index}. [{candidate.review_status}] "
                f"{candidate.kind} ({candidate.confidence:.2f}) "
                f"{candidate.content} "
                f"source={','.join(candidate.evidence_event_ids)}"
            )
        return 0

    if args.command == "accept":
        memory = store.accept_candidate(args.index, date=args.date, content=args.content)
        print(
            json.dumps(
                {
                    "id": memory.id,
                    "kind": memory.kind,
                    "content": memory.content,
                    "source_event_ids": memory.source_event_ids,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "reject":
        candidate = store.reject_candidate(args.index, date=args.date, note=args.note)
        print(json.dumps({"rejected": candidate.key, "content": candidate.content}, ensure_ascii=False))
        return 0

    if args.command == "memories":
        status = None if args.status == "all" else args.status
        memories = store.list_memories(status=status)
        for memory in memories:
            print(
                f"{memory.created_at} {memory.id} [{memory.status}] "
                f"{memory.kind} ({memory.confidence:.2f}): {memory.content} "
                f"source={','.join(memory.source_event_ids)}"
            )
        return 0

    if args.command == "event":
        if args.event_command == "show":
            event = store.get_event(args.event_id)
            if event is None:
                print(json.dumps({"error": "Event not found."}, ensure_ascii=False))
                return 1
            print(_event_json(event))
            return 0
        if args.event_command == "update":
            private_value = True if args.private else False if args.public else None
            event = store.update_event(
                args.event_id,
                raw=args.raw,
                source_method=args.method,
                source_app=args.app,
                window_title=args.window_title,
                project=args.project,
                tags=args.tags,
                is_private=private_value,
            )
            if event is None:
                print(json.dumps({"error": "Event not found."}, ensure_ascii=False))
                return 1
            print(_event_json(event))
            return 0
        if args.event_command == "delete":
            print(json.dumps({"deleted_events": store.delete_event(args.event_id)}, ensure_ascii=False))
            return 0

    if args.command == "memory":
        if args.memory_command == "show":
            memory = store.get_memory(args.memory_id)
            if memory is None:
                print(json.dumps({"error": "Memory not found."}, ensure_ascii=False))
                return 1
            print(_memory_json(memory))
            return 0
        if args.memory_command == "update":
            memory = store.update_memory(
                args.memory_id,
                kind=args.kind,
                content=args.content,
                confidence=args.confidence,
                source_event_ids=args.source_event_ids,
                status=args.status,
            )
            if memory is None:
                print(json.dumps({"error": "Memory not found."}, ensure_ascii=False))
                return 1
            print(_memory_json(memory))
            return 0
        if args.memory_command == "archive":
            print(json.dumps({"archived_memories": store.archive_memory(args.memory_id)}, ensure_ascii=False))
            return 0
        if args.memory_command == "restore":
            print(json.dumps({"restored_memories": store.restore_memory(args.memory_id)}, ensure_ascii=False))
            return 0
        if args.memory_command == "delete":
            print(json.dumps({"deleted_memories": store.delete_memory(args.memory_id)}, ensure_ascii=False))
            return 0

    if args.command == "delete":
        if args.delete_command == "event":
            print(json.dumps({"deleted_events": store.delete_event(args.event_id)}, ensure_ascii=False))
            return 0
        if args.delete_command == "date":
            print(json.dumps({"deleted_events": store.delete_events_by_date(args.date)}, ensure_ascii=False))
            return 0
        if args.delete_command == "tag":
            print(json.dumps({"deleted_events": store.delete_events_by_tag(args.tag)}, ensure_ascii=False))
            return 0
        if args.delete_command == "summary":
            deleted = store.delete_daily_summary(args.date, version=args.version)
            print(json.dumps({"deleted_summaries": deleted}, ensure_ascii=False))
            return 0
        if args.delete_command == "memory":
            print(json.dumps({"deleted_memories": store.delete_memory(args.memory_id)}, ensure_ascii=False))
            return 0
        if args.delete_command == "archive-memory":
            print(json.dumps({"archived_memories": store.archive_memory(args.memory_id)}, ensure_ascii=False))
            return 0
        if args.delete_command == "purge":
            if not args.yes:
                print(json.dumps({"error": "Pass --yes to confirm full local data deletion."}, ensure_ascii=False))
                return 1
            store.purge_all()
            print(json.dumps({"purged": True}, ensure_ascii=False))
            return 0

    return 1


def _summary_record_json(record: object) -> str:
    return json.dumps(
        {
            "id": record.id,
            "date": record.date,
            "version": record.version,
            "generator": record.generator,
            "created_at": record.created_at,
            "source_event_ids": record.source_event_ids,
            "summary": record.summary,
        },
        ensure_ascii=False,
        indent=2,
    )


def _memory_json(memory: object) -> str:
    return json.dumps(
        {
            "id": memory.id,
            "kind": memory.kind,
            "content": memory.content,
            "confidence": memory.confidence,
            "source_event_ids": memory.source_event_ids,
            "created_at": memory.created_at,
            "updated_at": memory.updated_at,
            "status": memory.status,
        },
        ensure_ascii=False,
        indent=2,
    )


def _event_json(event: object) -> str:
    return json.dumps(
        {
            "id": event.id,
            "created_at": event.created_at,
            "source_method": event.source_method,
            "source_app": event.source_app,
            "window_title": event.window_title,
            "project": event.project,
            "tags": event.tags,
            "is_private": event.is_private,
            "raw": event.raw,
            "redacted": event.redacted,
        },
        ensure_ascii=False,
        indent=2,
    )


def _event_context(event: object) -> str:
    parts = [event.source_app]
    if event.project:
        parts.append(f"project={event.project}")
    if event.window_title:
        parts.append(f"title={event.window_title}")
    return f" [{' '.join(parts)}]"


def _timeline_row(row: dict[str, object]) -> str:
    projects = _compact_counts(dict(row["projects"]))
    tags = _compact_counts(dict(row["tags"]))
    summaries = ",".join(str(version) for version in row["saved_summary_versions"]) or "-"
    return (
        f"{row['date']} "
        f"events={row['events']} public={row['public_events']} private={row['private_events']} "
        f"summaries={summaries} pending={row['pending_memory_candidates']} "
        f"projects={projects} tags={tags}"
    )


def _compact_counts(counts: dict[object, object]) -> str:
    if not counts:
        return "-"
    return ",".join(f"{key}:{value}" for key, value in counts.items())


def _project_row(row: dict[str, object]) -> str:
    tags = _compact_counts(dict(row["tags"]))
    return (
        f"{row['project']} "
        f"events={row['events']} public={row['public_events']} private={row['private_events']} "
        f"days={row['active_days']} last={row['last_event_at']} "
        f"summaries={row['saved_summaries']} memories={row['active_memories']} "
        f"pending={row['pending_memory_candidates']} tags={tags}"
    )


def _tag_row(row: dict[str, object]) -> str:
    projects = _compact_counts(dict(row["projects"]))
    return (
        f"{row['tag']} "
        f"events={row['events']} public={row['public_events']} private={row['private_events']} "
        f"days={row['active_days']} last={row['last_event_at']} "
        f"summaries={row['saved_summaries']} memories={row['active_memories']} "
        f"pending={row['pending_memory_candidates']} projects={projects}"
    )


def _ime_sidecar_stdio() -> int:
    from .ime_sidecar import SidecarError, StubRimeSidecar

    try:
        request = json.loads(sys.stdin.read() or "{}")
        method = str(request["method"])
        params = dict(request.get("params", {}))
        sidecar = StubRimeSidecar(schema=str(params.get("schema", "luna_pinyin")))
        if method == "schema":
            result = sidecar.schema_info()
        elif method == "compose":
            result = sidecar.compose(str(params.get("text", "")))
        elif method == "candidates":
            result = {"candidates": sidecar.candidates(str(params.get("text", "")))}
        elif method == "commit":
            result = sidecar.commit(
                str(params.get("text", "")),
                candidate_index=int(params.get("candidate_index", 1)),
            )
        elif method == "clear":
            result = sidecar.clear()
        else:
            raise SidecarError(f"Unsupported IME sidecar method: {method}")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, SidecarError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"result": result}, ensure_ascii=False))
    return 0


def _daily_overview_text(overview: dict[str, object]) -> str:
    events = dict(overview["events"])
    summary = dict(overview["summary"])
    saved_summaries = list(overview["saved_summaries"])
    pending_candidates = list(overview["pending_memory_candidates"])
    active_memories = list(overview["active_memories"])
    projects = _compact_counts(dict(events["projects"]))
    tags = _compact_counts(dict(events["tags"]))
    latest_summary = saved_summaries[-1] if saved_summaries else None
    latest_summary_text = f"v{latest_summary['version']} {latest_summary['id']}" if latest_summary else "-"

    lines = [
        f"MirrorMe Daily {overview['date']}",
        (
            f"events={events['total']} public={events['public']} private={events['private']} "
            f"saved_summaries={len(saved_summaries)} latest_summary={latest_summary_text} "
            f"pending={len(pending_candidates)} active_memories={len(active_memories)}"
        ),
        f"projects={projects}",
        f"tags={tags}",
        f"summary={summary['summary']}",
        "",
        "Topics:",
        *_text_list(list(summary["topics"])),
        "",
        "Pending Memory Candidates:",
        *_candidate_lines(pending_candidates),
        "",
        "Active Memories:",
        *_memory_lines(active_memories),
    ]
    return "\n".join(lines).rstrip() + "\n"


def _text_list(items: list[object]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


def _candidate_lines(candidates: list[object]) -> list[str]:
    if not candidates:
        return ["- None"]
    return [
        f"- {candidate['index']}. [{candidate['review_status']}] "
        f"{candidate['kind']} ({float(candidate['confidence']):.2f}) "
        f"{candidate['content']} source={','.join(candidate['evidence_event_ids'])}"
        for candidate in candidates
    ]


def _memory_lines(memories: list[object]) -> list[str]:
    if not memories:
        return ["- None"]
    return [
        f"- [{memory['status']}] {memory['kind']} ({float(memory['confidence']):.2f}) "
        f"{memory['content']} source={','.join(memory['source_event_ids'])}"
        for memory in memories
    ]


def _read_ingest_source(args: object) -> tuple[str, str, str | None]:
    path = args.path
    if args.stdin and path is not None:
        raise ValueError("Pass either a file path or --stdin, not both.")
    if args.stdin:
        return sys.stdin.read(), "stdin", None
    if path is None:
        raise ValueError("Pass a file path or --stdin.")
    return path.read_text(encoding="utf-8"), "file", path.name


def _split_ingest_text(text: str, *, split_paragraphs: bool) -> list[str]:
    if split_paragraphs:
        return [chunk.strip() for chunk in re.split(r"\n\s*\n+", text) if chunk.strip()]
    stripped = text.strip()
    return [stripped] if stripped else []


def _backup_filename(date: str | None) -> str:
    timestamp = datetime.now(LOCAL_TZ).strftime("%Y%m%d-%H%M%S")
    date_part = f"{date}-" if date else ""
    return f"mirrorme-backup-{date_part}{timestamp}.json"


if __name__ == "__main__":
    raise SystemExit(main())
