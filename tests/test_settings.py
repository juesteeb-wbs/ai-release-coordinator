from app.settings import Settings, load_settings


def test_load_settings_uses_support_ticket_api_key(monkeypatch):
    monkeypatch.setenv("SUPPORT_TICKET_API_KEY", "configured-ticket-key")

    settings = load_settings()

    assert settings.api_key == "configured-ticket-key"


def test_load_settings_ignores_legacy_support_api_key(monkeypatch):
    monkeypatch.setenv("SUPPORT_API_KEY", "legacy-key")
    monkeypatch.delenv("SUPPORT_TICKET_API_KEY", raising=False)

    settings = load_settings()

    assert settings.api_key == Settings.api_key
