from mirrorme.observation_quality import apply_quality_gate, assess_observation_input


def test_short_text_is_not_eligible_for_llm_observation() -> None:
    quality = assess_observation_input("很短的文本", 1)

    assert quality["status"] == "insufficient"
    assert quality["can_observe"] is False
    assert quality["confidence_cap"] == 0.0


def test_limited_input_caps_llm_confidence_and_marks_quality() -> None:
    quality = assess_observation_input("足够长" * 45, 1)
    observation = apply_quality_gate({"data_quality": "sufficient", "confidence": 0.9}, quality)

    assert quality["status"] == "limited"
    assert observation["data_quality"] == "limited"
    assert observation["confidence"] == 0.55


def test_rich_input_is_sufficient_and_still_has_a_confidence_cap() -> None:
    quality = assess_observation_input("完整输入" * 80, 4)
    observation = apply_quality_gate({"data_quality": "sufficient", "confidence": 0.95}, quality)

    assert quality["status"] == "sufficient"
    assert observation["confidence"] == 0.85
