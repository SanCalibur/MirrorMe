import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from unittest.mock import patch

from mirrorme.store import EventStore
from mirrorme.web import create_handler


def test_web_api_can_capture_and_read_daily_overview(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(tmp_path / "mirrorme.db"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        created = _post_json(
            f"{base_url}/api/events",
            {
                "text": "我决定 MirrorMe 先做 web dashboard。",
                "project": "MirrorMe",
                "tags": "web,daily",
                "created_at": "2026-06-25T09:00:00+08:00",
            },
        )
        overview = _get_json(f"{base_url}/api/daily?date=2026-06-25")
        events = _get_json(f"{base_url}/api/events?date=2026-06-25")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert created["project"] == "MirrorMe"
    assert created["tags"] == ["web", "daily"]
    assert overview["events"]["total"] == 1
    assert overview["events"]["projects"] == {"MirrorMe": 1}
    assert overview["events"]["tags"] == {"web": 1, "daily": 1}
    assert overview["pending_memory_candidates"][0]["review_status"] == "pending"
    assert events[0]["id"] == created["id"]
    assert "raw" not in events[0]


def test_web_root_serves_frontend(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(tmp_path / "mirrorme.db"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        with urlopen(f"{base_url}/", timeout=5) as response:
            body = response.read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert response.status == 200
    assert '<div id="root"></div>' in body
    assert "/assets/" in body


def test_web_serves_the_separate_state_observatory_page(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(tmp_path / "mirrorme.db"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        with urlopen(f"{base_url}/state", timeout=5) as response:
            body = response.read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert response.status == 200
    assert '<div id="root"></div>' in body
    assert "/assets/" in body


def test_web_serves_the_mvp_showcase_page(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(tmp_path / "mirrorme.db"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        with urlopen(f"{base_url}/showcase", timeout=5) as response:
            body = response.read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert response.status == 200
    assert '<div id="root"></div>' in body


def test_web_api_exposes_input_method_status(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(tmp_path / "mirrorme.db"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        status = _get_json(f"{base_url}/api/ime/status")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert status["selected_engine_id"] == "rime-librime"
    assert status["selected_engine"]["commercial_fit"] == "strong"
    assert status["capture_policy"]["capture_committed_text_only"] is True
    assert status["native_adapter"]["engine_id"] == "rime-librime"
    assert "readiness" in status["native_adapter"]


def test_web_api_exposes_ime_sidecar_protocol(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(tmp_path / "mirrorme.db"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        schema = _get_json(f"{base_url}/api/ime/schema")
        composition = _post_json(f"{base_url}/api/ime/compose", {"text": "ni hao"})
        committed = _post_json(
            f"{base_url}/api/ime/commit",
            {"text": "ni hao", "candidate_index": 1},
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert schema["engine"] == "stub-rime-sidecar"
    assert composition["candidates"][0]["text"] == "你好"
    assert committed["committed"] == "你好"


def test_web_api_can_capture_ime_commit_for_analysis(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(tmp_path / "mirrorme.db"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        captured = _post_json(
            f"{base_url}/api/ime/capture",
            {
                "text": "wo jue de mirrorme xian zuo shu ju fen xi",
                "candidate_index": 1,
                "project": "MirrorMe",
                "tags": "analysis,ime-test",
                "created_at": "2026-06-25T09:00:00+08:00",
            },
        )
        overview = _get_json(f"{base_url}/api/daily?date=2026-06-25")
        events = _get_json(f"{base_url}/api/events?date=2026-06-25")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert captured["composition"]["committed"] == "我觉得MirrorMe先做数据分析"
    assert captured["event"]["source_method"] == "ime_commit"
    assert captured["event"]["tags"] == ["ime", "committed", "analysis", "ime-test"]
    assert captured["analysis"]["source_event_ids"] == [captured["event"]["id"]]
    assert overview["summary"]["source_event_ids"] == [captured["event"]["id"]]
    assert overview["pending_memory_candidates"][0]["kind"] == "preference"
    assert events[0]["id"] == captured["event"]["id"]


def test_web_api_exposes_stage_one_review_controls(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(tmp_path / "mirrorme.db"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        created = _post_json(
            f"{base_url}/api/events",
            {
                "text": "我决定 MirrorMe 今天保存一版摘要。",
                "project": "MirrorMe",
                "created_at": "2026-06-25T09:00:00+08:00",
            },
        )
        paused = _post_json(f"{base_url}/api/capture/pause", {})
        paused_overview = _get_json(f"{base_url}/api/daily?date=2026-06-25")
        resumed = _post_json(f"{base_url}/api/capture/resume", {})
        saved = _post_json(f"{base_url}/api/summary/save", {"date": "2026-06-25"})
        exported = _get_json(f"{base_url}/api/export?date=2026-06-25")
        deleted = _delete_json(f"{base_url}/api/events/{created['id']}")
        after_delete = _get_json(f"{base_url}/api/daily?date=2026-06-25")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert paused == {"capture_paused": True}
    assert paused_overview["capture_paused"] is True
    assert resumed == {"capture_paused": False}
    assert saved["version"] == 1
    assert exported["events"][0]["id"] == created["id"]
    assert "raw" not in exported["events"][0]["content"]
    assert deleted == {"deleted_events": 1}
    assert after_delete["events"]["total"] == 0


def test_frontend_utf8_strings_do_not_regress() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    analysis = (root / "frontend" / "src" / "components" / "analysis-workspace.tsx").read_text(encoding="utf-8")

    assert "数据采集" in source
    assert "把每天的表达" in analysis
    assert "æ¯æ—¥" not in source
    assert "æ¯æ—¥" not in analysis


def test_frontend_provides_default_llm_prompts_for_first_time_settings() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")

    assert "DEFAULT_CLEANING_PROMPT" in source
    assert "DEFAULT_OBSERVATION_PROMPT" in source
    assert 'sessionStorage.getItem("llm_prompt") || DEFAULT_CLEANING_PROMPT' in source
    assert 'sessionStorage.getItem("llm_observation_prompt") || DEFAULT_OBSERVATION_PROMPT' in source


def test_frontend_uses_the_fluid_icon_navigation() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")

    assert "function FluidNavigation" in source
    assert 'id="primary-functions"' in source
    assert "closeOnOutsidePress" in source
    assert "closeOnEscape" in source
    assert "<FluidNavigation path={path} />" in source


def test_frontend_includes_a_self_contained_thirty_day_mvp_showcase() -> None:
    root = Path(__file__).resolve().parents[1]
    app = (root / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    showcase = (root / "frontend" / "src" / "components" / "mvp-showcase.tsx").read_text(encoding="utf-8")

    assert 'href: "/showcase"' in app
    assert 'path === "/showcase"' in app
    assert "Array.from({ length: 30 }" in showcase
    assert "30 天的表达" in showcase
    assert "演示数据为本地生成的产品样本" in showcase


def test_frontend_marks_ime_engine_mode_and_prevents_stale_candidates() -> None:
    root = Path(__file__).resolve().parents[1]
    app = (root / "mirrorme" / "web_static" / "app.js").read_text(encoding="utf-8")
    style = (root / "mirrorme" / "web_static" / "style.css").read_text(encoding="utf-8")

    assert "imeMode" in app
    assert "imeRequestSequence" in app
    assert "nodes.imeMode.dataset.native" in app
    assert ".mode-badge[data-native=\"true\"]" in style


def test_frontend_keeps_llm_key_out_of_persistent_browser_storage() -> None:
    root = Path(__file__).resolve().parents[1]
    app = (root / "mirrorme" / "web_static" / "app.js").read_text(encoding="utf-8")
    index = (root / "mirrorme" / "web_static" / "index.html").read_text(encoding="utf-8")

    assert "/api/text-workbench/llm-clean" in app
    assert "localStorage" not in app
    assert 'autocomplete="off"' in index


def test_frontend_uses_manual_dashboard_refresh() -> None:
    root = Path(__file__).resolve().parents[1]
    app = (root / "mirrorme" / "web_static" / "app.js").read_text(encoding="utf-8")

    assert "setInterval(refresh" not in app
    assert 'refreshButton.addEventListener("click", refresh)' in app


def test_web_api_processes_text_without_persisting_it(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(tmp_path / "mirrorme.db"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        result = _post_json(
            f"{base_url}/api/text-workbench/process",
            {"text": "  我们  要做测试。我们  要做测试。 ", "replacements": "测试 => 验证"},
        )
        events = _get_json(f"{base_url}/api/events")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result["output"] == "我们要做验证。"
    assert result["evaluation"]["metrics"][0]["key"] == "expression_accuracy"
    assert events == []


def test_web_api_saves_and_lists_daily_state_assessments(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(tmp_path / "mirrorme.db"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        event = _post_json(
            f"{base_url}/api/events",
            {"text": "我很焦虑，但决定先完成下一步。", "created_at": "2026-06-25T09:00:00+08:00"},
        )
        saved = _post_json(f"{base_url}/api/state-assessments/daily", {"date": "2026-06-25"})
        records = _get_json(f"{base_url}/api/state-assessments?latest_per_day=1&limit=30")
        records_in_range = _get_json(f"{base_url}/api/state-assessments?latest_per_day=1&start_date=2026-06-25&end_date=2026-06-25")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert saved["source_event_ids"] == [event["id"]]
    assert saved["assessment"]["metrics"][3]["key"] == "stress"
    assert [record["id"] for record in records] == [saved["id"]]
    assert [record["id"] for record in records_in_range] == [saved["id"]]


def test_web_api_saves_llm_observation_from_an_accepted_document(tmp_path: Path) -> None:
    db_path = tmp_path / "mirrorme.db"
    store = EventStore(db_path)
    event = store.add_text("A daily source", created_at="2026-06-25T09:00:00+08:00")
    document = store.save_cleaned_document(date="2026-06-25", content="A daily source", source_event_ids=[event.id], model="cleaner", prompt="clean")
    store.accept_cleaned_document(document.id)
    observation = {"method": "llm", "metrics": [], "summary": "A structured observation", "data_quality": "sufficient", "confidence": 0.8, "model": "observer", "prompt_hash": "hash"}

    with patch("mirrorme.web.observe_text_with_llm", return_value=observation):
        server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(db_path))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            saved = _post_json(f"{base_url}/api/state-assessments/llm", {"document_id": document.id, "api_url": "http://local", "api_key": "key", "model": "observer", "prompt": "focus"})
            records = _get_json(f"{base_url}/api/state-assessments?method=llm&date=2026-06-25")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    assert saved["assessment"]["method"] == "llm"
    assert saved["assessment"]["cleaned_document_id"] == document.id
    assert [record["id"] for record in records] == [saved["id"]]


def test_web_api_batch_processes_public_dates_and_skips_existing_observations(tmp_path: Path) -> None:
    db_path = tmp_path / "mirrorme.db"
    store = EventStore(db_path)
    first = store.add_text("First public day", created_at="2026-06-24T09:00:00+08:00")
    second = store.add_text("Second public day", created_at="2026-06-25T09:00:00+08:00")
    store.add_text("Private day", is_private=True, created_at="2026-06-26T09:00:00+08:00")
    existing = store.save_cleaned_document(date="2026-06-24", content="First public day", source_event_ids=[first.id], model="cleaner", prompt="clean")
    existing = store.accept_cleaned_document(existing.id)
    assert existing is not None
    store.save_llm_state_assessment(existing, {"method": "llm", "metrics": [], "summary": "Existing", "data_quality": "sufficient", "confidence": 0.8, "model": "observer", "prompt_hash": "hash"})
    observation = {"method": "llm", "metrics": [], "summary": "Batch observation", "data_quality": "sufficient", "confidence": 0.8, "model": "observer", "prompt_hash": "hash"}

    with patch("mirrorme.web.clean_text_with_llm", side_effect=lambda **kwargs: kwargs["text"]), patch("mirrorme.web.observe_text_with_llm", return_value=observation):
        server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(db_path))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            result = _post_json(f"{base_url}/api/state-assessments/llm/batch", {"api_url": "http://local", "api_key": "key", "model": "model", "cleaning_prompt": "clean", "prompt": "observe"})
            records = _get_json(f"{base_url}/api/state-assessments?method=llm")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    assert result["skipped"] == ["2026-06-24"]
    assert [item["date"] for item in result["processed"]] == ["2026-06-25"]
    assert result["failed"] == []
    assert {record["date"] for record in records} == {"2026-06-24", "2026-06-25"}
    assert second.id in records[0]["source_event_ids"] or second.id in records[1]["source_event_ids"]


def test_frontend_bounds_and_groups_system_ime_event_cards() -> None:
    root = Path(__file__).resolve().parents[1]
    app = (root / "mirrorme" / "web_static" / "app.js").read_text(encoding="utf-8")

    assert "limit: \"120\"" in app
    assert "composeEventBlocks(events)" in app
    assert "SYSTEM_IME_GROUP_GAP_MS" in app


def test_web_event_api_limits_the_returned_window(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(tmp_path / "mirrorme.db"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        for index in range(3):
            _post_json(f"{base_url}/api/events", {"text": f"event {index}"})
        events = _get_json(f"{base_url}/api/events?limit=2")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert [event["redacted"] for event in events] == ["event 1", "event 2"]


def _get_json(url: str) -> object:
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: object) -> object:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _delete_json(url: str) -> object:
    request = Request(url, method="DELETE")
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))
