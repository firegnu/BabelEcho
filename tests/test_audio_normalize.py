from pathlib import Path

from babelecho.audio_normalize import normalize_audio_transcript
from babelecho.jsonio import read_json, write_json
from babelecho.paths import create_run


def _write_audio_source(run_paths) -> None:
    write_json(
        run_paths.source_json,
        {
            "run_id": run_paths.run_id,
            "source_type": "audio_file",
            "provider": "local_file",
        },
    )


def _write_asr(run_paths, segments: list[dict]) -> Path:
    path = run_paths.run_dir / "asr" / "raw.json"
    write_json(
        path,
        {
            "provider": "fixture",
            "model": "fixture",
            "language": "en",
            "duration_seconds": 10.0,
            "segments": segments,
        },
    )
    return path


def _write_diarization(run_paths, segments: list[dict], speaker_count: int = 2) -> Path:
    path = run_paths.run_dir / "asr" / "diarization.json"
    write_json(
        path,
        {
            "provider": "fixture",
            "model": "fixture",
            "speaker_count": speaker_count,
            "segments": segments,
        },
    )
    return path


def test_audio_normalize_maps_asr_segments_to_diarization_speakers(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "audio-normalize")
    _write_audio_source(run_paths)
    _write_asr(
        run_paths,
        [
            {
                "id": "asr_0001",
                "start_ms": 0,
                "end_ms": 4200,
                "text": "Welcome back to the agent systems roundtable.",
                "confidence": 0.95,
            },
            {
                "id": "asr_0002",
                "start_ms": 4300,
                "end_ms": 9200,
                "text": "Today we are looking at long running agent evaluations.",
                "confidence": 0.93,
            },
        ],
    )
    _write_diarization(
        run_paths,
        [
            {"start_ms": 0, "end_ms": 4200, "speaker": "speaker_1"},
            {"start_ms": 4300, "end_ms": 9200, "speaker": "speaker_2"},
        ],
    )

    output = normalize_audio_transcript(run_paths)

    normalized = read_json(output)
    assert normalized == {
        "episode_id": "audio-normalize",
        "language": "en",
        "segments": [
            {
                "id": "0001",
                "start_ms": 0,
                "end_ms": 4200,
                "speaker": "speaker_1",
                "text": "Welcome back to the agent systems roundtable.",
                "source": "asr",
            },
            {
                "id": "0002",
                "start_ms": 4300,
                "end_ms": 9200,
                "speaker": "speaker_2",
                "text": "Today we are looking at long running agent evaluations.",
                "source": "asr",
            },
        ],
    }
    quality = read_json(run_paths.transcript_quality_json)
    assert quality["recommendation"] == "safe_to_adapt"
    assert quality["metrics"]["speaker_count"] == 2
    assert quality["metrics"]["timestamp_error_count"] == 0
    assert quality["metrics"]["source_type"] == "audio_file"
    assert quality["metrics"]["extractor"] == "asr"


def test_audio_normalize_uses_single_speaker_when_diarization_disabled(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "audio-normalize-none")
    _write_asr(
        run_paths,
        [
            {
                "start_ms": 0,
                "end_ms": 2000,
                "text": "First sentence from the recording.",
            },
            {
                "start_ms": 2400,
                "end_ms": 4200,
                "text": "Second sentence from the same recording.",
            },
        ],
    )
    write_json(
        run_paths.run_dir / "asr" / "diarization.json",
        {
            "provider": "none",
            "model": None,
            "speaker_count": 1,
            "segments": [],
            "warnings": ["diarization_disabled"],
        },
    )

    normalize_audio_transcript(run_paths)

    normalized = read_json(run_paths.normalized_transcript_json)
    assert {segment["speaker"] for segment in normalized["segments"]} == {"speaker_1"}
    quality = read_json(run_paths.transcript_quality_json)
    assert "diarization_disabled" in quality["warnings"]


def test_audio_normalize_marks_non_monotonic_timestamps_for_inspection(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "audio-normalize-time")
    _write_asr(
        run_paths,
        [
            {"start_ms": 0, "end_ms": 3000, "text": "First ASR segment."},
            {"start_ms": 2500, "end_ms": 4000, "text": "Overlapping ASR segment."},
        ],
    )
    write_json(
        run_paths.run_dir / "asr" / "diarization.json",
        {"provider": "none", "model": None, "speaker_count": 1, "segments": []},
    )

    normalize_audio_transcript(run_paths)

    quality = read_json(run_paths.transcript_quality_json)
    assert quality["recommendation"] == "inspect_first"
    assert quality["metrics"]["timestamp_error_count"] == 1
    assert "timestamp_errors" in quality["warnings"]


def test_audio_normalize_marks_many_short_speaker_turns_for_inspection(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "audio-normalize-turns")
    asr_segments = []
    diarization_segments = []
    for index in range(24):
        start_ms = index * 500
        end_ms = start_ms + 300
        speaker = "speaker_1" if index % 2 == 0 else "speaker_2"
        asr_segments.append(
            {
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": f"Short turn number {index}.",
            }
        )
        diarization_segments.append(
            {"start_ms": start_ms, "end_ms": end_ms, "speaker": speaker}
        )
    _write_asr(run_paths, asr_segments)
    _write_diarization(run_paths, diarization_segments)

    normalize_audio_transcript(run_paths)

    quality = read_json(run_paths.transcript_quality_json)
    assert quality["recommendation"] == "inspect_first"
    assert quality["metrics"]["speaker_turn_count"] == 24
    assert "too_many_short_speaker_turns" in quality["warnings"]


def test_audio_normalize_keeps_low_risk_cross_speaker_segments_safe(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "audio-normalize-low-risk-crossing")
    _write_asr(
        run_paths,
        [
            {"start_ms": 0, "end_ms": 1000, "text": "Opening statement."},
            {"start_ms": 1200, "end_ms": 2200, "text": "Follow up from host one."},
            {
                "start_ms": 2400,
                "end_ms": 7400,
                "text": "This ASR segment includes a tiny speaker boundary overlap.",
            },
            {"start_ms": 7600, "end_ms": 8600, "text": "Reply from host two."},
        ],
    )
    _write_diarization(
        run_paths,
        [
            {"start_ms": 0, "end_ms": 7000, "speaker": "speaker_1"},
            {"start_ms": 7000, "end_ms": 8600, "speaker": "speaker_2"},
        ],
    )

    normalize_audio_transcript(run_paths)

    quality = read_json(run_paths.transcript_quality_json)
    assert quality["recommendation"] == "safe_to_adapt"
    assert "asr_segment_crosses_speaker_turns" in quality["warnings"]
    assert quality["metrics"]["cross_speaker_segment_count"] == 1
    assert quality["metrics"]["cross_speaker_segment_ratio"] == 0.25
    assert quality["metrics"]["ambiguous_speaker_segment_count"] == 0
    assert quality["metrics"]["min_primary_speaker_overlap_ratio"] == 0.92


def test_audio_normalize_aggregates_same_speaker_split_turns(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "audio-normalize-split-turns")
    _write_asr(
        run_paths,
        [
            {
                "start_ms": 0,
                "end_ms": 5200,
                "text": "A single speaker sentence spans two diarization turns.",
            },
        ],
    )
    _write_diarization(
        run_paths,
        [
            {"start_ms": 0, "end_ms": 2200, "speaker": "speaker_1"},
            {"start_ms": 2200, "end_ms": 5200, "speaker": "speaker_1"},
        ],
        speaker_count=1,
    )

    normalize_audio_transcript(run_paths)

    quality = read_json(run_paths.transcript_quality_json)
    assert quality["recommendation"] == "safe_to_adapt"
    assert "asr_segment_crosses_speaker_turns" not in quality["warnings"]
    assert quality["metrics"]["cross_speaker_segment_count"] == 0
    assert quality["metrics"]["ambiguous_speaker_segment_count"] == 0
    assert quality["metrics"]["min_primary_speaker_overlap_ratio"] is None


def test_audio_normalize_keeps_sparse_ambiguous_segments_safe(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "audio-normalize-sparse-ambiguous")
    asr_segments = []
    diarization_segments = []
    for index in range(100):
        start_ms = index * 2_000
        end_ms = start_ms + 1_000
        asr_segments.append(
            {
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": f"ASR sentence {index}.",
            }
        )
        if index < 4:
            diarization_segments.extend(
                [
                    {
                        "start_ms": start_ms,
                        "end_ms": start_ms + 450,
                        "speaker": "speaker_1",
                    },
                    {
                        "start_ms": start_ms + 450,
                        "end_ms": end_ms,
                        "speaker": "speaker_2",
                    },
                ]
            )
        else:
            diarization_segments.append(
                {
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "speaker": "speaker_1",
                }
            )
    _write_asr(run_paths, asr_segments)
    _write_diarization(run_paths, diarization_segments)

    normalize_audio_transcript(run_paths)

    quality = read_json(run_paths.transcript_quality_json)
    assert quality["recommendation"] == "safe_to_adapt"
    assert "asr_segment_crosses_speaker_turns" in quality["warnings"]
    assert "ambiguous_speaker_assignments" not in quality["warnings"]
    assert quality["metrics"]["cross_speaker_segment_count"] == 4
    assert quality["metrics"]["ambiguous_speaker_segment_count"] == 4
    assert quality["metrics"]["ambiguous_speaker_segment_ratio"] == 0.04


def test_audio_normalize_marks_ambiguous_cross_speaker_segments_for_inspection(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "audio-normalize-ambiguous-crossing")
    _write_asr(
        run_paths,
        [
            {"start_ms": 0, "end_ms": 2000, "text": "Ambiguous mixed turn one."},
            {"start_ms": 2000, "end_ms": 4000, "text": "Ambiguous mixed turn two."},
            {"start_ms": 4000, "end_ms": 6000, "text": "Ambiguous mixed turn three."},
            {"start_ms": 6000, "end_ms": 8000, "text": "Clean single speaker turn."},
        ],
    )
    _write_diarization(
        run_paths,
        [
            {"start_ms": 0, "end_ms": 1000, "speaker": "speaker_1"},
            {"start_ms": 1000, "end_ms": 2000, "speaker": "speaker_2"},
            {"start_ms": 2000, "end_ms": 3000, "speaker": "speaker_2"},
            {"start_ms": 3000, "end_ms": 4000, "speaker": "speaker_1"},
            {"start_ms": 4000, "end_ms": 5000, "speaker": "speaker_1"},
            {"start_ms": 5000, "end_ms": 8000, "speaker": "speaker_2"},
        ],
    )

    normalize_audio_transcript(run_paths)

    quality = read_json(run_paths.transcript_quality_json)
    assert quality["recommendation"] == "inspect_first"
    assert "ambiguous_speaker_assignments" in quality["warnings"]
    assert quality["metrics"]["cross_speaker_segment_count"] == 3
    assert quality["metrics"]["cross_speaker_segment_ratio"] == 0.75
    assert quality["metrics"]["ambiguous_speaker_segment_count"] == 3
    assert quality["metrics"]["min_primary_speaker_overlap_ratio"] == 0.5


def test_audio_normalize_keeps_short_boundary_missing_overlap_safe(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "audio-normalize-tail-missing")
    _write_asr(
        run_paths,
        [
            {"start_ms": 0, "end_ms": 2_000, "text": "Main episode sentence."},
            {"start_ms": 2_200, "end_ms": 3_200, "text": "Bye."},
        ],
    )
    _write_diarization(
        run_paths,
        [
            {"start_ms": 0, "end_ms": 2_000, "speaker": "speaker_1"},
        ],
        speaker_count=1,
    )

    normalize_audio_transcript(run_paths)

    quality = read_json(run_paths.transcript_quality_json)
    assert quality["recommendation"] == "safe_to_adapt"
    assert "missing_diarization_overlap" in quality["warnings"]
    assert quality["metrics"]["missing_diarization_overlap_segment_count"] == 1
    assert quality["metrics"]["missing_diarization_overlap_boundary_segment_count"] == 1
    assert quality["metrics"]["missing_diarization_overlap_total_duration_ms"] == 1000


def test_audio_normalize_marks_interior_missing_overlap_for_inspection(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "audio-normalize-mid-missing")
    _write_asr(
        run_paths,
        [
            {"start_ms": 0, "end_ms": 2_000, "text": "Opening sentence."},
            {"start_ms": 3_000, "end_ms": 5_000, "text": "Uncovered middle sentence."},
            {"start_ms": 6_000, "end_ms": 8_000, "text": "Closing sentence."},
        ],
    )
    _write_diarization(
        run_paths,
        [
            {"start_ms": 0, "end_ms": 2_000, "speaker": "speaker_1"},
            {"start_ms": 6_000, "end_ms": 8_000, "speaker": "speaker_1"},
        ],
        speaker_count=1,
    )

    normalize_audio_transcript(run_paths)

    quality = read_json(run_paths.transcript_quality_json)
    assert quality["recommendation"] == "inspect_first"
    assert "missing_diarization_overlap" in quality["warnings"]
    assert quality["metrics"]["missing_diarization_overlap_segment_count"] == 1
    assert quality["metrics"]["missing_diarization_overlap_boundary_segment_count"] == 0


def test_audio_normalize_rejects_empty_asr_text(tmp_path: Path):
    run_paths = create_run(tmp_path / "workspace", "audio-normalize-empty")
    _write_asr(
        run_paths,
        [
            {"start_ms": 0, "end_ms": 1000, "text": "   "},
            {"start_ms": 1200, "end_ms": 2000, "text": ""},
        ],
    )
    write_json(
        run_paths.run_dir / "asr" / "diarization.json",
        {"provider": "none", "model": None, "speaker_count": 1, "segments": []},
    )

    normalize_audio_transcript(run_paths)

    normalized = read_json(run_paths.normalized_transcript_json)
    quality = read_json(run_paths.transcript_quality_json)
    assert normalized["segments"] == []
    assert quality["recommendation"] == "reject"
    assert "empty_transcript" in quality["reasons"]
    assert "empty_asr_segments" in quality["warnings"]


def test_audio_normalize_merges_adjacent_same_speaker_short_segments(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "audio-normalize-merge")
    _write_asr(
        run_paths,
        [
            {"start_ms": 0, "end_ms": 1000, "text": "The first short phrase."},
            {"start_ms": 1200, "end_ms": 2200, "text": "The second short phrase."},
        ],
    )
    write_json(
        run_paths.run_dir / "asr" / "diarization.json",
        {"provider": "none", "model": None, "speaker_count": 1, "segments": []},
    )

    normalize_audio_transcript(run_paths)

    normalized = read_json(run_paths.normalized_transcript_json)
    assert normalized["segments"] == [
        {
            "id": "0001",
            "start_ms": 0,
            "end_ms": 2200,
            "speaker": "speaker_1",
            "text": "The first short phrase. The second short phrase.",
            "source": "asr",
        }
    ]


def test_audio_normalize_drops_high_confidence_boundary_ads(tmp_path: Path):
    run_paths = create_run(tmp_path / "workspace", "audio-normalize-boundary-ads")
    _write_audio_source(run_paths)
    _write_asr(
        run_paths,
        [
            {
                "start_ms": 0,
                "end_ms": 3500,
                "text": "This BBC podcast is supported by ads outside the UK.",
            },
            {
                "start_ms": 30000,
                "end_ms": 40180,
                "text": "This TV broadcast will be waiting only one year for more information on our website.",
            },
            {
                "start_ms": 60000,
                "end_ms": 64340,
                "text": "One point five. Do you want to work, astronaut?",
            },
            {
                "start_ms": 90000,
                "end_ms": 100800,
                "text": "Hello. This is 6 Minute English from BBC Learning English.",
            },
            {
                "start_ms": 100800,
                "end_ms": 110000,
                "text": "Today we are talking about screen time for children.",
            },
            {
                "start_ms": 450000,
                "end_ms": 462000,
                "text": "Once again, our six minutes are up.",
            },
            {"start_ms": 462000, "end_ms": 466000, "text": "Goodbye."},
            {
                "start_ms": 476000,
                "end_ms": 492000,
                "text": "BBC NL is the best of Brits drama and comedy series.",
            },
        ],
    )
    write_json(
        run_paths.run_dir / "asr" / "diarization.json",
        {"provider": "none", "model": None, "speaker_count": 1, "segments": []},
    )

    normalize_audio_transcript(run_paths)

    normalized = read_json(run_paths.normalized_transcript_json)
    assert [segment["text"] for segment in normalized["segments"]] == [
        "Hello. This is 6 Minute English from BBC Learning English. Today we are talking about screen time for children.",
        "Once again, our six minutes are up. Goodbye.",
    ]
    assert [segment["id"] for segment in normalized["segments"]] == ["0001", "0002"]
    quality = read_json(run_paths.transcript_quality_json)
    assert quality["recommendation"] == "safe_to_adapt"
    assert "dropped_boundary_content_segments" in quality["warnings"]
    assert quality["metrics"]["dropped_boundary_content_segment_count"] == 4
    assert quality["metrics"]["segment_count"] == 2


def test_audio_normalize_keeps_uncertain_boundary_promo_with_warning(
    tmp_path: Path,
):
    run_paths = create_run(tmp_path / "workspace", "audio-normalize-possible-promo")
    _write_audio_source(run_paths)
    _write_asr(
        run_paths,
        [
            {
                "start_ms": 0,
                "end_ms": 4000,
                "text": "For more information, visit our website.",
            },
            {
                "start_ms": 4500,
                "end_ms": 8000,
                "text": "Welcome to the actual episode.",
            },
        ],
    )
    write_json(
        run_paths.run_dir / "asr" / "diarization.json",
        {"provider": "none", "model": None, "speaker_count": 1, "segments": []},
    )

    normalize_audio_transcript(run_paths)

    normalized = read_json(run_paths.normalized_transcript_json)
    assert [segment["text"] for segment in normalized["segments"]] == [
        "For more information, visit our website. Welcome to the actual episode."
    ]
    quality = read_json(run_paths.transcript_quality_json)
    assert quality["recommendation"] == "safe_to_adapt"
    assert "possible_boundary_content_segments" in quality["warnings"]
    assert quality["metrics"]["possible_boundary_content_segment_count"] == 1
