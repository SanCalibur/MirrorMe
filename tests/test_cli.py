import io
import json
from pathlib import Path

from mirrorme.cli import main
from mirrorme.store import EventStore


def test_add_accepts_created_at_for_historical_backfill(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "mirrorme.db"

    result = main(
        [
            "--db",
            str(db_path),
            "add",
            "Backfilled output.",
            "--created-at",
            "2026-06-25T21:15:00+08:00",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    [event] = EventStore(db_path).list_by_date("2026-06-25")
    assert result == 0
    assert output["created_at"] == "2026-06-25T21:15:00+08:00"
    assert event.raw == "Backfilled output."


def test_ingest_file_splits_paragraphs(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "mirrorme.db"
    source = tmp_path / "daily-note.txt"
    source.write_text(
        "First captured paragraph.\n\n"
        "Second captured paragraph with email test@example.com.\n\n",
        encoding="utf-8",
    )

    result = main(
        [
            "--db",
            str(db_path),
            "ingest",
            str(source),
            "--split-paragraphs",
            "--project",
            "MirrorMe",
            "--tag",
            "batch",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    events = EventStore(db_path).list_events()
    assert result == 0
    assert output["captured"] == 2
    assert output["ids"] == [event.id for event in events]
    assert [event.raw for event in events] == [
        "First captured paragraph.",
        "Second captured paragraph with email test@example.com.",
    ]
    assert events[0].source_method == "file"
    assert events[0].window_title == "daily-note.txt"
    assert events[0].project == "MirrorMe"
    assert events[0].tags == ["batch"]
    assert events[1].redacted == "Second captured paragraph with email [REDACTED:email]."


def test_ingest_uses_created_at_for_all_split_events(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "mirrorme.db"
    source = tmp_path / "historical.txt"
    source.write_text("First old note.\n\nSecond old note.", encoding="utf-8")

    result = main(
        [
            "--db",
            str(db_path),
            "ingest",
            str(source),
            "--split-paragraphs",
            "--created-at",
            "2026-06-25T08:00:00+08:00",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    events = EventStore(db_path).list_by_date("2026-06-25")
    assert result == 0
    assert output["captured"] == 2
    assert [event.created_at for event in events] == [
        "2026-06-25T08:00:00+08:00",
        "2026-06-25T08:00:00+08:00",
    ]
    assert events[0].id.endswith("_001")
    assert events[1].id.endswith("_002")


def test_ingest_stdin_creates_single_event(tmp_path: Path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "mirrorme.db"
    monkeypatch.setattr("sys.stdin", io.StringIO("Captured from stdin.\n"))

    result = main(["--db", str(db_path), "ingest", "--stdin", "--method", "pipe"])

    output = json.loads(capsys.readouterr().out)
    [event] = EventStore(db_path).list_events()
    assert result == 0
    assert output["captured"] == 1
    assert event.raw == "Captured from stdin."
    assert event.source_method == "pipe"


def test_ingest_requires_file_or_stdin(tmp_path: Path, capsys) -> None:
    result = main(["--db", str(tmp_path / "mirrorme.db"), "ingest"])

    output = json.loads(capsys.readouterr().out)
    assert result == 1
    assert output["error"] == "Pass a file path or --stdin."


def test_add_rejects_invalid_created_at(tmp_path: Path, capsys) -> None:
    result = main(
        [
            "--db",
            str(tmp_path / "mirrorme.db"),
            "add",
            "Bad timestamp.",
            "--created-at",
            "not-a-date",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert result == 1
    assert output["error"] == "created_at must be an ISO datetime or date."


def test_doctor_command_reports_json(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "mirrorme.db"
    EventStore(db_path).add_text("Healthy event.")

    result = main(["--db", str(db_path), "doctor"])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["ok"] is True
    assert output["counts"]["events"] == 1


def test_ime_status_command_reports_selected_engine(tmp_path: Path, capsys) -> None:
    result = main(["--db", str(tmp_path / "mirrorme.db"), "ime", "status"])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["selected_engine_id"] == "rime-librime"
    assert output["selected_engine"]["license"] == "BSD-3-Clause"
    assert output["capture_policy"]["capture_raw_keystrokes"] is False


def test_ime_engines_command_lists_candidates(tmp_path: Path, capsys) -> None:
    result = main(["--db", str(tmp_path / "mirrorme.db"), "ime", "engines"])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert [engine["id"] for engine in output if engine["recommended"]] == ["rime-librime"]


def test_ime_probe_command_reports_native_adapter(tmp_path: Path, capsys) -> None:
    result = main(["--db", str(tmp_path / "mirrorme.db"), "ime", "probe"])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["engine_id"] == "rime-librime"
    assert output["binary_env"] == "MIRRORME_RIME_BINARY"
    assert "readiness" in output


def test_ime_compliance_command_reports_manifest_state(tmp_path: Path, capsys) -> None:
    result = main(["--db", str(tmp_path / "mirrorme.db"), "ime", "compliance"])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["ok_for_commercial_bundle"] is False
    assert output["counts"]["allowed"] == 2
    assert output["counts"]["pending"] >= 1
    assert output["counts"]["blockers"] >= 1


def test_ime_compose_command_uses_sidecar_protocol(tmp_path: Path, capsys) -> None:
    result = main(["--db", str(tmp_path / "mirrorme.db"), "ime", "compose", "ni hao"])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["preedit"] == "ni hao"
    assert output["candidates"][0]["text"] == "你好"


def test_ime_commit_command_uses_sidecar_protocol(tmp_path: Path, capsys) -> None:
    result = main(["--db", str(tmp_path / "mirrorme.db"), "ime", "commit", "zhong wen"])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["committed"] == "中文"


def test_ime_commit_command_reports_bad_candidate(tmp_path: Path, capsys) -> None:
    result = main(["--db", str(tmp_path / "mirrorme.db"), "ime", "commit", "ni hao", "--candidate", "99"])

    output = json.loads(capsys.readouterr().out)
    assert result == 1
    assert "candidate_index" in output["error"]


def test_ime_capture_command_commits_and_feeds_analysis(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "mirrorme.db"

    result = main(
        [
            "--db",
            str(db_path),
            "ime",
            "capture",
            "wo jue de mirrorme xian zuo shu ju fen xi",
            "--project",
            "MirrorMe",
            "--tag",
            "analysis",
            "--created-at",
            "2026-06-25T09:00:00+08:00",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    [event] = EventStore(db_path).list_by_date("2026-06-25")
    summary = EventStore(db_path).daily_summary("2026-06-25")
    assert result == 0
    assert output["composition"]["committed"] == "我觉得MirrorMe先做数据分析"
    assert output["event"]["id"] == event.id
    assert output["event"]["source_method"] == "ime_commit"
    assert output["event"]["tags"] == ["ime", "committed", "analysis"]
    assert output["analysis"]["source_event_ids"] == [event.id]
    assert event.raw == "我觉得MirrorMe先做数据分析"
    assert event.project == "MirrorMe"
    assert summary["memory_candidates"][0]["kind"] == "preference"


def test_ime_sidecar_command_runs_json_stdio(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps({"method": "compose", "params": {"text": "ni hao"}})),
    )

    result = main(["--db", str(tmp_path / "mirrorme.db"), "ime", "sidecar"])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["result"]["candidates"][0]["text"] == "你好"


def test_timeline_command_prints_daily_rows(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "mirrorme.db"
    store = EventStore(db_path)
    store.add_text(
        "Timeline event.",
        created_at="2026-06-25T10:00:00+08:00",
        project="MirrorMe",
        tags=["stage1"],
    )

    result = main(["--db", str(db_path), "timeline", "--start", "2026-06-25", "--end", "2026-06-25"])

    output = capsys.readouterr().out
    assert result == 0
    assert "2026-06-25 events=1 public=1 private=0" in output
    assert "projects=MirrorMe:1" in output
    assert "tags=stage1:1" in output


def test_timeline_command_can_print_json(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "mirrorme.db"
    EventStore(db_path).add_text("Timeline event.", created_at="2026-06-25T10:00:00+08:00")

    result = main(["--db", str(db_path), "timeline", "--json"])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output[0]["date"] == "2026-06-25"
    assert output[0]["events"] == 1


def test_daily_command_prints_review_dashboard(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "mirrorme.db"
    store = EventStore(db_path)
    event = store.add_text(
        "\u6211\u51b3\u5b9a MirrorMe \u5148\u505a daily command\u3002",
        created_at="2026-06-25T10:00:00+08:00",
        project="MirrorMe",
        tags=["daily"],
    )
    store.save_daily_summary(event.created_at[:10])

    result = main(["--db", str(db_path), "daily", "--date", "2026-06-25"])

    output = capsys.readouterr().out
    assert result == 0
    assert "MirrorMe Daily 2026-06-25" in output
    assert "events=1 public=1 private=0 saved_summaries=1" in output
    assert "projects=MirrorMe:1" in output
    assert "tags=daily:1" in output
    assert "Pending Memory Candidates:" in output
    assert "daily command" in output


def test_today_alias_can_print_daily_json_and_include_private(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "mirrorme.db"
    store = EventStore(db_path)
    store.add_text(
        "Public daily event.",
        created_at="2026-06-25T10:00:00+08:00",
        tags=["daily"],
    )
    store.add_text(
        "Private daily event.",
        created_at="2026-06-25T11:00:00+08:00",
        tags=["daily"],
        is_private=True,
    )

    result = main(["--db", str(db_path), "today", "--date", "2026-06-25", "--include-private", "--json"])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["date"] == "2026-06-25"
    assert output["events"]["total"] == 2
    assert output["events"]["private"] == 1
    assert output["events"]["tags"] == {"daily": 2}


def test_projects_command_prints_project_rows(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "mirrorme.db"
    store = EventStore(db_path)
    store.add_text(
        "Project event.",
        created_at="2026-06-25T10:00:00+08:00",
        project="MirrorMe",
        tags=["stage1"],
    )

    result = main(["--db", str(db_path), "projects"])

    output = capsys.readouterr().out
    assert result == 0
    assert "MirrorMe events=1 public=1 private=0" in output
    assert "tags=stage1:1" in output


def test_projects_command_can_print_json_and_include_private(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "mirrorme.db"
    store = EventStore(db_path)
    store.add_text("Public project event.", project="MirrorMe")
    store.add_text("Private project event.", project="MirrorMe", is_private=True)

    result = main(["--db", str(db_path), "projects", "--include-private", "--json"])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output[0]["project"] == "MirrorMe"
    assert output[0]["events"] == 2
    assert output[0]["private_events"] == 1


def test_tags_command_prints_tag_rows(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "mirrorme.db"
    store = EventStore(db_path)
    store.add_text(
        "Tagged event.",
        created_at="2026-06-25T10:00:00+08:00",
        project="MirrorMe",
        tags=["stage1"],
    )

    result = main(["--db", str(db_path), "tags"])

    output = capsys.readouterr().out
    assert result == 0
    assert "stage1 events=1 public=1 private=0" in output
    assert "projects=MirrorMe:1" in output


def test_tags_command_can_print_json_and_include_private(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "mirrorme.db"
    store = EventStore(db_path)
    store.add_text("Public tagged event.", tags=["stage1"])
    store.add_text("Private tagged event.", tags=["stage1"], is_private=True)

    result = main(["--db", str(db_path), "tags", "--include-private", "--json"])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output[0]["tag"] == "stage1"
    assert output[0]["events"] == 2
    assert output[0]["private_events"] == 1


def test_backup_writes_complete_importable_export(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "mirrorme.db"
    backup_dir = tmp_path / "backups"
    store = EventStore(db_path)
    public_event = store.add_text("Public event.")
    private_event = store.add_text("Private raw event.", is_private=True)

    result = main(["--db", str(db_path), "backup", "--dir", str(backup_dir)])

    output = json.loads(capsys.readouterr().out)
    backup_path = Path(output["output"])
    backup = json.loads(backup_path.read_text(encoding="utf-8"))
    assert result == 0
    assert backup_path.parent == backup_dir
    assert backup_path.name.startswith("mirrorme-backup-")
    assert output["events"] == 2
    assert output["include_private"] is True
    assert output["include_raw"] is True
    assert output["doctor_ok"] is True
    assert {event["id"] for event in backup["events"]} == {public_event.id, private_event.id}
    assert backup["events"][1]["content"]["raw"] == "Private raw event."


def test_backup_redacted_only_excludes_private_and_raw(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "mirrorme.db"
    output_path = tmp_path / "backup.json"
    store = EventStore(db_path)
    public_event = store.add_text("Email test@example.com")
    store.add_text("Private raw event.", is_private=True)

    result = main(["--db", str(db_path), "backup", "--output", str(output_path), "--redacted-only"])

    output = json.loads(capsys.readouterr().out)
    backup = json.loads(output_path.read_text(encoding="utf-8"))
    assert result == 0
    assert output["output"] == str(output_path)
    assert output["events"] == 1
    assert output["include_private"] is False
    assert output["include_raw"] is False
    assert [event["id"] for event in backup["events"]] == [public_event.id]
    assert backup["events"][0]["content"] == {"redacted": "Email [REDACTED:email]"}
