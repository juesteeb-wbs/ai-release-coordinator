import re


SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(
        r"(?i)\b[\w-]*(api[_-]?key|token|password|secret)[\w-]*\b\s*[:=]\s*['\"]?[^'\"\s]+"
    ),
)


def redact_secrets(text: str) -> tuple[str, bool]:
    redacted = text
    changed = False
    for pattern in SECRET_PATTERNS:
        redacted, count = pattern.subn("[REDACTED_SECRET]", redacted)
        changed = changed or count > 0
    return redacted, changed
