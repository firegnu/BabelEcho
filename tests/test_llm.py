import json
from urllib.error import URLError

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


class FakeSpeakerGenderResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None

    def read(self) -> bytes:
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "speakers": [
                                        {
                                            "speaker": "ROMAN MARS",
                                            "gender": "male",
                                            "confidence": 0.95,
                                            "reason": "public host knowledge",
                                        },
                                        {
                                            "speaker": "TAYA",
                                            "gender": "unknown",
                                            "confidence": 0.2,
                                            "reason": "insufficient evidence",
                                        },
                                    ]
                                }
                            )
                        }
                    }
                ]
            }
        ).encode("utf-8")


class FakeAdaptSegmentsResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None

    def read(self) -> bytes:
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "segments": [
                                        {"id": "0002", "text": "第二段中文"},
                                        {"id": "0001", "text": "第一段中文"},
                                    ]
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }
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


def test_openai_compatible_client_retries_transient_url_errors(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        if len(requests) == 1:
            raise URLError("Tunnel connection failed: 503 Service Unavailable")
        return FakeResponse()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setattr(llm, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm, "sleep", lambda _seconds: None)

    client = build_llm_client(
        {
            "provider": "openai_compatible",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-pro",
            "api_key_env": "DEEPSEEK_API_KEY",
        }
    )

    output = client.adapt_segment("Retry this request.")

    assert output == "这是一段自然的中文口播稿。"
    assert len(requests) == 2


def test_openai_compatible_client_infers_speaker_genders_once(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeSpeakerGenderResponse()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    client = build_llm_client(
        {
            "provider": "openai_compatible",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-pro",
            "api_key_env": "DEEPSEEK_API_KEY",
            "temperature": 0.1,
            "max_tokens": 1024,
        }
    )

    output = client.infer_speaker_genders(
        [
            {
                "speaker": "ROMAN MARS",
                "segment_count": 13,
                "samples": ["Welcome to 99% Invisible. I'm Roman Mars."],
            },
            {
                "speaker": "TAYA",
                "segment_count": 1,
                "samples": ["A short question."],
            },
        ]
    )

    assert output == [
        {
            "speaker": "ROMAN MARS",
            "gender": "male",
            "confidence": 0.95,
            "reason": "public host knowledge",
        },
        {
            "speaker": "TAYA",
            "gender": "unknown",
            "confidence": 0.2,
            "reason": "insufficient evidence",
        },
    ]
    assert len(requests) == 1
    request, timeout = requests[0]
    assert request.full_url == "https://api.deepseek.com/chat/completions"
    assert timeout == 120
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["temperature"] == 0.1
    assert payload["max_tokens"] == 1024
    prompt = payload["messages"][0]["content"]
    assert "male/female/unknown" in prompt
    assert "ROMAN MARS" in prompt
    assert "TAYA" in prompt


def test_openai_compatible_client_adapts_segments_in_one_json_request(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeAdaptSegmentsResponse()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    client = build_llm_client(
        {
            "provider": "openai_compatible",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-pro",
            "api_key_env": "DEEPSEEK_API_KEY",
            "temperature": 0.2,
            "max_tokens": 2048,
        }
    )

    output = client.adapt_segments(
        [
            {"id": "0001", "speaker": "HOST", "text": "First sentence."},
            {"id": "0002", "speaker": "GUEST", "text": "Second sentence."},
        ]
    )

    assert output == [
        {"id": "0002", "text": "第二段中文"},
        {"id": "0001", "text": "第一段中文"},
    ]
    assert len(requests) == 1
    request, timeout = requests[0]
    assert request.full_url == "https://api.deepseek.com/chat/completions"
    assert timeout == 120
    payload = json.loads(request.data.decode("utf-8"))
    prompt = payload["messages"][0]["content"]
    assert "Return only JSON" in prompt
    assert "Do not merge" in prompt
    assert "Return exactly 2 segments" in prompt
    assert "faithful Simplified Chinese spoken translation" in prompt
    assert "Keep the original order of ideas inside each segment" in prompt
    assert "Do not summarize, condense, embellish, or reorganize" in prompt
    assert "Clean transcript artifacts" in prompt
    assert "stage directions" in prompt
    assert "copyright" in prompt
    assert "URLs and domains" in prompt
    assert "MP3" in prompt
    assert "Preserve factual content" in prompt
    assert "0001" in prompt
    assert "0002" in prompt


def test_openai_compatible_client_supports_polished_adapt_style(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeAdaptSegmentsResponse()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    client = build_llm_client(
        {
            "provider": "openai_compatible",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-pro",
            "api_key_env": "DEEPSEEK_API_KEY",
            "adapt_style": "polished_spoken",
        }
    )

    client.adapt_segments([{"id": "0001", "speaker": "HOST", "text": "First sentence."}])

    payload = json.loads(requests[0][0].data.decode("utf-8"))
    prompt = payload["messages"][0]["content"]
    assert "natural Simplified Chinese spoken-script text" in prompt
    assert "Preserve factual content" in prompt


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
