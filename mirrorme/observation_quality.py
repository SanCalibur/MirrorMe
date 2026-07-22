from __future__ import annotations

import re


MINIMUM_CHARACTERS = 80
SUFFICIENT_CHARACTERS = 200
SUFFICIENT_SOURCE_EVENTS = 3


def assess_observation_input(text: str, source_event_count: int) -> dict[str, object]:
    character_count = len(re.sub(r"\s+", "", text))
    reasons: list[str] = []
    if character_count < MINIMUM_CHARACTERS:
        reasons.append(f"清洗文本少于 {MINIMUM_CHARACTERS} 个有效字符")
    if source_event_count < SUFFICIENT_SOURCE_EVENTS:
        reasons.append(f"来源事件少于 {SUFFICIENT_SOURCE_EVENTS} 条")

    if character_count < MINIMUM_CHARACTERS:
        return {
            "status": "insufficient",
            "can_observe": False,
            "character_count": character_count,
            "source_event_count": source_event_count,
            "confidence_cap": 0.0,
            "reasons": reasons,
        }

    if character_count < SUFFICIENT_CHARACTERS or source_event_count < SUFFICIENT_SOURCE_EVENTS:
        return {
            "status": "limited",
            "can_observe": True,
            "character_count": character_count,
            "source_event_count": source_event_count,
            "confidence_cap": 0.55,
            "reasons": reasons,
        }

    return {
        "status": "sufficient",
        "can_observe": True,
        "character_count": character_count,
        "source_event_count": source_event_count,
        "confidence_cap": 0.85,
        "reasons": [],
    }


def apply_quality_gate(observation: dict[str, object], quality: dict[str, object]) -> dict[str, object]:
    gated = {**observation, "quality": quality}
    if quality["status"] == "limited":
        gated["data_quality"] = "limited"
    confidence = float(observation.get("confidence", 0.0))
    gated["confidence"] = round(min(confidence, float(quality["confidence_cap"])), 2)
    return gated
