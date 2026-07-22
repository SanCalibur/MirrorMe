from __future__ import annotations

from .llm_cleaner import LlmCleaningError, request_llm_completion


DEFAULT_DIARY_PROMPT = """你是一位克制的中文日记编辑。根据当天已清洗的第一人称文本，写一篇 200 到 500 字的日记。
只写文本中能支持的主要事件、判断、感受和未完成事项；保留不确定性，不补充未出现的人名、地点、因果或细节。
使用自然的第一人称叙述，不要标题、列表、Markdown、诊断或建议。"""


def write_diary_with_llm(*, text: str, api_url: str, api_key: str, model: str, prompt: str = "") -> str:
    if not text.strip():
        raise LlmCleaningError("没有已接受的清洗文本可用于生成日记。")
    return request_llm_completion(text=text, api_url=api_url, api_key=api_key, model=model, system_prompt=prompt.strip() or DEFAULT_DIARY_PROMPT)
