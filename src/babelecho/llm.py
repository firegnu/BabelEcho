import json
import os
import shlex
from pathlib import Path
from typing import Any, Protocol
from urllib.request import Request, urlopen


class LLMClient(Protocol):
    def adapt_segment(self, text: str) -> str:
        raise NotImplementedError


class FixtureLLMClient:
    def adapt_segment(self, text: str) -> str:
        return f"中文口播：{text}"


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        temperature: float,
        max_tokens: int,
        api_key: str | None = None,
        extra_body: dict[str, Any] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = api_key
        self.extra_body = extra_body or {}

    def adapt_segment(self, text: str) -> str:
        prompt = (
            "请把下面英文播客片段改写成自然、适合口播的简体中文。"
            "只输出中文正文，不要解释。\n\n"
            f"{text}"
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        payload.update(self.extra_body)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"].strip()


class VLLMClient(OpenAICompatibleClient):
    pass


def read_env_file_value(path: str, key: str) -> str:
    source = Path(path)
    if not source.exists():
        raise ValueError(f"Configured api_key_file does not exist: {source}")
    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        name, separator, value = line.partition("=")
        if separator and name.strip() == key:
            parsed = shlex.split(value, comments=False, posix=True)
            return parsed[0] if parsed else ""
    raise ValueError(f"Configured api_key_file does not define {key}: {source}")


def resolve_api_key(config: dict) -> str | None:
    api_key_env = config.get("api_key_env")
    api_key_file = config.get("api_key_file")
    if api_key_env and api_key_file:
        raise ValueError("Configure only one of api_key_env or api_key_file")
    if api_key_env:
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise ValueError(f"Missing required environment variable: {api_key_env}")
        return api_key
    if api_key_file:
        api_key = read_env_file_value(api_key_file, "DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError(f"Configured api_key_file contains an empty DEEPSEEK_API_KEY: {api_key_file}")
        return api_key
    return None


def build_llm_client(config: dict) -> LLMClient:
    provider = config.get("provider")
    if provider == "fixture":
        return FixtureLLMClient()
    if provider == "local_vllm":
        return VLLMClient(
            base_url=config["base_url"],
            model=config["model"],
            temperature=float(config.get("temperature", 0.3)),
            max_tokens=int(config.get("max_tokens", 4096)),
        )
    if provider == "openai_compatible":
        return OpenAICompatibleClient(
            base_url=config["base_url"],
            model=config["model"],
            temperature=float(config.get("temperature", 0.3)),
            max_tokens=int(config.get("max_tokens", 4096)),
            api_key=resolve_api_key(config),
            extra_body=config.get("extra_body"),
        )
    raise ValueError(f"Unsupported llm.provider: {provider}")
