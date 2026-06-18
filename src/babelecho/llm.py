import json
import os
import shlex
from pathlib import Path
from time import sleep
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ADAPT_CLEANUP_INSTRUCTIONS = (
    "Clean transcript artifacts such as subtitle arrows, timing residue, "
    "HTML or caption markup, duplicated rolling-caption residue, and "
    "meaningless filler disfluencies. "
    "Drop non-spoken stage directions such as [music], [applause], and "
    "[laughter]; do not translate them into Chinese narration. "
    "Remove transcript boilerplate such as copyright notices, terms-of-use "
    "text, and rush transcript disclaimers when they are not episode content. "
    "Normalize URLs and domains for Chinese TTS readability; do not turn "
    "domain dots into Chinese full stops, and prefer spoken dot wording such "
    "as example 点 com. "
    "Write media abbreviations in TTS-friendly Latin letters and digits, "
    "for example MP3 as M P 3 and MP4 as M P 4. "
)


class LLMClient(Protocol):
    def adapt_segment(self, text: str) -> str:
        raise NotImplementedError

    def adapt_segments(self, segments: list[dict[str, Any]]) -> list[dict[str, str]]:
        raise NotImplementedError

    def infer_speaker_genders(self, speakers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raise NotImplementedError


class FixtureLLMClient:
    def adapt_segment(self, text: str) -> str:
        return f"中文口播：{text}"

    def adapt_segments(self, segments: list[dict[str, Any]]) -> list[dict[str, str]]:
        return [
            {"id": str(segment["id"]), "text": self.adapt_segment(str(segment["text"]))}
            for segment in segments
        ]

    def infer_speaker_genders(self, speakers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = []
        for speaker in speakers:
            speaker_name = str(speaker["speaker"])
            speaker_key = speaker_name.casefold()
            if any(marker in speaker_key for marker in ("female", "woman", "女")):
                gender = "female"
            elif any(marker in speaker_key for marker in ("male", "man", "男")):
                gender = "male"
            else:
                gender = "unknown"
            results.append(
                {
                    "speaker": speaker_name,
                    "gender": gender,
                    "confidence": 1.0 if gender != "unknown" else 0.0,
                    "reason": "fixture name marker" if gender != "unknown" else "fixture unknown",
                }
            )
        return results


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

    def _chat_completion(self, prompt: str) -> str:
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
        for attempt in range(3):
            try:
                with urlopen(request, timeout=120) as response:
                    body = json.loads(response.read().decode("utf-8"))
                break
            except HTTPError as error:
                if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise
                sleep(2 * (attempt + 1))
            except URLError:
                if attempt == 2:
                    raise
                sleep(2 * (attempt + 1))
        return body["choices"][0]["message"]["content"].strip()

    def adapt_segment(self, text: str) -> str:
        prompt = (
            "请把下面英文播客片段改写成自然、适合口播的简体中文。"
            "清理字幕噪声、舞台提示、版权或转写免责声明；"
            "URL 和域名要适合中文 TTS 朗读，MP3/MP4 等缩写要避免被读成中文数字。"
            "只输出中文正文，不要解释。\n\n"
            f"{text}"
        )
        return self._chat_completion(prompt)

    def adapt_segments(self, segments: list[dict[str, Any]]) -> list[dict[str, str]]:
        expected_count = len(segments)
        prompt = (
            "You are adapting English podcast transcript segments into natural "
            "Simplified Chinese spoken-script text.\n"
            "Return only JSON with shape "
            '{"segments":[{"id":"0001","text":"中文口播正文"}]}.\n'
            f"Return exactly {expected_count} segments, one output item for each input id. "
            "Do not merge, split, remove, add, or reorder segment ids. "
            "If an input segment is a fragment or continuation, still return one "
            "Chinese spoken-script fragment for that exact id. "
            f"{ADAPT_CLEANUP_INSTRUCTIONS}"
            "Preserve factual content, named entities, numbers, claims, questions, "
            "causal links, and meaningful emphasis. "
            "Do not summarize across segments. "
            "Keep each output text suitable for Chinese TTS. "
            "Do not include explanations or markdown.\n\n"
            f"{json.dumps({'segments': segments}, ensure_ascii=False)}"
        )
        return _parse_adapt_segments_response(self._chat_completion(prompt))

    def infer_speaker_genders(self, speakers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        prompt = (
            "You are choosing Chinese TTS voice presentation for podcast speakers.\n"
            "Classify each speaker as male/female/unknown for TTS voice selection only. "
            "Do not claim or verify real identity gender.\n"
            "Use evidence in this priority: explicit titles/pronouns or bio in samples, "
            "well-known public host knowledge, then name and context. "
            "If evidence is weak or ambiguous, use unknown. "
            "Return only JSON with shape "
            '{"speakers":[{"speaker":"NAME","gender":"male|female|unknown",'
            '"confidence":0.0,"reason":"short evidence"}]}.\n\n'
            f"{json.dumps({'speakers': speakers}, ensure_ascii=False)}"
        )
        return _parse_speaker_gender_response(self._chat_completion(prompt))


class VLLMClient(OpenAICompatibleClient):
    pass


def _extract_json_object(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("LLM speaker gender response did not contain a JSON object")
    return cleaned[start:end + 1]


def _parse_speaker_gender_response(text: str) -> list[dict[str, Any]]:
    data = json.loads(_extract_json_object(text))
    speakers = data.get("speakers")
    if not isinstance(speakers, list):
        raise ValueError("LLM speaker gender response must contain a speakers list")
    results = []
    for item in speakers:
        if not isinstance(item, dict):
            continue
        speaker = item.get("speaker")
        if speaker is None:
            continue
        gender = str(item.get("gender", "unknown")).casefold()
        if gender not in {"male", "female", "unknown"}:
            gender = "unknown"
        try:
            confidence = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        results.append(
            {
                "speaker": str(speaker),
                "gender": gender,
                "confidence": confidence,
                "reason": str(item.get("reason", "")),
            }
        )
    return results


def _parse_adapt_segments_response(text: str) -> list[dict[str, str]]:
    data = json.loads(_extract_json_object(text))
    segments = data.get("segments")
    if not isinstance(segments, list):
        raise ValueError("LLM adapt response must contain a segments list")
    results = []
    for item in segments:
        if not isinstance(item, dict):
            continue
        segment_id = item.get("id")
        segment_text = item.get("text")
        if segment_id is None or segment_text is None:
            continue
        results.append({"id": str(segment_id), "text": str(segment_text).strip()})
    return results


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
