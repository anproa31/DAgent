from src.core.config import get_settings, reset_settings_cache


def test_settings_defaults(isolated_env):
    settings = get_settings()
    assert settings.code_runner_url == "http://sandbox:8001/"
    assert str(isolated_env) == settings.datasource_root
    assert settings.sandbox_url == "http://sandbox:8001"


def test_settings_cache_reset(isolated_env, monkeypatch):
    monkeypatch.setenv("CODE_RUNNER_URL", "http://custom:9000/")
    reset_settings_cache()
    assert get_settings().code_runner_url == "http://custom:9000/"
