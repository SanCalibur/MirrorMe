from mirrorme.redaction import has_redactions, redact_text


def test_redacts_email_and_phone() -> None:
    text = "联系我 test@example.com 或 13800138000"

    redacted = redact_text(text)

    assert "test@example.com" not in redacted
    assert "13800138000" not in redacted
    assert "[REDACTED:email]" in redacted
    assert "[REDACTED:phone_cn]" in redacted


def test_redacts_password_like_fields() -> None:
    text = "password: hunter2"

    redacted = redact_text(text)

    assert "hunter2" not in redacted
    assert redacted == "[REDACTED:password]"


def test_detects_clean_text() -> None:
    assert not has_redactions("今天讨论了数字孪生的输入法入口。")

