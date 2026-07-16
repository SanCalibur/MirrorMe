import json
from unittest.mock import patch

import pytest

from mirrorme.llm_cleaner import LlmCleaningError, clean_text_with_llm


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def test_llm_cleaner_posts_openai_compatible_request() -> None:
    with patch(
        "mirrorme.llm_cleaner.urlopen",
        return_value=FakeResponse({"choices": [{"message": {"content": "清洗后的文本。"}}]}),
    ) as mocked:
        result = clean_text_with_llm(
            text="原始文本",
            api_url="https://example.test/v1",
            api_key="test-key",
            model="test-model",
        )

    request = mocked.call_args.args[0]
    assert result == "清洗后的文本。"
    assert request.full_url == "https://example.test/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer test-key"
    assert json.loads(request.data)["model"] == "test-model"


def test_llm_cleaner_requires_all_configuration_values() -> None:
    with pytest.raises(LlmCleaningError, match="API Key"):
        clean_text_with_llm(text="内容", api_url="https://example.test", api_key="", model="model")
