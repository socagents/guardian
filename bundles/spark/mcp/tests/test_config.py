"""Tests for configuration module."""

import pytest
from src.config.config import Settings


def test_settings_defaults():
    """Test that default settings are loaded correctly."""
    settings = Settings()
    assert settings.mcp_transport == "stdio"
    assert settings.mcp_port == 8080
    assert settings.mcp_path == "/api/v1/stream/mcp"
    assert settings.log_level == "INFO"


def test_settings_from_env(monkeypatch):
    """Test that settings can be loaded from environment variables."""
    monkeypatch.setenv("MCP_PORT", "9090")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings()
    assert settings.mcp_port == 9090
    assert settings.log_level == "DEBUG"
