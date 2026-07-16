from pathlib import Path
import sqlite3

import pytest

from mirrorme.store import CapturePausedError, EventStore


def test_add_and_list_text_event(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")

    event = store.add_text("Today I discussed MirrorMe.", tags=["idea"])
    events = store.list_by_date(event.created_at[:10])

    assert len(events) == 1
    assert events[0].id == event.id
    assert events[0].raw == "Today I discussed MirrorMe."
    assert events[0].tags == ["idea"]


def test_add_text_keeps_lightweight_context(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")

    event = store.add_text(
        "Discussed the next MirrorMe data model.",
        source_method="quick_input",
        source_app="Obsidian",
        window_title="MirrorMe Notes",
        project="MirrorMe",
        tags=["architecture"],
    )
    [stored] = store.list_by_date(event.created_at[:10])
    summary = store.daily_summary(event.created_at[:10])

    assert stored.source_method == "quick_input"
    assert stored.source_app == "Obsidian"
    assert stored.window_title == "MirrorMe Notes"
    assert stored.project == "MirrorMe"
    assert summary["topics"][:2] == ["MirrorMe", "architecture"]


def test_add_text_can_backfill_created_at(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")

    event = store.add_text(
        "Historical note for the right day.",
        created_at="2026-06-25T09:30:00+08:00",
    )

    assert event.created_at == "2026-06-25T09:30:00+08:00"
    assert event.id.startswith("evt_20260625_093000_0800_")
    assert store.list_by_date("2026-06-25") == [event]
    assert store.daily_summary("2026-06-25")["source_event_ids"] == [event.id]


def test_add_text_date_only_backfill_uses_local_midnight(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")

    event = store.add_text("Date-only backfill.", created_at="2026-06-25")

    assert event.created_at == "2026-06-25T00:00:00+08:00"


def test_update_event_changes_content_context_and_privacy(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    event = store.add_text("Original text", tags=["old"])

    updated = store.update_event(
        event.id,
        raw="Email me at test@example.com",
        source_method="quick_input",
        source_app="Obsidian",
        window_title="MirrorMe Notes",
        project="MirrorMe",
        tags=["new"],
        is_private=True,
    )

    assert updated is not None
    assert updated.raw == "Email me at test@example.com"
    assert updated.redacted == "Email me at [REDACTED:email]"
    assert updated.source_method == "quick_input"
    assert updated.source_app == "Obsidian"
    assert updated.window_title == "MirrorMe Notes"
    assert updated.project == "MirrorMe"
    assert updated.tags == ["new"]
    assert updated.is_private
    assert store.get_event(event.id) == updated
    assert store.daily_summary(event.created_at[:10])["source_event_ids"] == []


def test_update_event_project_and_tags_affect_summary_topics(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    event = store.add_text("Generic text")

    store.update_event(event.id, project="MirrorMe", tags=["context"])
    summary = store.daily_summary(event.created_at[:10])

    assert summary["topics"][:2] == ["MirrorMe", "context"]


def test_update_missing_event_returns_none(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")

    assert store.get_event("missing") is None
    assert store.update_event("missing", raw="Nope") is None


def test_private_events_are_excluded_from_summary(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")

    public_event = store.add_text("Public thought")
    private_event = store.add_text("Private thought", is_private=True)
    summary = store.daily_summary(public_event.created_at[:10])

    assert summary["event_count"] == 1
    assert summary["source_event_ids"] == [public_event.id]
    assert private_event.id not in summary["source_event_ids"]


def test_daily_summary_extracts_structure(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")

    event = store.add_text(
        "\u6211\u51b3\u5b9a MirrorMe \u5148\u505a text capture\u3002"
        "TODO: \u660e\u5929\u8865 review loop\uff1f",
        tags=["stage1"],
    )
    summary = store.daily_summary(event.created_at[:10])

    assert summary["topics"][:2] == ["stage1", "mirrorme"]
    assert summary["decisions"] == [{"content": "\u6211\u51b3\u5b9a MirrorMe \u5148\u505a text capture\u3002"}]
    assert summary["commitments"] == [{"content": "TODO: \u660e\u5929\u8865 review loop\uff1f"}]
    assert summary["open_questions"] == [{"content": "TODO: \u660e\u5929\u8865 review loop\uff1f"}]
    assert summary["memory_candidates"] == [
        {
            "kind": "decision",
            "content": "\u6211\u51b3\u5b9a MirrorMe \u5148\u505a text capture\u3002",
            "confidence": 0.62,
            "evidence_event_ids": [event.id],
        }
    ]


def test_daily_summary_composes_adjacent_system_ime_commits(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    first = store.add_text(
        "我觉得",
        source_method="system_ime_commit",
        source_app="MirrorMe Pinyin (Weasel)",
        created_at="2026-06-25T09:00:00+08:00",
    )
    second = store.add_text(
        "这个功能需要优先完成。",
        source_method="system_ime_commit",
        source_app="MirrorMe Pinyin (Weasel)",
        created_at="2026-06-25T09:00:03+08:00",
    )

    summary = store.daily_summary("2026-06-25")

    assert summary["event_count"] == 2
    assert summary["summary"] == "我觉得这个功能需要优先完成。"
    assert summary["memory_candidates"] == [
        {
            "kind": "preference",
            "content": "我觉得这个功能需要优先完成。",
            "confidence": 0.55,
            "evidence_event_ids": [first.id, second.id],
        }
    ]


def test_daily_summary_extends_the_system_ime_window_after_each_commit(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    first = store.add_text(
        "我觉得",
        source_method="system_ime_commit",
        source_app="MirrorMe Pinyin (Weasel)",
        created_at="2026-06-25T09:00:00+08:00",
    )
    second = store.add_text(
        "这个功能",
        source_method="system_ime_commit",
        source_app="MirrorMe Pinyin (Weasel)",
        created_at="2026-06-25T09:00:07+08:00",
    )
    third = store.add_text(
        "需要优先完成。",
        source_method="system_ime_commit",
        source_app="MirrorMe Pinyin (Weasel)",
        created_at="2026-06-25T09:00:14+08:00",
    )

    summary = store.daily_summary("2026-06-25")

    assert summary["summary"] == "我觉得这个功能需要优先完成。"
    assert summary["memory_candidates"][0]["evidence_event_ids"] == [first.id, second.id, third.id]


def test_daily_state_assessments_are_versioned_and_follow_event_deletion(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    event = store.add_text(
        "我很焦虑，截止时间快到了，但我决定先完成最小下一步。",
        created_at="2026-06-25T09:00:00+08:00",
    )

    first = store.save_daily_state_assessment("2026-06-25")
    second = store.save_daily_state_assessment("2026-06-25")

    assert first.version == 1
    assert second.version == 2
    assert first.source_event_ids == [event.id]
    assert first.assessment["metrics"][2]["key"] == "mood"
    assert store.list_state_assessments(latest_per_day=True) == [second]
    assert store.delete_event(event.id) == 1
    assert store.list_state_assessments() == []


def test_state_assessments_can_be_filtered_by_date_range(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    for date in ("2026-06-23", "2026-06-24", "2026-06-25"):
        store.add_text(f"A note for {date}", created_at=f"{date}T09:00:00+08:00")
        store.save_daily_state_assessment(date)

    records = store.list_state_assessments(
        start_date="2026-06-24",
        end_date="2026-06-25",
        latest_per_day=True,
    )

    assert [record.date for record in records] == ["2026-06-24", "2026-06-25"]


def test_llm_state_assessments_are_saved_from_accepted_documents_and_filterable(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    event = store.add_text("A cleaned observation source", created_at="2026-06-25T09:00:00+08:00")
    document = store.save_cleaned_document(date="2026-06-25", content="A cleaned observation source", source_event_ids=[event.id], model="cleaner", prompt="clean")
    accepted = store.accept_cleaned_document(document.id)
    assert accepted is not None

    saved = store.save_llm_state_assessment(accepted, {"method": "llm", "metrics": [], "summary": "Observed", "confidence": 0.7})

    assert saved.assessment["cleaned_document_id"] == document.id
    assert store.list_state_assessments(method="llm") == [saved]
    assert store.list_state_assessments(method="rules") == []


def test_event_dates_excludes_private_events_by_default(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    store.add_text("Public", created_at="2026-06-24T09:00:00+08:00")
    store.add_text("Private", is_private=True, created_at="2026-06-25T09:00:00+08:00")

    assert store.event_dates() == ["2026-06-24"]
    assert store.event_dates(include_private=True) == ["2026-06-24", "2026-06-25"]


def test_accept_candidate_creates_memory_and_removes_from_pending_review(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    event = store.add_text("\u6211\u51b3\u5b9a MirrorMe \u5148\u505a review loop\u3002")
    date = event.created_at[:10]

    candidates = store.review_candidates(date)
    memory = store.accept_candidate(1, date=date, content="MirrorMe should build the review loop first.")

    assert len(candidates) == 1
    assert memory.kind == "decision"
    assert memory.content == "MirrorMe should build the review loop first."
    assert memory.source_event_ids == [event.id]
    assert store.review_candidates(date) == []
    assert store.list_memories() == [memory]


def test_reject_candidate_removes_from_pending_review_without_memory(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    event = store.add_text("\u6211\u51b3\u5b9a MirrorMe \u5148\u505a discardable idea\u3002")
    date = event.created_at[:10]

    rejected = store.reject_candidate(1, date=date, note="not stable enough")

    assert rejected.review_status == "pending"
    assert store.review_candidates(date) == []
    assert store.list_memories() == []


def test_save_daily_summary_creates_versioned_records(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    event = store.add_text("Today I decided to persist daily summaries.", tags=["summary"])
    date = event.created_at[:10]

    first = store.save_daily_summary(date)
    second = store.save_daily_summary(date)

    assert first.id.endswith("_001")
    assert second.id.endswith("_002")
    assert first.version == 1
    assert second.version == 2
    assert first.summary["source_event_ids"] == [event.id]
    assert store.get_daily_summary_record(date) == second
    assert store.get_daily_summary_record(date, version=1) == first
    assert store.list_daily_summary_records(date) == [first, second]


def test_daily_report_renders_human_readable_markdown(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    event = store.add_text(
        "\u6211\u51b3\u5b9a MirrorMe \u5148\u505a daily reports\u3002TODO: review the report tonight?",
        source_app="Obsidian",
        window_title="MirrorMe Notes",
        project="MirrorMe",
        tags=["report"],
    )
    date = event.created_at[:10]
    store.save_daily_summary(date)
    store.accept_candidate(1, date=date)

    report = store.daily_report(date)

    assert report.startswith(f"# MirrorMe Daily Report: {date}\n")
    assert "## Overview" in report
    assert "- Events: 1" in report
    assert "- Saved summaries: 1" in report
    assert "- MirrorMe" in report
    assert "## Decisions" in report
    assert "daily reports" in report
    assert "## Commitments" in report
    assert "## Open Questions" in report
    assert "## Related Memories" in report
    assert event.id in report
    assert "v1" in report


def test_daily_report_excludes_private_events_by_default(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    public_event = store.add_text("Public daily note.")
    private_event = store.add_text("Email me at secret@example.com", is_private=True)
    date = public_event.created_at[:10]

    public_report = store.daily_report(date)
    private_report = store.daily_report(date, include_private=True)

    assert public_event.id in public_report
    assert private_event.id not in public_report
    assert "secret@example.com" not in private_report
    assert "Email me at [REDACTED:email]" in private_report
    assert f"{private_event.id} private" in private_report


def test_daily_overview_combines_daily_review_state(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    public_event = store.add_text(
        "\u6211\u51b3\u5b9a MirrorMe \u5148\u505a daily dashboard\u3002",
        created_at="2026-06-25T09:00:00+08:00",
        project="MirrorMe",
        tags=["daily"],
    )
    private_event = store.add_text(
        "Private daily note.",
        created_at="2026-06-25T10:00:00+08:00",
        project="MirrorMe",
        tags=["private"],
        is_private=True,
    )
    date = public_event.created_at[:10]
    store.save_daily_summary(date)

    public_overview = store.daily_overview(date)
    private_overview = store.daily_overview(date, include_private=True)
    memory = store.accept_candidate(1, date=date)
    reviewed_overview = store.daily_overview(date)

    assert public_overview["events"]["total"] == 1
    assert public_overview["events"]["private"] == 0
    assert public_overview["events"]["projects"] == {"MirrorMe": 1}
    assert public_overview["events"]["tags"] == {"daily": 1}
    assert public_overview["summary"]["source_event_ids"] == [public_event.id]
    assert len(public_overview["saved_summaries"]) == 1
    assert public_overview["pending_memory_candidates"][0]["review_status"] == "pending"
    assert private_overview["events"]["total"] == 2
    assert private_overview["events"]["private"] == 1
    assert private_overview["events"]["tags"] == {"daily": 1, "private": 1}
    assert private_event.id not in private_overview["summary"]["source_event_ids"]
    assert reviewed_overview["pending_memory_candidates"] == []
    assert reviewed_overview["active_memories"][0]["id"] == memory.id


def test_delete_event_removes_source_from_processing_outputs(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    event = store.add_text("\u6211\u51b3\u5b9a MirrorMe \u5148\u505a privacy deletion\u3002")
    date = event.created_at[:10]
    store.save_daily_summary(date)
    memory = store.accept_candidate(1, date=date)

    deleted = store.delete_event(event.id)

    assert deleted == 1
    assert store.list_by_date(date) == []
    assert store.daily_summary(date)["source_event_ids"] == []
    assert store.list_daily_summary_records(date) == []
    assert store.list_memories() == []
    archived = store.list_memories(status="archived")
    assert len(archived) == 1
    assert archived[0].id == memory.id


def test_delete_events_by_date_removes_events_and_saved_summaries(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    event = store.add_text("A public event")
    date = event.created_at[:10]
    store.save_daily_summary(date)

    deleted = store.delete_events_by_date(date)

    assert deleted == 1
    assert store.list_by_date(date) == []
    assert store.list_daily_summary_records(date) == []


def test_delete_events_by_tag_removes_matching_events_and_saved_summaries(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    keep = store.add_text("Keep this event", tags=["keep"])
    remove = store.add_text("Remove this event", tags=["remove"])
    date = remove.created_at[:10]
    store.save_daily_summary(date)

    deleted = store.delete_events_by_tag("remove")

    remaining = store.list_by_date(date)
    assert deleted == 1
    assert remaining == [keep]
    assert store.list_daily_summary_records(date) == []


def test_archive_and_delete_memory(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    memory = store.add_memory(
        kind="preference",
        content="Local-first data matters.",
        confidence=0.9,
        source_event_ids=[],
    )

    assert store.archive_memory(memory.id) == 1
    assert store.list_memories() == []
    assert store.list_memories(status="archived")[0].id == memory.id
    assert store.delete_memory(memory.id) == 1
    assert store.list_memories(status="archived") == []


def test_update_memory_changes_fields_and_timestamp(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    memory = store.add_memory(
        kind="preference",
        content="Old content.",
        confidence=0.4,
        source_event_ids=["evt_old"],
    )

    updated = store.update_memory(
        memory.id,
        kind="decision",
        content="Updated content.",
        confidence=0.9,
        source_event_ids=["evt_new"],
        status="archived",
    )

    assert updated is not None
    assert updated.id == memory.id
    assert updated.kind == "decision"
    assert updated.content == "Updated content."
    assert updated.confidence == 0.9
    assert updated.source_event_ids == ["evt_new"]
    assert updated.status == "archived"
    assert updated.updated_at >= memory.updated_at
    assert store.get_memory(memory.id) == updated


def test_restore_memory_reactivates_archived_memory(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    memory = store.add_memory(
        kind="decision",
        content="Restore me.",
        confidence=0.5,
        source_event_ids=[],
        status="archived",
    )

    assert store.restore_memory(memory.id) == 1
    assert store.get_memory(memory.id).status == "active"
    assert store.list_memories() == [store.get_memory(memory.id)]


def test_update_missing_memory_returns_none(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")

    assert store.get_memory("missing") is None
    assert store.update_memory("missing", content="Nope") is None


def test_purge_all_removes_everything(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    event = store.add_text("\u6211\u51b3\u5b9a MirrorMe \u5148\u505a purge\u3002")
    date = event.created_at[:10]
    store.save_daily_summary(date)
    store.accept_candidate(1, date=date)

    store.purge_all()

    assert store.list_by_date(date) == []
    assert store.list_daily_summary_records() == []
    assert store.list_memories(status=None) == []
    assert store.review_candidates(date, include_reviewed=True) == []


def test_capture_pause_blocks_add_text_unless_forced(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")

    store.pause_capture()

    assert store.is_capture_paused()
    with pytest.raises(CapturePausedError):
        store.add_text("This should not be captured.")

    forced = store.add_text("Forced capture.", force=True)
    store.resume_capture()
    resumed = store.add_text("Normal capture after resume.")

    assert not store.is_capture_paused()
    assert store.list_by_date(forced.created_at[:10]) == [forced, resumed]


def test_purge_all_resets_capture_pause(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")

    store.pause_capture()
    store.purge_all()

    assert not store.is_capture_paused()


def test_existing_database_gets_context_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "mirrorme.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        create table text_events (
            id text primary key,
            raw text not null,
            redacted text not null,
            created_at text not null,
            source_method text not null,
            source_app text not null,
            tags_json text not null,
            is_private integer not null default 0
        )
        """
    )
    conn.close()

    store = EventStore(db_path)
    event = store.add_text("Context migration works.", project="MirrorMe")
    [stored] = store.list_by_date(event.created_at[:10])

    assert stored.project == "MirrorMe"
    assert stored.window_title is None


def test_export_data_defaults_to_redacted_public_data(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    public_event = store.add_text(
        "Email me at test@example.com",
        source_app="Obsidian",
        window_title="MirrorMe Notes",
        project="MirrorMe",
        tags=["export"],
    )
    private_event = store.add_text("Private raw content", is_private=True)
    store.save_daily_summary(public_event.created_at[:10])
    memory = store.add_memory(
        kind="preference",
        content="Local exports should be redacted by default.",
        confidence=0.8,
        source_event_ids=[public_event.id],
    )

    exported = store.export_data(date=public_event.created_at[:10])

    assert exported["schema_version"] == 1
    assert exported["filters"]["include_private"] is False
    assert exported["filters"]["include_raw"] is False
    assert [event["id"] for event in exported["events"]] == [public_event.id]
    assert private_event.id not in [event["id"] for event in exported["events"]]
    assert exported["events"][0]["content"] == {"redacted": "Email me at [REDACTED:email]"}
    assert exported["events"][0]["source"]["app"] == "Obsidian"
    assert exported["daily_summaries"][0]["source_event_ids"] == [public_event.id]
    assert exported["memories"][0]["id"] == memory.id


def test_export_data_can_include_private_and_raw_content(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    event = store.add_text("Private raw content", is_private=True)

    exported = store.export_data(include_private=True, include_raw=True)

    assert exported["filters"]["include_private"] is True
    assert exported["filters"]["include_raw"] is True
    assert exported["events"][0]["id"] == event.id
    assert exported["events"][0]["content"]["raw"] == "Private raw content"


def test_import_data_restores_exported_records(tmp_path: Path) -> None:
    source = EventStore(tmp_path / "source.db")
    event = source.add_text(
        "Export/import should preserve raw content.",
        source_app="Obsidian",
        project="MirrorMe",
        tags=["import"],
    )
    summary = source.save_daily_summary(event.created_at[:10])
    memory = source.add_memory(
        kind="decision",
        content="MirrorMe should support import.",
        confidence=0.7,
        source_event_ids=[event.id],
    )
    exported = source.export_data(include_raw=True)

    target = EventStore(tmp_path / "target.db")
    counts = target.import_data(exported)

    [imported_event] = target.list_events()
    assert counts["events_inserted"] == 1
    assert counts["summaries_inserted"] == 1
    assert counts["memories_inserted"] == 1
    assert imported_event.id == event.id
    assert imported_event.raw == "Export/import should preserve raw content."
    assert imported_event.source_app == "Obsidian"
    assert target.list_daily_summary_records()[0].id == summary.id
    assert target.list_memories()[0].id == memory.id


def test_import_data_skips_existing_records_unless_replace_is_set(tmp_path: Path) -> None:
    source = EventStore(tmp_path / "source.db")
    event = source.add_text("Original raw.", tags=["original"])
    exported = source.export_data(include_raw=True)

    target = EventStore(tmp_path / "target.db")
    target.import_data(exported)
    exported["events"][0]["content"]["raw"] = "Updated raw."
    exported["events"][0]["content"]["redacted"] = "Updated raw."

    skipped = target.import_data(exported)
    [still_original] = target.list_events()
    replaced = target.import_data(exported, replace=True)
    [updated] = target.list_events()

    assert skipped["events_skipped"] == 1
    assert still_original.raw == "Original raw."
    assert replaced["events_updated"] == 1
    assert updated.raw == "Updated raw."


def test_import_data_uses_redacted_content_when_raw_is_absent(tmp_path: Path) -> None:
    source = EventStore(tmp_path / "source.db")
    source.add_text("Email me at test@example.com")
    exported = source.export_data()

    target = EventStore(tmp_path / "target.db")
    target.import_data(exported)
    [event] = target.list_events()

    assert event.raw == "Email me at [REDACTED:email]"
    assert event.redacted == "Email me at [REDACTED:email]"


def test_search_finds_public_events_and_active_memories(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    event = store.add_text(
        "MirrorMe should support local search.",
        source_app="Obsidian",
        project="MirrorMe",
        tags=["retrieval"],
    )
    memory = store.add_memory(
        kind="decision",
        content="MirrorMe search should start with local keyword matching.",
        confidence=0.75,
        source_event_ids=[event.id],
    )

    results = store.search("search")

    assert [(result.kind, result.id) for result in results] == [
        ("memory", memory.id),
        ("event", event.id),
    ]


def test_search_respects_private_and_archived_defaults(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    private_event = store.add_text("Secret searchable event", is_private=True)
    archived = store.add_memory(
        kind="preference",
        content="Archived searchable memory",
        confidence=0.4,
        source_event_ids=[],
        status="archived",
    )

    default_results = store.search("searchable")
    expanded_results = store.search(
        "searchable",
        include_private=True,
        include_archived_memories=True,
    )

    assert default_results == []
    assert sorted((result.kind, result.id) for result in expanded_results) == [
        ("event", private_event.id),
        ("memory", archived.id),
    ]


def test_search_matches_project_tags_and_source_app(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    project_event = store.add_text("Generic text", project="MirrorMe")
    tag_event = store.add_text("Generic text", tags=["retrieval"])
    app_event = store.add_text("Generic text", source_app="Obsidian")

    assert [result.id for result in store.search("mirrorme")] == [project_event.id]
    assert [result.id for result in store.search("retrieval")] == [tag_event.id]
    assert [result.id for result in store.search("obsidian")] == [app_event.id]


def test_stats_summarizes_local_data(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    public_event = store.add_text("Public event", project="MirrorMe", tags=["stage1"])
    store.add_text("Private event", is_private=True, tags=["stage1"])
    store.save_daily_summary(public_event.created_at[:10])
    store.add_memory(
        kind="decision",
        content="Use local-first storage.",
        confidence=0.9,
        source_event_ids=[public_event.id],
    )
    store.add_memory(
        kind="preference",
        content="Archive old ideas.",
        confidence=0.4,
        source_event_ids=[],
        status="archived",
    )

    stats = store.stats()

    assert stats["capture_paused"] is False
    assert stats["events"]["total"] == 2
    assert stats["events"]["public"] == 1
    assert stats["events"]["private"] == 1
    assert stats["events"]["by_date"] == {public_event.created_at[:10]: 2}
    assert stats["events"]["by_project"] == {"MirrorMe": 1}
    assert stats["events"]["by_tag"] == {"stage1": 2}
    assert stats["daily_summaries"]["total"] == 1
    assert stats["memories"]["total"] == 2
    assert stats["memories"]["by_status"] == {"active": 1, "archived": 1}
    assert stats["memories"]["by_kind"] == {"decision": 1, "preference": 1}


def test_timeline_summarizes_date_range(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    first = store.add_text(
        "\u6211\u51b3\u5b9a MirrorMe \u5148\u505a timeline\u3002",
        created_at="2026-06-25T09:00:00+08:00",
        project="MirrorMe",
        tags=["stage1"],
    )
    store.add_text(
        "Private note.",
        created_at="2026-06-25T10:00:00+08:00",
        is_private=True,
        tags=["private"],
    )
    store.add_text(
        "Second day note.",
        created_at="2026-06-27T10:00:00+08:00",
        project="MirrorMe",
    )
    store.save_daily_summary(first.created_at[:10])

    rows = store.timeline(start="2026-06-25", end="2026-06-27", include_empty=True)

    assert [row["date"] for row in rows] == ["2026-06-25", "2026-06-26", "2026-06-27"]
    assert rows[0]["events"] == 2
    assert rows[0]["public_events"] == 1
    assert rows[0]["private_events"] == 1
    assert rows[0]["projects"] == {"MirrorMe": 1}
    assert rows[0]["tags"] == {"stage1": 1, "private": 1}
    assert rows[0]["saved_summary_versions"] == [1]
    assert rows[0]["pending_memory_candidates"] == 1
    assert rows[1]["events"] == 0
    assert rows[2]["events"] == 1


def test_timeline_omits_empty_days_by_default(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    store.add_text("First.", created_at="2026-06-25T09:00:00+08:00")
    store.add_text("Second.", created_at="2026-06-27T09:00:00+08:00")

    rows = store.timeline(start="2026-06-25", end="2026-06-27")

    assert [row["date"] for row in rows] == ["2026-06-25", "2026-06-27"]


def test_projects_summarizes_project_activity(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    first = store.add_text(
        "\u6211\u51b3\u5b9a MirrorMe \u5148\u505a projects index\u3002",
        created_at="2026-06-25T09:00:00+08:00",
        project="MirrorMe",
        tags=["stage1"],
    )
    store.add_text(
        "Second MirrorMe event.",
        created_at="2026-06-26T09:00:00+08:00",
        project="MirrorMe",
        tags=["stage1", "index"],
    )
    store.add_text(
        "Private MirrorMe event.",
        created_at="2026-06-26T10:00:00+08:00",
        project="MirrorMe",
        is_private=True,
    )
    store.add_text(
        "Other project event.",
        created_at="2026-06-27T09:00:00+08:00",
        project="Other",
    )
    store.save_daily_summary(first.created_at[:10])
    store.accept_candidate(1, date=first.created_at[:10])

    public_rows = store.projects()
    private_rows = store.projects(include_private=True)
    mirror = next(row for row in public_rows if row["project"] == "MirrorMe")
    mirror_with_private = next(row for row in private_rows if row["project"] == "MirrorMe")

    assert [row["project"] for row in public_rows] == ["Other", "MirrorMe"]
    assert mirror["events"] == 2
    assert mirror["public_events"] == 2
    assert mirror["private_events"] == 0
    assert mirror["active_days"] == 2
    assert mirror["tags"] == {"stage1": 2, "index": 1}
    assert mirror["saved_summaries"] == 1
    assert mirror["active_memories"] == 1
    assert mirror["pending_memory_candidates"] == 0
    assert mirror_with_private["events"] == 3
    assert mirror_with_private["private_events"] == 1


def test_tags_summarizes_tag_activity(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    first = store.add_text(
        "\u6211\u51b3\u5b9a MirrorMe \u5148\u505a tags index\u3002",
        created_at="2026-06-25T09:00:00+08:00",
        project="MirrorMe",
        tags=["stage1"],
    )
    store.add_text(
        "Cross-project tag event.",
        created_at="2026-06-26T09:00:00+08:00",
        project="Other",
        tags=["stage1", "index"],
    )
    store.add_text(
        "Private tagged event.",
        created_at="2026-06-27T09:00:00+08:00",
        project="MirrorMe",
        tags=["stage1"],
        is_private=True,
    )
    store.add_text(
        "Untagged event.",
        created_at="2026-06-27T10:00:00+08:00",
        project="MirrorMe",
    )
    store.save_daily_summary(first.created_at[:10])
    store.accept_candidate(1, date=first.created_at[:10])

    public_rows = store.tags()
    private_rows = store.tags(include_private=True)
    stage1 = next(row for row in public_rows if row["tag"] == "stage1")
    stage1_with_private = next(row for row in private_rows if row["tag"] == "stage1")

    assert [row["tag"] for row in public_rows] == ["stage1", "index"]
    assert stage1["events"] == 2
    assert stage1["public_events"] == 2
    assert stage1["private_events"] == 0
    assert stage1["active_days"] == 2
    assert stage1["projects"] == {"MirrorMe": 1, "Other": 1}
    assert stage1["saved_summaries"] == 1
    assert stage1["active_memories"] == 1
    assert stage1["pending_memory_candidates"] == 0
    assert stage1_with_private["events"] == 3
    assert stage1_with_private["private_events"] == 1


def test_doctor_reports_clean_store(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    event = store.add_text("Clean event.", created_at="2026-06-25T10:00:00+08:00")
    store.save_daily_summary(event.created_at[:10])
    store.add_memory(
        kind="preference",
        content="Clean memory.",
        confidence=0.8,
        source_event_ids=[event.id],
    )

    report = store.doctor()

    assert report["ok"] is True
    assert report["issue_count"] == 0
    assert report["counts"]["events"] == 1
    assert report["counts"]["daily_summaries"] == 1
    assert report["counts"]["memories"] == 1


def test_doctor_reports_integrity_issues(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "mirrorme.db")
    private_event = store.add_text(
        "Private event.",
        is_private=True,
        created_at="2026-06-25T10:00:00+08:00",
    )
    with sqlite3.connect(tmp_path / "mirrorme.db") as conn:
        conn.execute(
            """
            insert into memories (
                id, kind, content, confidence, source_event_ids_json,
                created_at, updated_at, status
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "mem_bad",
                "decision",
                "",
                0.4,
                '["evt_missing"]',
                "not-a-date",
                "2026-06-25T10:00:00+08:00",
                "floating",
            ),
        )
        conn.execute(
            """
            insert into daily_summaries (
                id, date, version, generator, summary_json,
                source_event_ids_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "sum_bad",
                "2026-06-25",
                1,
                "test",
                '{"date":"2026-06-26"}',
                f'["{private_event.id}", "evt_missing"]',
                "2026-06-25T10:00:00+08:00",
            ),
        )
        conn.execute(
            """
            insert into memory_reviews (
                candidate_key, status, memory_id, note, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?)
            """,
            ("review_bad", "accepted", "mem_missing", None, "bad-time", "2026-06-25T10:00:00+08:00"),
        )
        conn.execute(
            "update text_events set tags_json = ? where id = ?",
            ("not-json", private_event.id),
        )

    report = store.doctor()
    codes = {issue["code"] for issue in report["issues"]}

    assert report["ok"] is False
    assert report["error_count"] >= 1
    assert "invalid_json" in codes
    assert "invalid_timestamp" in codes
    assert "invalid_status" in codes
    assert "missing_source_event" in codes
    assert "private_event_in_summary" in codes
    assert "summary_date_mismatch" in codes
    assert "missing_review_memory" in codes
    assert "blank_content" in codes
