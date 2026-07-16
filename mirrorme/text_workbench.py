from __future__ import annotations

import re
from collections import Counter


FILLER_WORDS = ("然后", "就是", "其实", "那个", "这个", "嗯", "呃", "感觉")
ACTION_MARKERS = ("决定", "计划", "需要", "TODO", "待办", "下一步", "负责", "截止", "完成", "推进")
QUESTION_MARKERS = ("?", "？", "请问", "是否", "怎么", "如何")
POSITIVE_MARKERS = ("开心", "高兴", "满意", "喜欢", "顺利", "期待", "有趣", "感谢", "轻松", "不错")
NEGATIVE_MARKERS = ("难受", "焦虑", "烦", "累", "沮丧", "失望", "生气", "担心", "糟糕", "无力")
STRESS_MARKERS = ("压力", "来不及", "赶", "截止", "堆积", "崩溃", "焦虑", "失眠", "疲惫", "太多")
SOCIAL_MARKERS = ("我们", "你们", "他们", "客户", "同事", "朋友", "家人", "沟通", "讨论", "反馈")
SENSITIVE_PATTERNS = {
    "邮箱": re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    "手机号": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "身份证号": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
}


def process_text(text: str, *, replacements: str = "", deduplicate: bool = True) -> dict[str, object]:
    """Create a transient text-cleaning preview and rule-based quality assessment."""
    original = text
    cleaned = _normalize_text(text)
    changes: list[str] = []
    if cleaned != original:
        changes.append("已统一空白、换行和常见中文标点间距")

    for source, target in parse_replacements(replacements):
        occurrences = cleaned.count(source)
        if occurrences:
            cleaned = cleaned.replace(source, target)
            changes.append(f"已替换“{source}” {occurrences} 次")

    if deduplicate:
        deduplicated, removed = _deduplicate_adjacent_sentences(cleaned)
        if removed:
            cleaned = deduplicated
            changes.append(f"已移除 {removed} 段连续重复内容")

    return {
        "input_characters": len(original),
        "output": cleaned,
        "changes": changes,
        "evaluation": evaluate_text(cleaned),
    }


def parse_replacements(value: str) -> list[tuple[str, str]]:
    rules: list[tuple[str, str]] = []
    for number, line in enumerate(value.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if "=>" not in stripped:
            raise ValueError(f"替换规则第 {number} 行必须使用 => 分隔。")
        source, target = (part.strip() for part in stripped.split("=>", maxsplit=1))
        if not source:
            raise ValueError(f"替换规则第 {number} 行缺少原文。")
        rules.append((source, target))
    return rules


def evaluate_text(text: str) -> dict[str, object]:
    stripped = text.strip()
    sentences = [item.strip() for item in re.split(r"(?<=[。！？!?；;])\s*|\n+", stripped) if item.strip()]
    paragraphs = [item for item in re.split(r"\n{2,}", stripped) if item.strip()]
    length = len(stripped)
    average_sentence_length = round(length / len(sentences), 1) if sentences else 0
    filler_count = sum(stripped.count(word) for word in FILLER_WORDS)
    tokens = _tokens(stripped)
    repeated_tokens = sum(count - 1 for count in Counter(tokens).values() if count > 1)
    redundancy_ratio = repeated_tokens / len(tokens) if tokens else 0
    sensitive = {label: len(pattern.findall(stripped)) for label, pattern in SENSITIVE_PATTERNS.items()}
    sensitive = {label: count for label, count in sensitive.items() if count}
    action_count = sum(stripped.count(marker) for marker in ACTION_MARKERS)
    question_count = sum(stripped.count(marker) for marker in QUESTION_MARKERS)
    positive_count = sum(stripped.count(marker) for marker in POSITIVE_MARKERS)
    negative_count = sum(stripped.count(marker) for marker in NEGATIVE_MARKERS)
    stress_count = sum(stripped.count(marker) for marker in STRESS_MARKERS)
    social_count = sum(stripped.count(marker) for marker in SOCIAL_MARKERS)

    expression_accuracy = max(0, min(100, round(100 - max(0, average_sentence_length - 42) * 1.4 - filler_count * 5 - redundancy_ratio * 100)))
    organization = min(100, 45 + min(len(sentences), 5) * 8 + min(len(paragraphs), 3) * 5 + min(action_count, 2) * 7)
    mood_score, mood_detail = _mood_signal(positive_count, negative_count)
    stress_score = min(100, stress_count * 22 + max(0, question_count - action_count) * 8)
    energy_score = min(100, action_count * 18 + positive_count * 8)
    social_score = min(100, social_count * 16)
    return {
        "disclaimer": "这是基于文本关键词和结构的当下线索，不是心理或医疗诊断；短文本的参考价值有限。",
        "metrics": [
            {"key": "expression_accuracy", "label": "表达准确性", "score": expression_accuracy, "detail": f"平均句长 {average_sentence_length} 字，填充词 {filler_count} 个，重复词 {round(redundancy_ratio * 100)}%"},
            {"key": "organization", "label": "思路组织度", "score": organization, "detail": f"{len(paragraphs)} 段，{len(sentences)} 句，行动线索 {action_count} 个"},
            {"key": "mood", "label": "情绪倾向", "score": mood_score, "detail": mood_detail},
            {"key": "stress", "label": "压力信号", "score": stress_score, "detail": "信号较少" if not stress_count else f"检测到 {stress_count} 个压力相关表达"},
            {"key": "energy", "label": "行动能量", "score": energy_score, "detail": f"行动线索 {action_count} 个，积极线索 {positive_count} 个"},
            {"key": "social", "label": "社交关注", "score": social_score, "detail": "较少涉及他人或互动" if not social_count else f"检测到 {social_count} 个关系或互动线索"},
        ],
        "word_count": len(tokens),
        "sentence_count": len(sentences),
        "suggestions": _suggestions(average_sentence_length, filler_count, redundancy_ratio, action_count, sensitive, stress_count, negative_count),
    }


def _normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u3000", " ").replace("\u00a0", " ")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"(?<=[\u4e00-\u9fff]) (?=[\u4e00-\u9fff])", "", normalized)
    normalized = re.sub(r" *([，。！？；：、]) *", r"\1", normalized)
    normalized = re.sub(r" *\n *", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _deduplicate_adjacent_sentences(text: str) -> tuple[str, int]:
    parts = re.split(r"(?<=[。！？!?；;])", text)
    output: list[str] = []
    removed = 0
    for part in parts:
        if part and output and part.strip() == output[-1].strip():
            removed += 1
            continue
        output.append(part)
    return "".join(output), removed


def _tokens(text: str) -> list[str]:
    chinese = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    latin = re.findall(r"[A-Za-z][A-Za-z0-9_-]*", text.casefold())
    return [*chinese, *latin]


def _mood_signal(positive_count: int, negative_count: int) -> tuple[int, str]:
    if positive_count == negative_count == 0:
        return 50, "未检测到明显正负情绪词"
    if positive_count > negative_count:
        return min(100, 55 + (positive_count - negative_count) * 15), f"积极线索 {positive_count} 个，消极线索 {negative_count} 个"
    if negative_count > positive_count:
        return max(0, 45 - (negative_count - positive_count) * 15), f"消极线索 {negative_count} 个，积极线索 {positive_count} 个"
    return 50, f"积极与消极线索各 {positive_count} 个"


def _suggestions(average_length: float, filler_count: int, redundancy_ratio: float, action_count: int, sensitive: dict[str, int], stress_count: int, negative_count: int) -> list[str]:
    suggestions: list[str] = []
    if average_length > 42:
        suggestions.append("句子偏长，可在结论、转折或动作处拆句。")
    if filler_count:
        suggestions.append("可删除部分填充词，让结论更直接。")
    if redundancy_ratio > 0.2:
        suggestions.append("重复用词较多，可合并相邻表达。")
    if not action_count:
        suggestions.append("没有明确行动项，可补充负责人、下一步或截止时间。")
    if stress_count or negative_count:
        suggestions.append("文本出现压力或消极线索；可先缩小当前任务，记录一个最小的下一步，并留意后续多次评估的变化。")
    if sensitive:
        suggestions.append("输出前请确认敏感字段是否需要脱敏或删除。")
    return suggestions or ["文本当前结构清楚，可按需保存或导出。"]
