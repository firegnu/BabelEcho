# On-demand Episode Convert Design

Date: 2026-06-18

## Goal

Make BabelEcho work as a point-in-time conversion tool for one episode the user is interested in, not as an external podcast subscription scanner.

The primary workflow is:

```text
episode input -> transcript discovery -> normalize -> chunked DeepSeek adapt -> local TTS -> MP3 -> optional feed item
```

## Product Shape

The user gives BabelEcho a specific episode input. BabelEcho converts only that episode and writes the normal run artifacts:

- `transcript/raw.*`
- `transcript/normalized.json`
- `script/zh.json`
- `output/audio.mp3`
- optional `publish/feed.xml`

The feed output remains useful because podcast clients can play it, but it is an output format for the converted episode, not the reason for the workflow.

## Inputs

First implementation should prefer exact inputs over broad search:

- A YouTube video URL with public captions.
- A podcast episode page URL that contains transcript text or a transcript link.
- A podcast RSS feed URL plus selected episode URL.
- A local transcript file.
- An existing `source` YAML.

Search-based discovery, such as "show name plus episode keyword", can be added after the exact URL workflow is stable.

## Architecture

Add a thin on-demand orchestration layer over the existing adapters and pipeline. It should not duplicate ingest or transcript parsing logic.

- URL resolver: classifies the user input into an existing source type.
- Source config writer: saves the resolved source as a run-local or requested YAML config.
- Pipeline runner: calls the existing `run` path with the generated source.
- Output reporter: prints the key artifacts and whether transcript discovery succeeded.

Existing source contracts remain unchanged:

- `source.type=youtube_captions`
- `source.type=episode_page`
- `source.type=podcast_rss`
- `source.type=transcript_file`

## Error Handling

If transcript discovery fails, the command should fail clearly with the unsupported reason:

- no public YouTube captions
- no transcript link or transcript body on the episode page
- RSS episode has no `podcast:transcript`
- unsupported URL type

It should not silently fall back to ASR, scrape audio, require cookies, or pretend the episode is convertible.

## Scope

In:

- One requested episode per command.
- Exact URL and existing source inputs first.
- Reuse existing source adapters and pipeline stages.
- Preserve stage controls such as `--to-stage adapt` and `--from-stage synthesize`.
- Produce the existing artifact layout.

Out:

- Subscribing to a show and periodically scanning new episodes.
- Multi episode batch conversion.
- Skip-processed logic as a primary workflow.
- Spotify or Apple Podcasts page scraping.
- ASR fallback.
- YouTube audio download.
- Original host voice clone.

## Tests

- Unit test URL classification for YouTube and generic episode-page URLs.
- CLI test that an exact episode URL generates the expected source config and calls the existing pipeline path.
- Failure test for unsupported URLs.
- Fixture run test to `adapt` for at least one on-demand source type.

## Follow-up

After this is stable, add an optional search helper:

```text
query -> candidate episodes -> choose one -> on-demand convert
```

That helper should remain separate from subscription scanning.
