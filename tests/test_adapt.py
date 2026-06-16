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
