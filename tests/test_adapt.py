from pathlib import Path

from babelecho.adapt import adapt_to_chinese
from babelecho.jsonio import read_json, write_json
from babelecho.paths import create_run


def test_adapt_to_chinese_with_fixture_llm(tmp_path: Path):
    run_paths = create_run(tmp_path, "adapt-run")
    write_json(
        run_paths.normalized_transcript_json,
        {
            "episode_id": "adapt-run",
            "language": "en",
            "segments": [
                {
                    "id": "0001",
                    "start_ms": None,
                    "end_ms": None,
                    "speaker": None,
                    "text": "Welcome to the sample episode.",
                    "source": "transcript",
                }
            ],
        },
    )

    output = adapt_to_chinese(run_paths, {"provider": "fixture"})
    data = read_json(output)

    assert data["language"] == "zh-CN"
    assert data["segments"][0]["source_segment_ids"] == ["0001"]
    assert "中文口播" in data["segments"][0]["text"]


def test_adapt_to_chinese_batches_complete_segments_and_merges_by_original_id(
    tmp_path: Path,
    monkeypatch,
):
    run_paths = create_run(tmp_path, "chunked-adapt-run")
    write_json(
        run_paths.normalized_transcript_json,
        {
            "episode_id": "chunked-adapt-run",
            "language": "en",
            "segments": [
                {
                    "id": "0001",
                    "start_ms": None,
                    "end_ms": None,
                    "speaker": "HOST",
                    "text": "First sentence.",
                    "source": "transcript",
                },
                {
                    "id": "0002",
                    "start_ms": None,
                    "end_ms": None,
                    "speaker": "GUEST",
                    "text": "Second sentence.",
                    "source": "transcript",
                },
                {
                    "id": "0003",
                    "start_ms": None,
                    "end_ms": None,
                    "speaker": "HOST",
                    "text": "Third sentence.",
                    "source": "transcript",
                },
            ],
        },
    )
    calls = []

    class FakeBatchClient:
        def adapt_segment(self, text: str) -> str:
            raise AssertionError("chunked adapt should not call adapt_segment")

        def adapt_segments(self, segments: list[dict]) -> list[dict]:
            calls.append([segment["id"] for segment in segments])
            return [
                {"id": segment["id"], "text": f"中文 {segment['id']}"}
                for segment in reversed(segments)
            ]

    monkeypatch.setattr(
        "babelecho.adapt.build_llm_client",
        lambda _config: FakeBatchClient(),
    )

    output = adapt_to_chinese(
        run_paths,
        {"provider": "fake"},
        {"mode": "chunked", "chunk_max_segments": 2, "chunk_max_chars": 10_000},
    )
    data = read_json(output)

    assert calls == [["0001", "0002"], ["0003"]]
    assert [segment["id"] for segment in data["segments"]] == ["0001", "0002", "0003"]
    assert [segment["speaker"] for segment in data["segments"]] == ["HOST", "GUEST", "HOST"]
    assert [segment["text"] for segment in data["segments"]] == [
        "中文 0001",
        "中文 0002",
        "中文 0003",
    ]
    assert sorted(path.name for path in (run_paths.script_dir / "adapt-chunks").iterdir()) == [
        "chunk-0001.json",
        "chunk-0002.json",
    ]


def test_adapt_to_chinese_rejects_chunk_response_with_missing_segment_id(
    tmp_path: Path,
    monkeypatch,
):
    run_paths = create_run(tmp_path, "bad-chunked-adapt-run")
    write_json(
        run_paths.normalized_transcript_json,
        {
            "episode_id": "bad-chunked-adapt-run",
            "language": "en",
            "segments": [
                {
                    "id": "0001",
                    "start_ms": None,
                    "end_ms": None,
                    "speaker": "HOST",
                    "text": "First sentence.",
                    "source": "transcript",
                },
                {
                    "id": "0002",
                    "start_ms": None,
                    "end_ms": None,
                    "speaker": "GUEST",
                    "text": "Second sentence.",
                    "source": "transcript",
                },
            ],
        },
    )

    class FakeBadBatchClient:
        def adapt_segment(self, text: str) -> str:
            raise AssertionError("chunked adapt should not call adapt_segment")

        def adapt_segments(self, segments: list[dict]) -> list[dict]:
            return [{"id": "0001", "text": "中文 0001"}]

    monkeypatch.setattr(
        "babelecho.adapt.build_llm_client",
        lambda _config: FakeBadBatchClient(),
    )

    try:
        adapt_to_chinese(
            run_paths,
            {"provider": "fake"},
            {"mode": "chunked", "chunk_max_segments": 10, "chunk_max_chars": 10_000},
        )
    except ValueError as error:
        assert "missing ids" in str(error)
    else:
        raise AssertionError("chunk response with a missing id should fail")


def test_adapt_to_chinese_retries_chunk_response_with_missing_segment_id(
    tmp_path: Path,
    monkeypatch,
):
    run_paths = create_run(tmp_path, "retry-chunked-adapt-run")
    write_json(
        run_paths.normalized_transcript_json,
        {
            "episode_id": "retry-chunked-adapt-run",
            "language": "en",
            "segments": [
                {
                    "id": "0001",
                    "start_ms": None,
                    "end_ms": None,
                    "speaker": "HOST",
                    "text": "First sentence.",
                    "source": "transcript",
                },
                {
                    "id": "0002",
                    "start_ms": None,
                    "end_ms": None,
                    "speaker": "GUEST",
                    "text": "Second sentence.",
                    "source": "transcript",
                },
            ],
        },
    )
    calls = []

    class FakeRetryBatchClient:
        def adapt_segment(self, text: str) -> str:
            raise AssertionError("chunked adapt should not call adapt_segment")

        def adapt_segments(self, segments: list[dict]) -> list[dict]:
            calls.append([segment["id"] for segment in segments])
            if len(calls) == 1:
                return [{"id": "0001", "text": "中文 0001"}]
            return [
                {"id": segment["id"], "text": f"中文 {segment['id']}"}
                for segment in segments
            ]

    monkeypatch.setattr(
        "babelecho.adapt.build_llm_client",
        lambda _config: FakeRetryBatchClient(),
    )

    output = adapt_to_chinese(
        run_paths,
        {"provider": "fake"},
        {"mode": "chunked", "chunk_max_segments": 10, "chunk_max_chars": 10_000},
    )
    data = read_json(output)

    assert calls == [["0001", "0002"], ["0001", "0002"]]
    assert [segment["text"] for segment in data["segments"]] == [
        "中文 0001",
        "中文 0002",
    ]
