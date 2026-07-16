from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SYSTEM_PROMPT = """你是中文文本清洗助手。只输出清洗后的原文，不要解释、不加标题。
保留原意、事实、语气、专有名词、数字和不确定性；修正明显的空白、断句、重复片段、口语填充和标点问题。
不要编造、总结、扩写或删除具有实际信息的内容。"""


class LlmCleaningError(ValueError):
    pass


def clean_text_with_llm(*, text: str, api_url: str, api_key: str, model: str, prompt: str | None = None) -> str:
    if not text.strip():
        return ""
    return request_llm_completion(
        text=text,
        api_url=api_url,
        api_key=api_key,
        model=model,
        system_prompt=prompt.strip() if prompt and prompt.strip() else SYSTEM_PROMPT,
    )


def request_llm_completion(*, text: str, api_url: str, api_key: str, model: str, system_prompt: str) -> str:
    if not api_url.strip() or not api_key.strip() or not model.strip():
        raise LlmCleaningError("请填写 LLM URL、API Key 和模型名称。")
    endpoint = _chat_completions_url(api_url)
    payload = {
        "model": model.strip(),
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
    }
    request = Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key.strip()}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise LlmCleaningError(f"LLM 请求失败（HTTP {exc.code}）：{detail}") from exc
    except URLError as exc:
        raise LlmCleaningError(f"无法连接 LLM 服务：{exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise LlmCleaningError("LLM 服务返回了无法解析的数据。") from exc

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmCleaningError("LLM 服务未返回可用的清洗文本。") from exc
    if not isinstance(content, str) or not content.strip():
        raise LlmCleaningError("LLM 服务返回了空文本。")
    return content.strip()


def _chat_completions_url(value: str) -> str:
    url = value.strip().rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/v1"):
        return f"{url}/chat/completions"
    return f"{url}/v1/chat/completions"
