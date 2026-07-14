import pytest
import sys

from mirrorme.ime_sidecar import (
    NativeRimeSidecar,
    SidecarError,
    StubRimeSidecar,
    commit,
    compose,
    parse_sidecar_command,
    schema_info,
    sidecar_for_env,
    verify_sidecar,
)


def test_stub_sidecar_composes_known_pinyin() -> None:
    result = compose("ni hao")

    assert result["schema"] == "luna_pinyin"
    assert result["input"] == "ni hao"
    assert result["preedit"] == "ni hao"
    assert [candidate["text"] for candidate in result["candidates"][:2]] == ["你好", "你 好"]
    assert result["committed"] is None


def test_stub_sidecar_commits_candidate() -> None:
    result = commit("zhong wen", candidate_index=1)

    assert result["committed"] == "中文"
    assert result["preedit"] == ""
    assert result["candidates"][0]["text"] == "中文"


def test_stub_sidecar_composes_known_chunks_into_usable_phrase() -> None:
    result = commit("wo jue de mirrorme xian zuo shu ju fen xi", candidate_index=1)

    assert result["committed"] == "我觉得MirrorMe先做数据分析"
    assert result["candidates"][1]["text"] == "我觉得 MirrorMe 先做 数据 分析"


def test_stub_sidecar_rejects_out_of_range_candidate() -> None:
    with pytest.raises(ValueError, match="candidate_index"):
        commit("ni hao", candidate_index=99)


def test_stub_sidecar_schema_and_clear() -> None:
    sidecar = StubRimeSidecar()

    assert schema_info()["engine"] == "stub-rime-sidecar"
    assert sidecar.clear() == {
        "schema": "luna_pinyin",
        "input": "",
        "preedit": "",
        "candidates": [],
        "committed": None,
    }


def test_verify_sidecar_reports_stub_smoke_test() -> None:
    report = verify_sidecar("ni hao", env={})

    assert report["ok"] is True
    assert report["native"] is False
    assert report["native_required"] is False
    assert report["schema"]["engine"] == "stub-rime-sidecar"
    assert report["composition"]["candidates"][0]["text"] == "你好"
    assert report["commit"]["committed"] == "你好"


def test_verify_sidecar_can_require_a_native_engine() -> None:
    with pytest.raises(SidecarError, match="native=false"):
        verify_sidecar("ni hao", env={}, require_native=True)


def test_sidecar_for_env_falls_back_to_stub_when_native_is_not_ready() -> None:
    sidecar = sidecar_for_env({})

    assert isinstance(sidecar, StubRimeSidecar)


def test_sidecar_for_env_uses_command_configuration(tmp_path) -> None:
    script = tmp_path / "fake_command_sidecar.py"
    script.write_text(
        """
import json
import sys

request = json.loads(sys.stdin.read())
print(json.dumps({"result": {"schema": "luna_pinyin", "input": "cmd", "preedit": "cmd", "candidates": [], "committed": None}}))
""".strip(),
        encoding="utf-8",
    )
    sidecar = sidecar_for_env({"MIRRORME_RIME_COMMAND": f"{sys.executable} {script}"})

    assert isinstance(sidecar, NativeRimeSidecar)
    assert sidecar.compose("ni hao")["input"] == "cmd"


def test_parse_sidecar_command_handles_quoted_paths() -> None:
    assert parse_sidecar_command('"C:\\Tools\\Rime Sidecar\\sidecar.exe" --stdio') == [
        "C:\\Tools\\Rime Sidecar\\sidecar.exe",
        "--stdio",
    ]


def test_native_sidecar_uses_json_stdio_protocol(tmp_path) -> None:
    script = tmp_path / "fake_sidecar.py"
    script.write_text(
        """
import json
import sys

request = json.loads(sys.stdin.read())
method = request["method"]
params = request.get("params", {})
if method == "compose":
    result = {
        "schema": params.get("schema", "luna_pinyin"),
        "input": params["text"],
        "preedit": params["text"],
        "candidates": [{"index": 1, "text": "原生候选", "annotation": "native", "confidence": 0.99}],
        "committed": None,
    }
elif method == "commit":
    result = {
        "schema": params.get("schema", "luna_pinyin"),
        "input": params["text"],
        "preedit": "",
        "candidates": [{"index": 1, "text": "原生候选", "annotation": "native", "confidence": 0.99}],
        "committed": "原生候选",
    }
elif method == "schema":
    result = {"id": params.get("schema", "luna_pinyin"), "engine": "fake-native", "native": True}
else:
    result = {"error": "unsupported"}
print(json.dumps({"result": result}, ensure_ascii=False))
""".strip(),
        encoding="utf-8",
    )
    sidecar = NativeRimeSidecar([sys.executable, str(script)])

    composition = sidecar.compose("ni hao")
    committed = sidecar.commit("ni hao")
    schema = sidecar.schema_info()

    assert composition["candidates"][0]["text"] == "原生候选"
    assert committed["committed"] == "原生候选"
    assert schema["engine"] == "fake-native"

    report = verify_sidecar("ni hao", env={"MIRRORME_RIME_COMMAND": f"{sys.executable} {script}"}, require_native=True)
    assert report["native"] is True
    assert report["native_required"] is True


def test_native_sidecar_reports_invalid_json(tmp_path) -> None:
    script = tmp_path / "bad_sidecar.py"
    script.write_text("print('not-json')", encoding="utf-8")
    sidecar = NativeRimeSidecar([sys.executable, str(script)])

    with pytest.raises(SidecarError, match="invalid JSON"):
        sidecar.compose("ni hao")
