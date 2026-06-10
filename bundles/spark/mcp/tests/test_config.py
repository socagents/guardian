"""Tests for configuration module."""

import pytest
from src.config.config import Settings


def test_settings_defaults():
    """Test that default settings are loaded correctly."""
    settings = Settings()
    # v0.6.45 flipped xlog_url default from http://localhost:8000 to
    # https://localhost:8000 (xlog has served HTTPS unconditionally
    # since v0.4.0; the http default was a v0.3.x artifact). v0.6.46
    # updates the test assertion to match. test_settings_from_env still
    # uses http:// to verify the env override path — that test isn't
    # about the default.
    assert settings.xlog_url == "https://localhost:8000"
    assert settings.xlog_port == 8000
    assert settings.mcp_transport == "stdio"
    assert settings.log_level == "INFO"


def test_settings_from_env(monkeypatch):
    """Test that settings can be loaded from environment variables."""
    monkeypatch.setenv("XLOG_URL", "http://example.com:9000")
    monkeypatch.setenv("XLOG_PORT", "9000")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings()
    assert settings.xlog_url == "http://example.com:9000"
    assert settings.xlog_port == 9000
    assert settings.log_level == "DEBUG"
