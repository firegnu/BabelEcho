/* Read-only data layer over workspace/published/.
   The frontend ONLY reads published artifacts; it never writes or triggers anything. */
(function () {
  const BE = (window.BE = window.BE || {});

  // Where the published artifacts are served from.
  // Dev default matches the repo-root static server + the workspace/published symlink.
  // For other deployments, set window.BABELECHO_BASE before this script loads.
  BE.BASE = (window.BABELECHO_BASE != null ? window.BABELECHO_BASE : '/workspace/published').replace(/\/+$/, '');

  // index.json paths (audio_path / artifact_path) are relative to published/.
  BE.fromBase = (p) => new URL(BE.BASE + '/' + String(p).replace(/^\/+/, ''), location.href).href;

  // artifact.json paths (media.audio_path, artifacts.*) are relative to the episode dir.
  const episodeDirUrl = (artifactPath) =>
    new URL(BE.BASE + '/' + String(artifactPath).replace(/\/[^/]*$/, '/'), location.href);
  BE.resolveInEpisode = (artifactPath, rel) => new URL(rel, episodeDirUrl(artifactPath)).href;

  async function getJSON(url) {
    const res = await fetch(url, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
    return res.json();
  }

  // transcript files come in two shapes: { segments: [...] } or a bare [...].
  const segmentsOf = (json) =>
    Array.isArray(json) ? json : json && Array.isArray(json.segments) ? json.segments : [];

  // List entry point. Default to status === 'succeeded', newest first.
  BE.loadIndex = async function () {
    const idx = await getJSON(BE.fromBase('index.json'));
    const episodes = (idx.episodes || [])
      .filter((e) => e.status === 'succeeded')
      .sort((a, b) => String(b.published_at || '').localeCompare(String(a.published_at || '')));
    return { title: idx.title || 'BabelEcho', description: idx.description || '', episodes };
  };

  // Lightweight: just the source host for an episode (for the list's secondary line).
  const HOST_CACHE = {};
  BE.loadHost = async function (item) {
    if (item.run_id in HOST_CACHE) return HOST_CACHE[item.run_id];
    const art = await getJSON(BE.fromBase(item.artifact_path));
    const s = art.source || {};
    return (HOST_CACHE[item.run_id] = BE.host(s.episode_url || s.input_url || ''));
  };

  // Detail entry point: artifact.json + zh/en transcripts, normalized for rendering.
  BE.loadEpisode = async function (item) {
    const artifact = await getJSON(BE.fromBase(item.artifact_path));
    const a = artifact.artifacts || {};
    const zhRel = a.script_zh || 'transcript.zh.json';
    const enRel = a.transcript_en || 'transcript.en.json';

    const [zh, en] = await Promise.all([
      getJSON(BE.resolveInEpisode(item.artifact_path, zhRel)).then(segmentsOf).catch(() => []),
      getJSON(BE.resolveInEpisode(item.artifact_path, enRel)).then(segmentsOf).catch(() => []),
    ]);

    const speakers = Array.isArray(artifact.speakers) ? artifact.speakers : [];
    const byName = {};
    speakers.forEach((sp) => { if (sp.display_name) byName[sp.display_name] = sp; });

    return {
      item,
      artifact,
      run_id: artifact.run_id || item.run_id,
      route: artifact.route || item.route,
      status: artifact.status || item.status,
      title: artifact.title || item.title,
      summary: artifact.summary || null,
      published_at: artifact.published_at || item.published_at || null,
      source: artifact.source || {},
      quality: artifact.quality || null,
      media: artifact.media || {},
      speakers,
      asr: artifact.asr || null,
      ui: artifact.ui || {},
      zh,
      en,
      // role lookup: zh segments only carry the speaker name, not voice_role.
      roleOf: (name) => (name && byName[name] ? byName[name].voice_role : null),
      audioUrl: BE.fromBase(item.audio_path),
      sourceUrl: (artifact.source || {}).episode_url || (artifact.source || {}).input_url || '',
      feedUrl: (artifact.source || {}).feed_url || null,
      // resolve an artifacts.* relative path to a clickable URL
      fileUrl: (rel) => BE.resolveInEpisode(item.artifact_path, rel),
    };
  };
})();
