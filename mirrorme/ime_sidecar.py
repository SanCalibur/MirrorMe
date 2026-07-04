from __future__ import annotations

import json
import os
import shlex
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from .ime import probe_native_adapter


DEFAULT_SCHEMA = "luna_pinyin"
DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class ImeCandidate:
    index: int
    text: str
    annotation: str
    confidence: float


@dataclass(frozen=True)
class ImeComposition:
    schema: str
    input: str
    preedit: str
    candidates: list[ImeCandidate]
    committed: str | None


class SidecarError(RuntimeError):
    """Raised when a native sidecar request fails."""


class StubRimeSidecar:
    """Deterministic sidecar stub that preserves the future librime API shape."""

    def __init__(self, *, schema: str = DEFAULT_SCHEMA) -> None:
        self.schema = schema

    def schema_info(self) -> dict[str, object]:
        return {
            "id": self.schema,
            "name": "Rime Luna Pinyin",
            "engine": "stub-rime-sidecar",
            "native": False,
        }

    def compose(self, text: str) -> dict[str, object]:
        normalized = _normalize_input(text)
        composition = ImeComposition(
            schema=self.schema,
            input=normalized,
            preedit=normalized,
            candidates=_candidate_list(normalized),
            committed=None,
        )
        return _composition_to_dict(composition)

    def candidates(self, text: str) -> list[dict[str, object]]:
        return [asdict(candidate) for candidate in _candidate_list(_normalize_input(text))]

    def commit(self, text: str, *, candidate_index: int = 1) -> dict[str, object]:
        normalized = _normalize_input(text)
        candidates = _candidate_list(normalized)
        if candidate_index < 1 or candidate_index > len(candidates):
            raise ValueError("candidate_index is out of range.")
        committed = candidates[candidate_index - 1].text
        composition = ImeComposition(
            schema=self.schema,
            input=normalized,
            preedit="",
            candidates=candidates,
            committed=committed,
        )
        return _composition_to_dict(composition)

    def clear(self) -> dict[str, object]:
        return _composition_to_dict(
            ImeComposition(
                schema=self.schema,
                input="",
                preedit="",
                candidates=[],
                committed=None,
            )
        )


class NativeRimeSidecar:
    def __init__(
        self,
        command: Sequence[str],
        *,
        schema: str = DEFAULT_SCHEMA,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.command = list(command)
        self.schema = schema
        self.timeout_seconds = timeout_seconds

    def schema_info(self) -> dict[str, object]:
        return self._request("schema", {"schema": self.schema})

    def compose(self, text: str) -> dict[str, object]:
        return self._request("compose", {"text": text, "schema": self.schema})

    def candidates(self, text: str) -> list[dict[str, object]]:
        payload = self._request("candidates", {"text": text, "schema": self.schema})
        candidates = payload.get("candidates", payload)
        if not isinstance(candidates, list):
            raise SidecarError("Native sidecar returned invalid candidates payload.")
        return [dict(candidate) for candidate in candidates]

    def commit(self, text: str, *, candidate_index: int = 1) -> dict[str, object]:
        return self._request(
            "commit",
            {
                "text": text,
                "candidate_index": candidate_index,
                "schema": self.schema,
            },
        )

    def clear(self) -> dict[str, object]:
        return self._request("clear", {"schema": self.schema})

    def _request(self, method: str, params: dict[str, object]) -> dict[str, object]:
        request = json.dumps({"method": method, "params": params}, ensure_ascii=False) + "\n"
        try:
            completed = subprocess.run(
                self.command,
                input=request,
                capture_output=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                timeout=self.timeout_seconds,
                check=False,
            )
        except OSError as exc:
            raise SidecarError(f"Failed to start native sidecar: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise SidecarError("Native sidecar timed out.") from exc

        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise SidecarError(f"Native sidecar exited with {completed.returncode}: {detail}")
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise SidecarError("Native sidecar returned invalid JSON.") from exc
        if not isinstance(response, dict):
            raise SidecarError("Native sidecar returned a non-object response.")
        if response.get("error"):
            raise SidecarError(str(response["error"]))
        result = response.get("result", response)
        if not isinstance(result, dict):
            raise SidecarError("Native sidecar result should be an object.")
        return result


def sidecar_for_env(
    env: Mapping[str, str] | None = None,
    *,
    schema: str = DEFAULT_SCHEMA,
) -> StubRimeSidecar | NativeRimeSidecar:
    env = env or os.environ
    probe = probe_native_adapter(env)
    if probe["ready"] and probe.get("command"):
        return NativeRimeSidecar(parse_sidecar_command(str(probe["command"])), schema=schema)
    if probe["ready"] and probe.get("binary_path"):
        return NativeRimeSidecar([str(Path(str(probe["binary_path"])))], schema=schema)
    return StubRimeSidecar(schema=schema)


def compose(
    text: str,
    *,
    schema: str = DEFAULT_SCHEMA,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    return sidecar_for_env(env, schema=schema).compose(text)


def commit(
    text: str,
    *,
    candidate_index: int = 1,
    schema: str = DEFAULT_SCHEMA,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    return sidecar_for_env(env, schema=schema).commit(text, candidate_index=candidate_index)


def schema_info(
    schema: str = DEFAULT_SCHEMA,
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    return sidecar_for_env(env, schema=schema).schema_info()


def parse_sidecar_command(command: str) -> list[str]:
    parts = [part.strip('"') for part in shlex.split(command, posix=False)]
    if not parts:
        raise SidecarError("Native sidecar command is empty.")
    return parts


def _normalize_input(text: str) -> str:
    return " ".join(text.strip().casefold().split())


def _candidate_list(text: str) -> list[ImeCandidate]:
    if not text:
        return []
    dictionary = {
        "ni": ["你", "尼", "呢"],
        "hao": ["好", "号", "浩"],
        "ni hao": ["你好", "你 好", "倪浩"],
        "wo": ["我", "握", "窝"],
        "shi": ["是", "时", "事"],
        "zhong": ["中", "种", "重"],
        "wen": ["文", "问", "闻"],
        "zhong wen": ["中文", "中文输入", "中文文档"],
        "shu ru": ["输入", "输入法", "录入"],
        "shu ru fa": ["输入法", "输入 法", "书入法"],
        "mirrorme": ["MirrorMe"],
    }
    texts = dictionary.get(text, [text])
    return [
        ImeCandidate(
            index=index + 1,
            text=value,
            annotation=f"{text}#{index + 1}",
            confidence=max(0.35, 0.9 - index * 0.12),
        )
        for index, value in enumerate(texts[:5])
    ]


def _composition_to_dict(composition: ImeComposition) -> dict[str, object]:
    return {
        "schema": composition.schema,
        "input": composition.input,
        "preedit": composition.preedit,
        "candidates": [asdict(candidate) for candidate in composition.candidates],
        "committed": composition.committed,
    }
