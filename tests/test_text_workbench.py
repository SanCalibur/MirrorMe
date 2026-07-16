import pytest

from mirrorme.text_workbench import parse_replacements, process_text


def test_process_text_normalizes_replaces_and_evaluates() -> None:
    result = process_text("  我们  要做测试。我们  要做测试。 ", replacements="测试 => 验证")

    assert result["output"] == "我们要做验证。"
    assert "已替换“测试” 2 次" in result["changes"]
    assert [metric["key"] for metric in result["evaluation"]["metrics"]] == [
        "expression_accuracy",
        "organization",
        "mood",
        "stress",
        "energy",
        "social",
    ]
    assert "不是心理或医疗诊断" in result["evaluation"]["disclaimer"]


def test_process_text_surfaces_mood_and_stress_as_text_signals() -> None:
    result = process_text("我很焦虑，截止时间快到了，事情太多。")
    metrics = {item["key"]: item for item in result["evaluation"]["metrics"]}

    assert metrics["mood"]["score"] < 50
    assert metrics["stress"]["score"] > 0


def test_parse_replacements_rejects_ambiguous_rule() -> None:
    with pytest.raises(ValueError, match="=>"):
        parse_replacements("wrong rule")
