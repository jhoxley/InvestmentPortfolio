from config.settings import Settings


def test_default_settings(monkeypatch) -> None:
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.delenv("MARKET_DATA_SERVICE_URL", raising=False)
    monkeypatch.delenv("PORTFOLIO_ANALYSIS_SERVICE_URL", raising=False)

    # _env_file=None isolates this test from any real .env file in the cwd;
    # pydantic-settings supports this at init time but its type stubs don't
    # declare it, hence the targeted ignore.
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.host == "127.0.0.1"
    assert settings.port == 8050
    assert settings.debug is False
    assert settings.market_data_service_url == "http://127.0.0.1:8001"
    assert settings.portfolio_analysis_service_url == "http://127.0.0.1:8000"


def test_env_vars_override_defaults(monkeypatch) -> None:
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("MARKET_DATA_SERVICE_URL", "http://127.0.0.1:9001")
    monkeypatch.setenv("PORTFOLIO_ANALYSIS_SERVICE_URL", "http://127.0.0.1:9000")

    # _env_file=None isolates this test from any real .env file in the cwd;
    # pydantic-settings supports this at init time but its type stubs don't
    # declare it, hence the targeted ignore.
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.host == "0.0.0.0"
    assert settings.port == 9000
    assert settings.debug is True
    assert settings.market_data_service_url == "http://127.0.0.1:9001"
    assert settings.portfolio_analysis_service_url == "http://127.0.0.1:9000"
