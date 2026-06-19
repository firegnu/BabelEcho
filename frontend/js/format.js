/* Pure presentation helpers. No DOM, no fetch. */
(function () {
  const BE = (window.BE = window.BE || {});

  // m:ss or h:mm:ss
  BE.fmt = function (s) {
    s = Math.max(0, Math.floor(s || 0));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
    const ss = String(x).padStart(2, '0');
    return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`;
  };
  BE.fmtDur = (s) => BE.fmt(Math.round(s || 0));

  // ISO 8601 -> "2026-06-19 13:01 UTC"; null/empty -> ""
  BE.fmtTime = (iso) => (iso ? String(iso).replace('T', ' ').replace('Z', ' UTC').slice(0, 16) : '');

  BE.host = (u) => {
    try { return new URL(u).host; } catch (e) { return u || ''; }
  };

  // ms -> m:ss for en timestamps; null -> ""
  BE.fmtMs = (ms) => (ms == null ? '' : BE.fmt(ms / 1000));

  BE.fmtBytes = (n) => {
    if (!n && n !== 0) return '';
    const u = ['B', 'KB', 'MB', 'GB'];
    let i = 0, v = Number(n);
    while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
    return (i === 0 ? v : v.toFixed(1)) + ' ' + u[i];
  };

  // BabelEcho fixed voice-role -> token color; unknown role -> accent.
  BE.roleColor = (role) => {
    const set = { male_a: 1, male_b: 1, female_a: 1, female_b: 1 };
    return role && set[role] ? `var(--role-${role})` : 'var(--accent)';
  };

  // quality.recommendation -> { dot color var, short label }
  BE.quality = (rec) => {
    const map = {
      safe_to_adapt: { dot: 'var(--ok)', label: 'safe_to_adapt' },
      inspect_first: { dot: 'var(--warn)', label: 'inspect_first' },
      reject: { dot: 'var(--bad)', label: 'reject' },
      unknown: { dot: 'var(--unknown)', label: 'unknown' },
    };
    return map[rec] || map.unknown;
  };

  // Human description per recommendation (does NOT promise "absolutely correct").
  BE.qualityDesc = (rec) => ({
    safe_to_adapt: '已通过后端质量门禁，可进入后续流程。safe_to_adapt 表示“正常可播放”，不代表内容绝对正确，仍建议抽检。',
    inspect_first: '后端质量门禁建议先人工复核再使用。',
    reject: '后端质量门禁不建议处理或播放此产物。',
    unknown: '未生成质量报告。',
  }[rec] || '未生成质量报告。');

  // Article heading heuristic: short segment with no terminal punctuation.
  // (transcript.zh.json has no explicit heading flag.)
  BE.isHeading = (text) => {
    const t = String(text || '').trim();
    return t.length > 0 && t.length <= 24 && !/[。.!！?？…）)」』”"，,、；;：:]$/.test(t);
  };

  BE.escapeHtml = (s) =>
    String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // Deterministic decorative waveform (FNV-1a seed) — purely visual, matches design.
  BE.wave = (seed, n) => {
    let h = 2166136261;
    for (let i = 0; i < seed.length; i++) { h ^= seed.charCodeAt(i); h = Math.imul(h, 16777619); }
    let x = h >>> 0; const out = [];
    for (let i = 0; i < n; i++) {
      x = (Math.imul(x, 1664525) + 1013904223) >>> 0;
      const r = x / 4294967295;
      const env = 0.4 + 0.6 * Math.sin((i / (n - 1)) * Math.PI);
      out.push(Math.max(0.14, Math.min(1, (0.22 + 0.9 * r) * env)));
    }
    return out;
  };
})();
