import socket

import pytest


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch):
    """Tests never inherit credentials, live flags or access to network sockets."""
    for key in ("APP_MODE", "ALLOW_LIVE_FETCH", "ALLOW_LIVE_PROVIDERS", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_MODEL", "ANTHROPIC_MODEL"):
        monkeypatch.delenv(key, raising=False)

    def no_network(*args, **kwargs):
        raise AssertionError("Network access is forbidden in tests")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
