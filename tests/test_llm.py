import json

import pytest

from babelecho import llm
from babelecho.llm import build_llm_client


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None

    def read(self) -> bytes:
        return json.dumps(
            {"choices": [{"message": {"content": "这是一段自然的中文口播稿。"}}]}
        ).encode("utf-8")


def test_openai_compatible_client_sends_auth_and_extra_body(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    client = build_llm_client(
        {
            "provider": "openai_compatible",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-pro",
            "api_key_env": "DEEPSEEK_API_KEY",
            "temperature": 0.3,
            "max_tokens": 512,
            "extra_body": {"thinking": {"type": "disabled"}},
        }
    )

    output = client.adapt_segment("Today we talk about local-first AI.")

    assert output == "这是一段自然的中文口播稿。"
    request, timeout = requests[0]
    assert request.full_url == "https://api.deepseek.com/chat/completions"
    assert timeout == 120
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer test-deepseek-key"
    assert request.get_header("Content-type") == "application/json"

    payload = json.loads(request.data.decode("utf-8"))
    assert payload["model"] == "deepseek-v4-pro"
    assert payload["temperature"] == 0.3
    assert payload["max_tokens"] == 512
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["messages"][0]["role"] == "user"
    assert "Today we talk about local-first AI." in payload["messages"][0]["content"]


def test_openai_compatible_client_requires_configured_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        build_llm_client(
            {
                "provider": "openai_compatible",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-v4-pro",
                "api_key_env": "DEEPSEEK_API_KEY",
            }
        )


def test_openai_compatible_client_reads_api_key_file(tmp_path, monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    api_key_file = tmp_path / "deepseek.env"
    api_key_file.write_text(
        "\n# Local DeepSeek credential\nDEEPSEEK_API_KEY=file-backed-key\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    client = build_llm_client(
        {
            "provider": "openai_compatible",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-pro",
            "api_key_file": str(api_key_file),
        }
    )

    client.adapt_segment("A short transcript segment.")

    request, _ = requests[0]
    assert request.get_header("Authorization") == "Bearer file-backed-key"


def test_openai_compatible_client_reports_missing_api_key_file(tmp_path):
    missing_api_key_file = tmp_path / "missing-deepseek.env"

    with pytest.raises(ValueError, match="api_key_file"):
        build_llm_client(
            {
                "provider": "openai_compatible",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-v4-pro",
                "api_key_file": str(missing_api_key_file),
            }
        )
