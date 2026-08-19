from release_agent.redaction import redact_secrets


def test_redact_secrets_masks_github_tokens():
    redacted, changed = redact_secrets("token = ghp_1234567890abcdefghijklmnop")

    assert changed is True
    assert redacted == "[REDACTED_SECRET]"


def test_redact_secrets_masks_password_assignments():
    redacted, changed = redact_secrets("DATABASE_PASSWORD=super-secret-value")

    assert changed is True
    assert redacted == "[REDACTED_SECRET]"


def test_redact_secrets_leaves_normal_text_unchanged():
    redacted, changed = redact_secrets("Add customer email ticket filter")

    assert changed is False
    assert redacted == "Add customer email ticket filter"
