import json
from pathlib import Path
from unittest.mock import patch

from mirrorme.ime_bridge import drain_system_ime_queue
from mirrorme.store import EventStore


def test_drain_system_ime_queue_stores_only_valid_commits(tmp_path: Path) -> None:
    queue = tmp_path / "mirrorme-ime-commits.ndjson"
    queue.write_text(
        "\n".join(
            [
                json.dumps({"version": 1, "text": "MirrorMe system input"}),
                "not-json",
                json.dumps({"version": 1, "text": "   "}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    store = EventStore(tmp_path / "mirrorme.db")

    result = drain_system_ime_queue(store, queue_path=queue)

    [event] = store.list_events()
    assert result == {"captured": 1, "discarded": 2, "paused": 0}
    assert event.raw == "MirrorMe system input"
    assert event.source_method == "system_ime_commit"
    assert event.source_app == "MirrorMe Pinyin (Weasel)"
    assert event.tags == ["ime", "committed", "system"]
    assert not queue.exists()


def test_drain_uses_the_input_method_commit_timestamp(tmp_path: Path) -> None:
    queue = tmp_path / "mirrorme-ime-commits.ndjson"
    queue.write_text(
        json.dumps({"version": 1, "created_at": "2026-07-16T21:25:38+0800", "text": "Timed commit"}) + "\n",
        encoding="utf-8",
    )
    store = EventStore(tmp_path / "mirrorme.db")

    drain_system_ime_queue(store, queue_path=queue)

    assert store.list_events()[0].created_at == "2026-07-16T21:25:38+08:00"


def test_drain_system_ime_queue_discards_commits_while_capture_is_paused(tmp_path: Path) -> None:
    queue = tmp_path / "mirrorme-ime-commits.ndjson"
    queue.write_text(json.dumps({"version": 1, "text": "Do not retain this"}) + "\n", encoding="utf-8")
    store = EventStore(tmp_path / "mirrorme.db")
    store.pause_capture()

    result = drain_system_ime_queue(store, queue_path=queue)

    assert result == {"captured": 0, "discarded": 0, "paused": 1}
    assert store.list_events() == []


def test_drain_system_ime_queue_accepts_a_utf8_bom_on_the_first_line(tmp_path: Path) -> None:
    queue = tmp_path / "mirrorme-ime-commits.ndjson"
    queue.write_text("\ufeff" + json.dumps({"version": 1, "text": "BOM-safe commit"}) + "\n", encoding="utf-8")
    store = EventStore(tmp_path / "mirrorme.db")

    assert drain_system_ime_queue(store, queue_path=queue) == {"captured": 1, "discarded": 0, "paused": 0}


def test_drain_skips_a_batch_that_is_already_being_processed(tmp_path: Path) -> None:
    queue = tmp_path / "mirrorme-ime-commits.ndjson"
    processing = queue.with_suffix(queue.suffix + ".processing")
    processing.write_text(json.dumps({"version": 1, "text": "Duplicate batch"}) + "\n", encoding="utf-8")
    store = EventStore(tmp_path / "mirrorme.db")

    assert drain_system_ime_queue(store, queue_path=queue) == {"captured": 0, "discarded": 0, "paused": 0}
    assert store.list_events() == []


def test_drain_leaves_a_locked_queue_for_a_later_request(tmp_path: Path) -> None:
    queue = tmp_path / "mirrorme-ime-commits.ndjson"
    queue.write_text(json.dumps({"version": 1, "text": "Locked commit"}) + "\n", encoding="utf-8")
    store = EventStore(tmp_path / "mirrorme.db")

    with patch.object(Path, "replace", side_effect=PermissionError):
        assert drain_system_ime_queue(store, queue_path=queue) == {"captured": 0, "discarded": 0, "paused": 0}

    assert queue.exists()
    assert store.list_events() == []
