from __future__ import annotations

import re


REDACTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("api_key", re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}\b")),
    ("password", re.compile(r"(?i)\b(password|passwd|pwd|密码)\s*[:=：]\s*\S+")),
    ("verification_code", re.compile(r"(?i)\b(code|验证码|verification code)\s*[:=：]?\s*\d{4,8}\b")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("phone_cn", re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")),
    ("bank_card", re.compile(r"(?<!\d)(?:\d[ -]?){15,19}(?!\d)")),
    ("id_card_cn", re.compile(r"(?<!\d)\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)")),
]


def redact_text(text: str) -> str:
    redacted = text
    for label, pattern in REDACTION_PATTERNS:
        redacted = pattern.sub(f"[REDACTED:{label}]", redacted)
    return redacted


def has_redactions(text: str) -> bool:
    return redact_text(text) != text

