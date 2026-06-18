from .jsonio import read_json, write_json
from .llm import build_llm_client
from .paths import RunPaths


def _chunk_segments(
    segments: list[dict],
    max_segments: int,
    max_chars: int,
) -> list[list[dict]]:
    chunks: list[list[dict]] = []
    current: list[dict] = []
    current_chars = 0
    for segment in segments:
        text_length = len(str(segment.get("text", "")))
        would_exceed_segments = len(current) >= max_segments
        would_exceed_chars = current and current_chars + text_length > max_chars
        if would_exceed_segments or would_exceed_chars:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(segment)
        current_chars += text_length
    if current:
        chunks.append(current)
    return chunks


def _validate_chunk_response(
    expected_segments: list[dict],
    adapted_segments: list[dict],
    chunk_number: int,
) -> dict[str, str]:
    expected_ids = [str(segment["id"]) for segment in expected_segments]
    seen: set[str] = set()
    adapted_by_id: dict[str, str] = {}
    duplicates: list[str] = []
    extra: list[str] = []
    for item in adapted_segments:
        segment_id = str(item.get("id", ""))
        text = str(item.get("text", "")).strip()
        if segment_id in seen:
            duplicates.append(segment_id)
            continue
        seen.add(segment_id)
        if segment_id not in expected_ids:
            extra.append(segment_id)
            continue
        adapted_by_id[segment_id] = text

    missing = [segment_id for segment_id in expected_ids if segment_id not in adapted_by_id]
    if missing or duplicates or extra:
        details = []
        if missing:
            details.append(f"missing ids: {', '.join(missing)}")
        if duplicates:
            details.append(f"duplicate ids: {', '.join(duplicates)}")
        if extra:
            details.append(f"extra ids: {', '.join(extra)}")
        raise ValueError(f"Invalid adapt chunk {chunk_number}: {'; '.join(details)}")
    empty = [segment_id for segment_id, text in adapted_by_id.items() if not text]
    if empty:
        raise ValueError(f"Invalid adapt chunk {chunk_number}: empty text ids: {', '.join(empty)}")
    return adapted_by_id


def _adapt_segments_one_by_one(transcript: dict, llm_config: dict) -> list[dict]:
    client = build_llm_client(llm_config)
    segments = []
    for segment in transcript["segments"]:
        text = client.adapt_segment(segment["text"])
        segments.append(
            {
                "id": segment["id"],
                "source_segment_ids": [segment["id"]],
                "speaker": segment.get("speaker"),
                "text": text,
            }
        )
    return segments


def _adapt_segments_in_chunks(
    run_paths: RunPaths,
    transcript: dict,
    llm_config: dict,
    adapt_config: dict,
) -> list[dict]:
    client = build_llm_client(llm_config)
    max_segments = max(1, int(adapt_config.get("chunk_max_segments", 20)))
    max_chars = max(1, int(adapt_config.get("chunk_max_chars", 8000)))
    retry_attempts = max(1, int(adapt_config.get("chunk_retry_attempts", 2)))
    chunks = _chunk_segments(transcript["segments"], max_segments, max_chars)
    chunk_dir = run_paths.script_dir / "adapt-chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    adapted_by_id: dict[str, str] = {}
    for index, chunk in enumerate(chunks, start=1):
        payload = [
            {
                "id": segment["id"],
                "speaker": segment.get("speaker"),
                "text": segment["text"],
            }
            for segment in chunk
        ]
        last_error: ValueError | None = None
        for _attempt in range(retry_attempts):
            adapted_segments = client.adapt_segments(payload)
            try:
                chunk_result = _validate_chunk_response(chunk, adapted_segments, index)
                break
            except ValueError as error:
                last_error = error
        else:
            assert last_error is not None
            raise last_error
        adapted_by_id.update(chunk_result)
        write_json(
            chunk_dir / f"chunk-{index:04d}.json",
            {
                "chunk": index,
                "input_ids": [segment["id"] for segment in chunk],
                "segments": [
                    {"id": segment["id"], "text": chunk_result[str(segment["id"])]}
                    for segment in chunk
                ],
            },
        )
    return [
        {
            "id": segment["id"],
            "source_segment_ids": [segment["id"]],
            "speaker": segment.get("speaker"),
            "text": adapted_by_id[str(segment["id"])],
        }
        for segment in transcript["segments"]
    ]


def adapt_to_chinese(
    run_paths: RunPaths,
    llm_config: dict,
    adapt_config: dict | None = None,
) -> str:
    transcript = read_json(run_paths.normalized_transcript_json)
    config = adapt_config or {}
    if config.get("mode") == "chunked":
        segments = _adapt_segments_in_chunks(
            run_paths,
            transcript,
            llm_config,
            config,
        )
    else:
        segments = _adapt_segments_one_by_one(transcript, llm_config)
    script = {
        "episode_id": transcript["episode_id"],
        "language": "zh-CN",
        "segments": segments,
    }
    write_json(run_paths.chinese_script_json, script)
    return str(run_paths.chinese_script_json)
