import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

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
    assert "每日输出工作台" in body
    assert "imeReadiness" in body
    assert "/app.js" in body


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
