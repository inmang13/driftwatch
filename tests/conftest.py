import pytest


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Tests never call an LLM, whatever .env or the shell says."""
    monkeypatch.setenv("LLM", "fallback")
