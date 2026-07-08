from pathlib import Path

from mirrorme.ime import input_method_status, list_engines, probe_native_adapter, recommended_engine


def test_recommended_input_method_engine_is_librime() -> None:
    engine = recommended_engine()

    assert engine.id == "rime-librime"
    assert engine.license == "BSD-3-Clause"
    assert engine.commercial_fit == "strong"
    assert engine.recommended is True


def test_input_method_status_exposes_capture_policy() -> None:
    status = input_method_status({})

    assert status["selected_engine_id"] == "rime-librime"
    assert status["native_adapter"]["readiness"] == "not_configured"
    assert status["capture_policy"]["capture_committed_text_only"] is True
    assert status["capture_policy"]["capture_raw_keystrokes"] is False
    assert status["capture_policy"]["capture_composition_drafts"] is False
    assert status["capture_policy"]["password_field_exclusion_required"] is True
    assert len(status["integration_steps"]) >= 3


def test_input_method_candidate_list_marks_only_one_recommendation() -> None:
    engines = list_engines()

    assert [engine.id for engine in engines if engine.recommended] == ["rime-librime"]
    assert {engine.id for engine in engines} >= {"rime-librime", "rime-weasel", "fcitx5", "libpinyin"}


def test_probe_native_adapter_reports_missing_configuration() -> None:
    status = probe_native_adapter({})

    assert status["readiness"] == "not_configured"
    assert status["configured"] is False
    assert status["ready"] is False
    assert status["shared_data_dir_env"] == "MIRRORME_RIME_SHARED_DATA_DIR"
    assert status["user_data_dir_env"] == "MIRRORME_RIME_USER_DATA_DIR"


def test_probe_native_adapter_reports_ready_configuration(tmp_path: Path) -> None:
    binary = tmp_path / "librime-sidecar.exe"
    data_dir = tmp_path / "rime-data"
    binary.write_text("placeholder", encoding="utf-8")
    data_dir.mkdir()

    status = probe_native_adapter(
        {
            "MIRRORME_RIME_BINARY": str(binary),
            "MIRRORME_RIME_DATA_DIR": str(data_dir),
            "MIRRORME_RIME_SHARED_DATA_DIR": str(data_dir),
            "MIRRORME_RIME_USER_DATA_DIR": str(data_dir),
        }
    )

    assert status["readiness"] == "ready"
    assert status["ready"] is True
    assert status["binary_exists"] is True
    assert status["data_dir_exists"] is True
    assert status["shared_data_dir_exists"] is True
    assert status["user_data_dir_exists"] is True
    assert status["sidecar_protocol"]["transport"] == "json_stdio"


def test_probe_native_adapter_accepts_command_configuration() -> None:
    status = probe_native_adapter({"MIRRORME_RIME_COMMAND": "python -m mirrorme.cli ime sidecar"})

    assert status["readiness"] == "ready"
    assert status["ready"] is True
    assert status["command_configured"] is True
    assert status["command_env"] == "MIRRORME_RIME_COMMAND"
