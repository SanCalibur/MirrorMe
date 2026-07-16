from __future__ import annotations

import re
from collections import Counter
from typing import Protocol

from .composition import compose_events, source_event_ids

class SummaryEvent(Protocol):
    id: str
    redacted: str
    project: str | None
    tags: list[str]


DECISION_MARKERS = ("决定", "确定", "选择", "先做", "不做", "改成", "采用", "放弃")
COMMITMENT_MARKERS = ("我会", "我要", "需要", "计划", "明天", "下周", "待办", "TODO", "todo")
PREFERENCE_MARKERS = ("我喜欢", "我不喜欢", "我更倾向", "我倾向", "我希望", "我想", "我觉得")
QUESTION_MARKERS = ("?", "？")

STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "today",
    "about",
    "should",
    "would",
}


def build_daily_summary(date: str, events: list[SummaryEvent]) -> dict[str, object]:
    composed_events = compose_events(events)
    public_snippets = [event.redacted.strip() for event in composed_events if event.redacted.strip()]
    source_ids = [event.id for event in events]
    decisions = _matching_sentences(public_snippets, DECISION_MARKERS)
    commitments = _matching_sentences(public_snippets, COMMITMENT_MARKERS)
    open_questions = _matching_sentences(public_snippets, QUESTION_MARKERS)

    return {
        "date": date,
        "event_count": len(events),
        "summary": _overview(public_snippets),
        "topics": _topics(composed_events, public_snippets),
        "decisions": decisions,
        "commitments": commitments,
        "people": _people(public_snippets),
        "open_questions": open_questions,
        "memory_candidates": _memory_candidates(composed_events),
        "source_event_ids": source_ids,
    }


def _overview(snippets: list[str]) -> str:
    if not snippets:
        return "No public text output captured for this date."

    joined = " ".join(snippets)
    if len(joined) <= 220:
        return joined
    return joined[:217].rstrip() + "..."


def _topics(events: list[SummaryEvent], snippets: list[str]) -> list[str]:
    topics: Counter[str] = Counter()
    for event in events:
        if event.project:
            topics[event.project.strip()] += 3
        for tag in event.tags:
            if tag.strip():
                topics[tag.strip()] += 2

    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", " ".join(snippets))
    topics.update(word.lower() for word in words if word.lower() not in STOP_WORDS)
    return [topic for topic, _ in topics.most_common(8)]


def _matching_sentences(snippets: list[str], markers: tuple[str, ...]) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    for snippet in snippets:
        for sentence in _split_sentences(snippet):
            if any(marker in sentence for marker in markers):
                matches.append({"content": sentence})
                break
    return matches


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?；;])\s*", text)
    return [part.strip() for part in parts if part.strip()]


def _people(snippets: list[str]) -> list[str]:
    people: set[str] = set()
    text = " ".join(snippets)
    people.update(re.findall(r"@([A-Za-z0-9_\-\u4e00-\u9fff]{2,24})", text))
    people.update(re.findall(r"(?:和|给|问|找)([\u4e00-\u9fff]{2,4})(?:说|聊|确认|讨论|发)", text))
    return sorted(people)


def _memory_candidates(events: list[SummaryEvent]) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for event in events:
        for sentence in _split_sentences(event.redacted):
            if any(marker in sentence for marker in PREFERENCE_MARKERS):
                candidates.append(
                    {
                        "kind": "preference",
                        "content": sentence,
                        "confidence": 0.55,
                        "evidence_event_ids": source_event_ids(event),
                    }
                )
                break
            if any(marker in sentence for marker in DECISION_MARKERS):
                candidates.append(
                    {
                        "kind": "decision",
                        "content": sentence,
                        "confidence": 0.62,
                        "evidence_event_ids": source_event_ids(event),
                    }
                )
                break
    return candidates
