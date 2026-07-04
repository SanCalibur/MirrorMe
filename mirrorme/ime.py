from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from collections.abc import Mapping


ADAPTER_VERSION = 1
SELECTED_ENGINE_ID = "rime-librime"
RIME_BINARY_ENV = "MIRRORME_RIME_BINARY"
RIME_COMMAND_ENV = "MIRRORME_RIME_COMMAND"
RIME_DATA_DIR_ENV = "MIRRORME_RIME_DATA_DIR"


@dataclass(frozen=True)
class InputMethodEngine:
    id: str
    name: str
    role: str
    license: str
    source_url: str
    commercial_fit: str
    embedding_status: str
    recommended: bool
    notes: list[str]


@dataclass(frozen=True)
class InputMethodStatus:
    adapter_version: int
    selected_engine_id: str
    selected_engine: InputMethodEngine
    native_adapter: dict[str, object]
    capture_policy: dict[str, object]
    integration_steps: list[str]
    engines: list[InputMethodEngine]


def list_engines() -> list[InputMethodEngine]:
    return [
        InputMethodEngine(
            id="rime-librime",
            name="librime",
            role="Cross-platform input method engine",
            license="BSD-3-Clause",
            source_url="https://github.com/rime/librime",
            commercial_fit="strong",
            embedding_status="selected_for_native_prototype",
            recommended=True,
            notes=[
                "Preferred engine candidate for a commercial-friendly built-in IME layer.",
                "Use as a native sidecar or dynamic library behind MirrorMe's IME adapter.",
                "Dictionary and schema licenses must be reviewed separately from the engine.",
            ],
        ),
        InputMethodEngine(
            id="rime-weasel",
            name="Weasel",
            role="Windows Rime frontend",
            license="GPL-3.0",
            source_url="https://github.com/rime/weasel",
            commercial_fit="weak_for_direct_bundling",
            embedding_status="reference_or_external_integration",
            recommended=False,
            notes=[
                "Useful Windows reference implementation.",
                "Do not bundle directly unless the product distribution can comply with GPLv3.",
            ],
        ),
        InputMethodEngine(
            id="fcitx5",
            name="Fcitx 5",
            role="Linux/BSD input method framework",
            license="LGPL-2.1+",
            source_url="https://github.com/fcitx/fcitx5",
            commercial_fit="medium",
            embedding_status="platform_option",
            recommended=False,
            notes=[
                "Good option for Linux ecosystem integration.",
                "Less direct fit for a Windows-first local MirrorMe app.",
            ],
        ),
        InputMethodEngine(
            id="libpinyin",
            name="libpinyin",
            role="Pinyin algorithm library",
            license="GPL-3.0",
            source_url="https://github.com/libpinyin/libpinyin",
            commercial_fit="weak_for_direct_bundling",
            embedding_status="reference_only",
            recommended=False,
            notes=[
                "Useful algorithm reference.",
                "GPL-3.0 is not ideal for direct embedding in a commercial/proprietary app.",
            ],
        ),
    ]


def recommended_engine() -> InputMethodEngine:
    for engine in list_engines():
        if engine.recommended:
            return engine
    raise RuntimeError("No recommended input method engine is configured.")


def probe_native_adapter(env: Mapping[str, str] | None = None) -> dict[str, object]:
    env = env or os.environ
    command_value = env.get(RIME_COMMAND_ENV, "")
    binary_value = env.get(RIME_BINARY_ENV, "")
    data_dir_value = env.get(RIME_DATA_DIR_ENV, "")
    binary_path = Path(binary_value) if binary_value else None
    data_dir = Path(data_dir_value) if data_dir_value else None
    command_configured = bool(command_value.strip())
    binary_exists = bool(binary_path and binary_path.is_file())
    data_dir_exists = bool(data_dir and data_dir.is_dir())
    configured = command_configured or bool(binary_path)
    binary_ready = binary_exists and (data_dir is None or data_dir_exists)
    ready = command_configured or binary_ready

    if ready:
        readiness = "ready"
    elif configured:
        readiness = "configured_but_missing_files"
    else:
        readiness = "not_configured"

    return {
        "engine_id": SELECTED_ENGINE_ID,
        "readiness": readiness,
        "configured": configured,
        "ready": ready,
        "command_env": RIME_COMMAND_ENV,
        "command": command_value or None,
        "command_configured": command_configured,
        "binary_env": RIME_BINARY_ENV,
        "binary_path": str(binary_path) if binary_path else None,
        "binary_exists": binary_exists,
        "data_dir_env": RIME_DATA_DIR_ENV,
        "data_dir": str(data_dir) if data_dir else None,
        "data_dir_exists": data_dir_exists,
        "sidecar_protocol": {
            "process": "native_librime_sidecar",
            "transport": "json_stdio",
            "required_methods": ["compose", "candidates", "commit", "clear", "schema"],
            "request_shape": {"method": "compose", "params": {"text": "ni hao", "schema": "luna_pinyin"}},
            "response_shape": {"result": {"preedit": "ni hao", "candidates": []}},
        },
    }


def input_method_status(env: Mapping[str, str] | None = None) -> dict[str, object]:
    selected = recommended_engine()
    status = InputMethodStatus(
        adapter_version=ADAPTER_VERSION,
        selected_engine_id=selected.id,
        selected_engine=selected,
        native_adapter=probe_native_adapter(env),
        capture_policy={
            "capture_committed_text_only": True,
            "capture_raw_keystrokes": False,
            "capture_composition_drafts": False,
            "respect_capture_pause": True,
            "password_field_exclusion_required": True,
        },
        integration_steps=[
            "Package upstream license notices and engine metadata.",
            "Build or download a verified librime binary for the target platform.",
            "Expose a native sidecar API for composition, candidates, commit, and schema switching.",
            "Connect committed text events to MirrorMe capture with pause and privacy controls.",
            "Run a release license audit before shipping binaries.",
        ],
        engines=list_engines(),
    )
    return {
        "adapter_version": status.adapter_version,
        "selected_engine_id": status.selected_engine_id,
        "selected_engine": asdict(status.selected_engine),
        "native_adapter": status.native_adapter,
        "capture_policy": status.capture_policy,
        "integration_steps": status.integration_steps,
        "engines": [asdict(engine) for engine in status.engines],
    }
