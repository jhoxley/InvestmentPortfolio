from config.settings import Settings


def test_default_settings(monkeypatch) -> None:
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)

    # _env_file=None isolates this test from any real .env file in the cwd;
    # pydantic-settings supports this at init time but its type stubs don't
    # declare it, hence the targeted ignore.
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.host == "127.0.0.1"
    assert settings.port == 8050
    assert settings.debug is False


def test_env_vars_override_defaults(monkeypatch) -> None:
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("DEBUG", "true")

    # _env_file=None isolates this test from any real .env file in the cwd;
    # pydantic-settings supports this at init time but its type stubs don't
    # declare it, hence the targeted ignore.
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.host == "0.0.0.0"
    assert settings.port == 9000
    assert settings.debug is True
