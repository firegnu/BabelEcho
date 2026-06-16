import json
from typing import Protocol
from urllib.request import Request, urlopen


class LLMClient(Protocol):
    def adapt_segment(self, text: str) -> str:
        raise NotImplementedError


class FixtureLLMClient:
    def adapt_segment(self, text: str) -> str:
        return f"中文口播：{text}"


class VLLMClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

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
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"].strip()


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
    raise ValueError(f"Unsupported llm.provider: {provider}")
