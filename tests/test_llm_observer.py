import json
from unittest.mock import patch

import pytest

from mirrorme.llm_observer import LlmObservationError, observe_text_with_llm


def _response() -> dict[str, object]:
    return {
        "summary": "文本表达了推进事项时的压力与行动取向。",
        "data_quality": "sufficient",
        "confidence": 0.74,
        "metrics": [
            {"key": "expression_clarity", "score": 70, "detail": "表达有明确任务对象。", "evidence": ["先完成最小下一步"]},
            {"key": "thought_organization", "score": 65, "detail": "有因果和行动衔接。", "evidence": ["但我决定先完成"]},
            {"key": "affect_tone", "score": 42, "detail": "出现焦虑表达。", "evidence": ["我很焦虑"]},
            {"key": "pressure_load", "score": 76, "detail": "截止时间带来压力。", "evidence": ["截止时间快到了"]},
            {"key": "action_orientation", "score": 82, "detail": "有明确下一步。", "evidence": ["完成最小下一步"]},
            {"key": "social_orientation", "score": 10, "detail": "较少涉及互动。", "evidence": []},
        ],
        "observations": ["单日文本出现压力线索，但同时包含具体行动。"],
    }


def test_observer_normalizes_a_valid_structured_llm_response() -> None:
    with patch("mirrorme.llm_observer.request_llm_completion", return_value=json.dumps(_response(), ensure_ascii=False)):
        observation = observe_text_with_llm(text="我很焦虑，截止时间快到了，但我决定先完成最小下一步。", api_url="https://example.test", api_key="key", model="model")

    assert observation["method"] == "llm"
    assert observation["metrics"][3]["key"] == "pressure_load"
    assert observation["metrics"][3]["evidence"] == ["截止时间快到了"]


def test_observer_rejects_a_response_without_all_fixed_dimensions() -> None:
    invalid = _response()
    invalid["metrics"] = invalid["metrics"][:-1]
    with patch("mirrorme.llm_observer.request_llm_completion", return_value=json.dumps(invalid, ensure_ascii=False)):
        with pytest.raises(LlmObservationError, match="六个固定观察维度"):
            observe_text_with_llm(text="文本", api_url="https://example.test", api_key="key", model="model")
