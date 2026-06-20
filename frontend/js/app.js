/* App shell: hash routing, Library + Detail rendering, real <audio> player. */
(function () {
  const BE = window.BE;
  const esc = BE.escapeHtml;
  const app = document.getElementById('app');
  const audio = document.getElementById('player');
  const mobileMQ = window.matchMedia('(max-width: 820px)');

  let INDEX = null;            // { title, description, episodes }
  const EP_CACHE = {};         // run_id -> normalized episode
  const filters = { route: 'all', source: 'all', quality: 'all', speaker: 'all' };
  let curTab = 'script';
  let curEp = null;            // currently rendered detail episode
  let followSegs = [];          // [{el, start, end}] for the current tab panel
  let followIdx = -1;           // index of currently highlighted segment
  let suppressFollowUntil = 0;  // pause auto-scroll until this ms timestamp (manual scroll)

  const uniq = (base, extra) => {
    const out = base.slice();
    extra.forEach((v) => { if (v && out.indexOf(v) < 0) out.push(v); });
    return out;
  };
  const posKey = (id) => 'be:pos:' + id;
  const loadPos = (id) => { try { return parseFloat(localStorage.getItem(posKey(id))) || 0; } catch (e) { return 0; } };
  const savePos = (id, p) => { try { localStorage.setItem(posKey(id), String(p)); if (p > 0) localStorage.setItem('be:last', id); } catch (e) {} };
  const lastPlayedId = () => { try { return localStorage.getItem('be:last'); } catch (e) { return null; } };
  // visible only mid-listen: started past the intro, not yet at the end
  const midListen = (id, dur) => { const p = loadPos(id); return p >= 5 && (!dur || p < dur - 5) ? p : 0; };

  // ---------------- routing ----------------
  function parseHash() {
    const h = location.hash.replace(/^#\/?/, '');
    if (h.indexOf('ep/') === 0) return { view: 'detail', id: decodeURIComponent(h.slice(3)) };
    return { view: 'library' };
  }
  async function route() {
    stopAudio();
    const r = parseHash();
    if (r.view === 'detail') await renderDetail(r.id);
    else await renderLibrary();
  }
  function stopAudio() { try { audio.pause(); } catch (e) {} audio.removeAttribute('src'); audio.load(); curEp = null; }

  async function ensureIndex() { if (!INDEX) INDEX = await BE.loadIndex(); return INDEX; }

  // ---------------- Library ----------------
  async function renderLibrary() {
    app.innerHTML = '<div class="loading">读取 index.json…</div>';
    try { await ensureIndex(); } catch (e) {
      app.innerHTML = `<div class="errbox">无法读取 index.json：${esc(e.message)}<br>请确认已从仓库根目录启动静态服务，且 workspace/published/ 可访问。</div>`;
      return;
    }
    document.title = 'BabelEcho · 本地资料库';
    const eps = INDEX.episodes;
    const cnt = (pred) => eps.filter(pred).length;
    const qrec = (e) => e.quality_recommendation || 'unknown';

    const routes = uniq(['transcript_first', 'article_reading', 'audio_first'], eps.map((e) => e.route));
    const sources = uniq(['podcast_rss', 'web_article', 'youtube_captions', 'audio_file'], eps.map((e) => e.source_type));
    const quals = uniq(['safe_to_adapt', 'inspect_first', 'reject', 'unknown'], eps.map(qrec));

    const filt = (group, value, label, opts) => {
      opts = opts || {};
      const active = filters[group] === value;
      const c = opts.count;
      const dot = opts.dot ? `<span class="f-dot" style="background:${opts.dot}"></span>` : '';
      return `<button class="filt" data-group="${group}" data-value="${value}" aria-pressed="${active}" data-zero="${c === 0 ? 1 : 0}">
        <span class="f-label${opts.plain ? ' plain' : ''}">${dot}${esc(label)}</span><span class="f-count">${c}</span></button>`;
    };

    const railHtml = `<aside class="rail">
      <div class="rail-head"><span>资料库</span><span class="mono">${eps.length}</span></div>
      <div class="rail-group"><div class="rail-label">ROUTE</div>
        ${routes.map((r) => filt('route', r, r, { count: cnt((e) => e.route === r) })).join('')}</div>
      <div class="rail-group"><div class="rail-label">SOURCE</div>
        ${sources.map((sName) => filt('source', sName, sName, { count: cnt((e) => e.source_type === sName) })).join('')}</div>
      <div class="rail-group"><div class="rail-label">QUALITY</div>
        ${quals.map((q) => filt('quality', q, q, { count: cnt((e) => qrec(e) === q), dot: BE.quality(q).dot })).join('')}
        <div class="rail-note">safe_to_adapt 表示通过质量门禁、正常可播放，并不代表内容绝对正确。</div></div>
      <div class="rail-group"><div class="rail-label">SPEAKER</div>
        ${filt('speaker', 'with', '有角色', { count: cnt((e) => (e.speaker_count || 0) > 0), plain: true })}
        ${filt('speaker', 'without', '无角色分段', { count: cnt((e) => (e.speaker_count || 0) === 0), plain: true })}</div>
      ${anyFilter() ? '<button class="clear-btn" data-clear>清除筛选</button>' : ''}
    </aside>`;

    const shown = eps.filter((e) =>
      (filters.route === 'all' || e.route === filters.route) &&
      (filters.source === 'all' || e.source_type === filters.source) &&
      (filters.quality === 'all' || qrec(e) === filters.quality) &&
      (filters.speaker === 'all' || (filters.speaker === 'with' ? (e.speaker_count || 0) > 0 : (e.speaker_count || 0) === 0)));

    const totalDur = eps.reduce((a, e) => a + (e.duration_seconds || 0), 0);
    const routeKinds = new Set(eps.map((e) => e.route)).size;
    const allSafe = eps.length > 0 && eps.every((e) => qrec(e) === 'safe_to_adapt');

    const lastId = lastPlayedId();
    const lastEp = lastId ? eps.find((e) => e.run_id === lastId) : null;
    const lastPos = lastEp ? midListen(lastEp.run_id, lastEp.duration_seconds) : 0;
    const resumeHtml = (lastEp && lastPos)
      ? `<a class="resume-card" href="#/ep/${encodeURIComponent(lastEp.run_id)}">
          <div class="resume-ic">▶</div>
          <div class="resume-mid"><div class="resume-k">继续上次在听</div><div class="resume-title">${esc(lastEp.title)}</div></div>
          <div class="resume-pos">${BE.fmt(lastPos)}</div>
        </a>`
      : '';

    const rowsHtml = shown.map((e) => {
      const rc = e.route === 'article_reading' ? 'var(--accent-2)' : 'var(--accent)';
      const q = BE.quality(qrec(e));
      const none = (e.speaker_count || 0) === 0;
      const pos = midListen(e.run_id, e.duration_seconds);
      const prog = pos && e.duration_seconds
        ? `<div class="row-prog" title="已听 ${Math.round((pos / e.duration_seconds) * 100)}% · ${BE.fmt(pos)}"><span style="width:${Math.min(100, (pos / e.duration_seconds) * 100).toFixed(0)}%"></span></div>`
        : '';
      return `<a class="row grid-cols" data-rid="${esc(e.run_id)}" style="--route:${rc}" href="#/ep/${encodeURIComponent(e.run_id)}">
        <div style="min-width:0">
          <div class="row-title">${esc(e.title)}</div>
          <div class="row-host">${esc(e.run_id)}</div>
          ${prog}
        </div>
        <div class="badges"><span class="badge-route">${esc(e.route)}</span><span class="badge-source">${esc(e.source_type)}</span></div>
        <div class="row-dur">${BE.fmtDur(e.duration_seconds)}</div>
        <div class="row-spk" data-none="${none ? 1 : 0}">${none ? '无角色' : (e.speaker_count + ' 位说话人')}</div>
        <div><div class="q-line"><span class="dot" style="background:${q.dot}"></span>${esc(q.label)}</div>
          <div class="row-pub">${esc(BE.fmtTime(e.published_at).slice(5, 16))}</div></div>
      </a>`;
    }).join('');

    const emptyHtml = `<div class="empty">
      <div class="empty-title">${anyFilter() ? '当前筛选没有匹配的 episode。' : '没有 episode。'}</div>
      <div class="empty-sub">这些状态目前没有 fixture，界面仍保留其展示形态。</div>
      ${anyFilter() ? '<button class="clear-btn" data-clear>清除筛选</button>' : ''}</div>`;

    const listHtml = `<section class="list">
      <div class="term"><span class="u">visitor@babelecho</span>:<span class="p">~/published</span>$ ls episodes/<span class="cursor"></span></div>
      <div class="list-head"><h1 class="list-title">Episodes</h1><span class="list-count">${shown.length} / ${eps.length}</span></div>
      <div class="list-sub">按 published_at 倒序 · 仅展示 status = succeeded</div>
      <div class="chips">
        <span class="chip"><span class="k">总时长</span><span class="v">${BE.fmtDur(totalDur)}</span></span>
        <span class="chip"><span class="k">route</span><span class="v">${routeKinds}</span></span>
        ${allSafe ? '<span class="chip"><span class="dot"></span>全部 safe_to_adapt</span>' : ''}
      </div>
      ${resumeHtml}
      <div class="grid-cols cols"><div>标题 / 来源</div><div>route · source</div><div>时长</div><div>角色</div><div>质量 · 发布</div></div>
      ${shown.length ? rowsHtml : emptyHtml}
    </section>`;

    app.innerHTML = `<div class="library">${railHtml}${listHtml}</div>`;
    window.scrollTo(0, 0);
    enrichHosts(shown);
  }

  const anyFilter = () => Object.values(filters).some((v) => v !== 'all');

  // Lazily replace each row's secondary line (run_id) with the real source host
  // (index.json has no source URLs). Doubles as a cache warm-up for detail open.
  function enrichHosts(eps) {
    const queue = eps.slice();
    const worker = async () => {
      while (queue.length) {
        const e = queue.shift();
        try {
          const host = await BE.loadHost(e);
          if (!host) continue;
          const el = document.querySelector(`.row[data-rid="${e.run_id}"] .row-host`);
          if (el) { el.textContent = host; el.title = e.run_id; }
        } catch (_) { /* keep run_id fallback */ }
      }
    };
    for (let i = 0; i < 3; i++) worker();
  }

  // ---------------- Detail ----------------
  async function renderDetail(id) {
    app.innerHTML = '<div class="loading">读取 artifact.json…</div>';
    let item;
    try { await ensureIndex(); item = INDEX.episodes.find((e) => e.run_id === id); } catch (e) {
      app.innerHTML = `<div class="errbox">无法读取 index.json：${esc(e.message)}</div>`; return;
    }
    if (!item) { app.innerHTML = `<div class="errbox">未找到 episode：${esc(id)} <a class="back-btn" href="#/">返回资料库</a></div>`; return; }

    let ep;
    try { ep = EP_CACHE[id] || (EP_CACHE[id] = await BE.loadEpisode(item)); } catch (e) {
      app.innerHTML = `<div class="errbox">无法读取该集 artifact：${esc(e.message)} <a class="back-btn" href="#/">返回资料库</a></div>`; return;
    }
    curEp = ep; curTab = 'script';
    document.title = ep.title + ' · BabelEcho';

    const isArt = ep.route === 'article_reading';
    const accent = isArt ? 'var(--accent-2)' : 'var(--accent)';
    const q = BE.quality((ep.quality && ep.quality.recommendation) || 'unknown');
    const host = BE.host(ep.sourceUrl);

    app.innerHTML = `<div class="detail-scroll"><div class="detail" style="--accent-cur:${accent}">
      <a class="back-btn" href="#/"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 6l-6 6 6 6"/></svg>返回资料库</a>
      <div class="det-badges">
        <span class="badge-acc">${esc(ep.route)}</span>
        <span class="badge-pill">${esc(ep.item.source_type)}</span>
        <span class="badge-status"><span class="dot" style="background:${q.dot}"></span>${esc(ep.status)} · 可播放</span>
      </div>
      <h1 class="det-title">${esc(ep.title)}</h1>
      <div class="det-meta">${host ? `<span>${esc(host)}</span><span>·</span>` : ''}<span>${BE.fmtDur(ep.media.duration_seconds || ep.item.duration_seconds)}</span><span>·</span><span>${esc(BE.fmtTime(ep.published_at))}</span></div>
      <div class="det-grid">
        ${playerHtml(ep, isArt)}
        <aside class="det-rail">${railCardsHtml(ep, isArt)}</aside>
        <div class="det-body">
          ${tabsHtml(isArt)}
          <div class="tabpanel" id="tabpanel">${tabPanelHtml(ep, curTab, isArt)}</div>
        </div>
      </div>
    </div></div>`;

    wirePlayer(ep);
    collectFollowSegs();
    window.scrollTo(0, 0);
  }

  function playerHtml(ep, isArt) {
    const dur = ep.media.duration_seconds || ep.item.duration_seconds || 0;
    const playedColor = isArt ? 'var(--accent-2)' : 'var(--accent)';
    const bars = BE.wave(ep.run_id, 60).map((h) =>
      `<span class="bar" style="height:${(h * 100).toFixed(1)}%;background:var(--wave)" data-played="${playedColor}"></span>`).join('');
    return `<div class="player">
      <div class="wave" id="wave" role="slider" tabindex="0" aria-label="播放进度（左右键 ±5 秒）" aria-valuemin="0" aria-valuemax="${Math.round(dur)}" aria-valuenow="0" aria-valuetext="0:00">${bars}</div>
      <div class="player-time"><span class="pos" id="pos">0:00</span><span id="dur">${BE.fmtDur(dur)}</span></div>
      <div class="player-ctrl">
        <button class="play-btn" id="play" aria-label="播放/暂停">${ICON_PLAY}</button>
        <div class="eq" id="eq" hidden><span></span><span></span><span></span><span></span></div>
        <div class="seg-btns">
          <button class="seg-btn" data-skip="-15">−15s</button>
          <button class="seg-btn" data-skip="15">+15s</button>
          <button class="seg-btn" id="rate">1.0×</button>
        </div>
        <div class="spacer"></div>
        <a class="dl-btn" href="${esc(ep.audioUrl)}" download><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v12M7 11l5 5 5-5M5 21h14"/></svg>下载 MP3</a>
      </div></div>`;
  }

  function tabsHtml(isArt) {
    const defs = [['script', isArt ? '正文' : '中文脚本'], ['original', '英文原文'], ['quality', '质量'], ['meta', 'Metadata']];
    return `<div class="tabs" role="tablist">${defs.map(([k, l]) =>
      `<button class="tab" role="tab" data-tab="${k}" aria-selected="${k === curTab}">${l}</button>`).join('')}</div>`;
  }

  function tabPanelHtml(ep, tab, isArt) {
    if (tab === 'script') return scriptHtml(ep, isArt);
    if (tab === 'original') return originalHtml(ep, isArt);
    if (tab === 'quality') return qualityHtml(ep);
    return metaHtml(ep, isArt);
  }

  function scriptHtml(ep, isArt) {
    const segCount = metricVal(ep, 'segment_count') ?? ep.zh.length;
    if (isArt) {
      const body = ep.zh.map((s) => {
        const ts = s.start_ms != null ? ` data-start="${s.start_ms}" data-end="${s.end_ms}"` : '';
        return BE.isHeading(s.text)
          ? `<h3 class="reading-h"${ts}>${esc(s.text)}</h3>`
          : `<p class="reading-p"${ts}>${esc(s.text)}</p>`;
      }).join('');
      return `<div class="reading">${body}
        <div class="note">正文共 ${segCount} 段 · article_reading 路线为文章正文 + 小标题段，按阅读排版而非主持人转录行。播放时高亮跟随，可点击段落跳转。</div></div>`;
    }
    const rows = ep.zh.map((s) => {
      const role = ep.roleOf(s.speaker);
      const spk = s.speaker
        ? `<div class="seg-spk"><span class="seg-badge" style="--role:${BE.roleColor(role)}">${esc(s.speaker)}</span>${role ? `<span class="seg-role">${esc(role)}</span>` : ''}</div>`
        : '';
      const ts = s.start_ms != null ? ` data-start="${s.start_ms}" data-end="${s.end_ms}"` : '';
      return `<div class="seg"${ts}>${spk}<div class="seg-body"><span class="seg-id">${esc(s.id || '')}</span><p class="seg-text">${esc(s.text)}</p></div></div>`;
    }).join('');
    return `${rows}<div class="note">脚本共 ${segCount} 段 · 含无 speaker 的过场段时不显标签 · 播放时高亮跟随，可点击段落跳转。</div>`;
  }

  function originalHtml(ep, isArt) {
    if (!ep.en.length) {
      const note = isArt
        ? '英文为原始网页正文。可直接打开原文阅读。'
        : '本集没有可展示的英文 transcript。';
      return `<div class="empty-note"><div class="t">${note}</div>${ep.sourceUrl ? `<a class="linkout" href="${esc(ep.sourceUrl)}" target="_blank" rel="noopener">打开原文 ${ICON_EXT}</a>` : ''}</div>`;
    }
    if (isArt) {
      const body = ep.en.map((s) => BE.isHeading(s.text)
        ? `<h3 class="reading-h">${esc(s.text)}</h3>`
        : `<p class="reading-p">${esc(s.text)}</p>`).join('');
      return `<div class="reading">${body}<div class="note">英文为原始网页正文，transcript.en.json 无段级时间戳。</div></div>`;
    }
    const hasTs = ep.en.some((s) => s.start_ms != null);
    const rows = ep.en.map((s) => {
      const role = ep.roleOf(s.speaker);
      const meta = s.speaker
        ? `<div class="seg-spk"><span class="seg-badge" style="--role:${BE.roleColor(role)}">${esc(s.speaker)}</span>${s.start_ms != null ? `<span class="seg-time">${BE.fmtMs(s.start_ms)}</span>` : ''}</div>`
        : (s.start_ms != null ? `<div class="seg-spk"><span class="seg-time">${BE.fmtMs(s.start_ms)}</span></div>` : '');
      return `<div class="seg">${meta}<div class="seg-body"><span class="seg-id">${esc(s.id || '')}</span><p class="seg-text">${esc(s.text)}</p></div></div>`;
    }).join('');
    return `${rows}<div class="note">英文原文${hasTs ? '含段级时间戳（仅 podcast 路线），可按 id 与中文对照' : '无段级时间戳'} · 共 ${ep.en.length} 段。</div>`;
  }

  function qualityHtml(ep) {
    const Q = ep.quality || {};
    const rec = Q.recommendation || 'unknown';
    const q = BE.quality(rec);
    const warnings = Array.isArray(Q.warnings) ? Q.warnings : [];
    const reasons = Array.isArray(Q.reasons) ? Q.reasons : [];
    const metrics = Q.metrics || {};
    const metricCards = Object.keys(metrics).map((k) =>
      `<div class="metric"><div class="metric-k">${esc(k)}</div><div class="metric-v">${esc(String(metrics[k]))}</div></div>`).join('');
    const asrNote = ep.asr == null
      ? `未使用 ASR · ${esc(ep.route)} 路线，asr = null。`
      : `ASR：${esc(ep.asr.model || '')} · ${esc(ep.asr.language || '')} · diarization ${ep.asr.diarization && ep.asr.diarization.enabled ? '开启' : '关闭'}。`;
    return `<div class="q-card"><span class="dot" style="background:${q.dot}"></span>
        <div><div class="q-rec">${esc(rec)}</div><div class="q-desc">${esc(BE.qualityDesc(rec))}</div></div></div>
      <div class="q-cols">
        <div class="q-col"><div class="q-col-label">WARNINGS</div><div class="q-col-val">${warnings.length ? warnings.map((w) => `<span class="warn">${esc(w)}</span>`).join('') : '无警告'}</div></div>
        <div class="q-col"><div class="q-col-label">REASONS</div><div class="q-col-val">${reasons.length ? reasons.map((r) => esc(r)).join('<br>') : '无'}</div></div>
      </div>
      ${metricCards ? `<div class="metrics-label">METRICS</div><div class="metrics">${metricCards}</div>` : ''}
      <div class="asr-note"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/></svg>${asrNote}</div>`;
  }

  function metaHtml(ep, isArt) {
    const src = ep.source || {}, md = ep.media || {};
    const row = (k, v, href) => {
      if (v == null || v === '') return '';
      return `<div class="meta-row"><span class="meta-k">${esc(k)}</span>${href
        ? `<a class="meta-v" href="${esc(href)}" target="_blank" rel="noopener">${esc(v)} ↗</a>`
        : `<span class="meta-v">${esc(v)}</span>`}</div>`;
    };
    const identity = [row('run_id', ep.run_id), row('schema_version', ep.artifact.schema_version || '1.0'),
      row('status', ep.status), row('route', ep.route), row('published_at', ep.published_at)].join('');
    const source = [row('type', src.type), row('provider', src.provider),
      row('input_url', src.input_url, src.input_url), row('episode_url', src.episode_url, src.episode_url),
      row('transcript_url', src.transcript_url, src.transcript_url), row('feed_url', src.feed_url, src.feed_url)].join('');
    const media = [row('mime_type', md.mime_type), row('duration_seconds', md.duration_seconds),
      row('sample_rate', md.sample_rate != null ? md.sample_rate + ' Hz' : null), row('channels', md.channels),
      row('file_size_bytes', md.file_size_bytes != null ? `${md.file_size_bytes} (${BE.fmtBytes(md.file_size_bytes)})` : null)].join('');

    const artObj = ep.artifact.artifacts || {};
    const artItems = [];
    if (md.audio_path) artItems.push({ label: 'audio.mp3', path: md.audio_path, url: ep.audioUrl, dl: true });
    Object.keys(artObj).forEach((k) => {
      const rel = artObj[k]; if (!rel) return;
      artItems.push({ label: String(rel).split('/').pop(), path: rel, url: ep.fileUrl(rel), dl: false });
    });
    const arts = artItems.map((a) => `<div class="art-row">
        <div style="min-width:0"><span class="art-label">${esc(a.label)}</span><span class="art-path">${esc(a.path)}</span></div>
        ${a.dl ? `<a class="art-act dl" href="${esc(a.url)}" download>下载</a>` : `<a class="art-act" href="${esc(a.url)}" target="_blank" rel="noopener">查看 ↗</a>`}
      </div>`).join('');

    return `<div class="meta-sec"><div class="meta-sec-title">IDENTITY</div>${identity}</div>
      <div class="meta-sec"><div class="meta-sec-title">SOURCE</div>${source}
        ${isArt ? '<div class="meta-note">该来源未提供 author / site_name / published_time / excerpt，按缺省留白。asr = null。</div>' : ''}</div>
      <div class="meta-sec"><div class="meta-sec-title">MEDIA</div>${media}</div>
      <div class="meta-sec-title">ARTIFACTS</div>${arts}`;
  }

  function railCardsHtml(ep, isArt) {
    const hasSpk = (ep.speakers || []).length > 0;
    let head = '';
    if (hasSpk) {
      const rows = ep.speakers.map((sp) => {
        const role = sp.voice_role;
        const gender = sp.inferred_gender === 'male' ? '男声' : sp.inferred_gender === 'female' ? '女声' : 'gender —';
        return `<div class="spk-row" style="--role:${BE.roleColor(role)}">
          <div class="spk-av">${esc((sp.display_name || '?').slice(0, 1))}</div>
          <div class="spk-mid"><div class="spk-name">${esc(sp.display_name || sp.id)}</div><div class="spk-sub">${esc(gender)}</div></div>
          <div class="spk-right"><div class="spk-role">${esc(role || '—')}</div><div class="spk-count">${esc((sp.segment_count != null ? sp.segment_count : '—') + ' 段')}</div></div>
        </div>`;
      }).join('');
      head = `<div class="card collapsible" data-collapsible>
        <div class="card-head"><span>说话人 SPEAKERS</span><span><span class="cnt">${ep.speakers.length}</span> <button class="toggle" aria-label="展开/收起">−</button></span></div>
        <div class="card-body">${rows}</div></div>`;
    } else if (isArt) {
      head = `<div class="card muted"><div class="card-head"><span>文章朗读 ARTICLE</span></div>
        <div class="card-note">article_reading 路线不区分说话人，按正文 + 小标题阅读排版呈现。</div></div>`;
    } else {
      head = `<div class="card muted"><div class="card-head"><span>说话人 SPEAKERS</span></div>
        <div class="card-note">无角色分段。本集未识别说话人（speakers = []）。</div></div>`;
    }

    const segCount = metricVal(ep, 'segment_count');
    const info = [
      ['路线 route', ep.route], ['来源 source', ep.item.source_type],
      ['段数 segments', segCount != null ? String(segCount) : '—'],
      ['时长 duration', BE.fmtDur(ep.media.duration_seconds || ep.item.duration_seconds)],
      ['采样率', ep.media.sample_rate != null ? ep.media.sample_rate + ' Hz' : '—'],
      ['声道', ep.media.channels === 1 ? 'mono' : (ep.media.channels != null ? ep.media.channels : '—')],
    ].map(([k, v]) => `<div class="info-row"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`).join('');

    const sourceCard = `<div class="card collapsible" data-collapsible>
      <div class="card-head"><span>来源 / 下载</span><button class="toggle" aria-label="展开/收起">−</button></div>
      <div class="card-body">
        <a class="dl-btn" href="${esc(ep.audioUrl)}" download><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v12M7 11l5 5 5-5M5 21h14"/></svg>下载 MP3</a>
        ${ep.sourceUrl ? `<a class="src-link" href="${esc(ep.sourceUrl)}" target="_blank" rel="noopener">打开来源页 ${ICON_EXT}</a>` : ''}
        ${ep.feedUrl ? `<a class="src-link" href="${esc(ep.feedUrl)}" target="_blank" rel="noopener">打开 RSS feed ${ICON_EXT}</a>` : ''}
        ${isArt ? '<div class="card-note" style="margin-top:10px;font-size:11.5px;color:var(--fg-3)">该来源仅提供一个 URL，未含作者 / 站点名 / 发布时间 / 摘要，也无 RSS feed。</div>' : ''}
      </div></div>`;

    return `${head}
      <div class="card collapsible" data-collapsible><div class="card-head"><span>信息 INFO</span><button class="toggle" aria-label="展开/收起">−</button></div><div class="card-body">${info}</div></div>
      ${sourceCard}`;
  }

  const metricVal = (ep, key) => {
    const m = ep.quality && ep.quality.metrics;
    return m && m[key] != null ? m[key] : undefined;
  };

  // ---------------- follow-along ----------------
  function collectFollowSegs() {
    followSegs = [];
    followIdx = -1;
    const panel = document.getElementById('tabpanel');
    if (!panel) return;
    panel.querySelectorAll('[data-start]').forEach((el) => {
      followSegs.push({ el, start: Number(el.dataset.start), end: Number(el.dataset.end) });
    });
  }

  function followToTime(seconds) {
    if (!followSegs.length) return;
    const ms = seconds * 1000;
    let idx = -1;
    for (let i = 0; i < followSegs.length; i++) {
      if (followSegs[i].start <= ms) idx = i; else break;
    }
    if (idx === followIdx) return;
    if (followIdx >= 0 && followSegs[followIdx]) followSegs[followIdx].el.classList.remove('active');
    followIdx = idx;
    if (idx >= 0) {
      const el = followSegs[idx].el;
      el.classList.add('active');
      if (Date.now() > suppressFollowUntil) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  // ---------------- player wiring ----------------
  function wirePlayer(ep) {
    const dur0 = ep.media.duration_seconds || ep.item.duration_seconds || 0;
    const elPlay = document.getElementById('play');
    const elEq = document.getElementById('eq');
    const elPos = document.getElementById('pos');
    const elWave = document.getElementById('wave');
    const bars = elWave ? Array.from(elWave.children) : [];

    audio.src = ep.audioUrl;
    audio.playbackRate = 1;

    // Total-duration label stays the metadata value (matches the list/meta);
    // audio.duration only drives the progress ratio.
    const durOf = () => (isFinite(audio.duration) && audio.duration > 0 ? audio.duration : dur0);
    const paint = () => {
      const d = durOf();
      const played = Math.round((d > 0 ? audio.currentTime / d : 0) * bars.length);
      bars.forEach((b, i) => { b.style.background = i < played ? b.dataset.played : 'var(--wave)'; });
      if (elPos) elPos.textContent = BE.fmt(audio.currentTime);
      if (elWave) {
        elWave.setAttribute('aria-valuenow', Math.round(audio.currentTime));
        elWave.setAttribute('aria-valuetext', BE.fmt(audio.currentTime));
      }
      followToTime(audio.currentTime);
    };

    audio.onloadedmetadata = () => {
      if (elWave) elWave.setAttribute('aria-valuemax', Math.round(durOf()));
      const saved = loadPos(ep.run_id);
      if (saved > 1 && saved < durOf() - 2) audio.currentTime = saved;
      paint();
    };
    audio.ontimeupdate = () => { paint(); savePos(ep.run_id, audio.currentTime); };
    audio.onplay = () => { if (elPlay) elPlay.innerHTML = ICON_PAUSE; if (elEq) elEq.hidden = false; };
    audio.onpause = () => { if (elPlay) elPlay.innerHTML = ICON_PLAY; if (elEq) elEq.hidden = true; };
    audio.onended = () => { if (elPlay) elPlay.innerHTML = ICON_PLAY; if (elEq) elEq.hidden = true; };
    audio.onerror = () => { if (elPos) elPos.textContent = '音频不可用'; };

    if (elPlay) elPlay.onclick = () => { audio.paused ? audio.play().catch(() => {}) : audio.pause(); };
    if (elWave) elWave.onclick = (e) => {
      const r = elWave.getBoundingClientRect();
      audio.currentTime = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * durOf();
      paint();
    };
    if (elWave) elWave.onkeydown = (e) => {
      const d = durOf(); let t = audio.currentTime, handled = true;
      switch (e.key) {
        case 'ArrowRight': case 'ArrowUp': t += 5; break;
        case 'ArrowLeft': case 'ArrowDown': t -= 5; break;
        case 'PageUp': t += 30; break;
        case 'PageDown': t -= 30; break;
        case 'Home': t = 0; break;
        case 'End': t = d; break;
        default: handled = false;
      }
      if (handled) { e.preventDefault(); audio.currentTime = Math.min(d, Math.max(0, t)); paint(); }
    };
    paint();
  }

  // ---------------- global events ----------------
  app.addEventListener('click', (e) => {
    const filtBtn = e.target.closest('[data-group]');
    if (filtBtn) {
      const g = filtBtn.dataset.group, v = filtBtn.dataset.value;
      filters[g] = filters[g] === v ? 'all' : v;
      renderLibrary();
      return;
    }
    if (e.target.closest('[data-clear]')) {
      Object.keys(filters).forEach((k) => (filters[k] = 'all'));
      renderLibrary();
      return;
    }
    const tabBtn = e.target.closest('[data-tab]');
    if (tabBtn && curEp) {
      curTab = tabBtn.dataset.tab;
      document.querySelectorAll('.tab').forEach((t) => t.setAttribute('aria-selected', String(t.dataset.tab === curTab)));
      const panel = document.getElementById('tabpanel');
      if (panel) panel.innerHTML = tabPanelHtml(curEp, curTab, curEp.route === 'article_reading');
      collectFollowSegs();
      followToTime(audio.currentTime);
      return;
    }
    const skip = e.target.closest('[data-skip]');
    if (skip) { audio.currentTime = Math.max(0, audio.currentTime + Number(skip.dataset.skip)); return; }
    if (e.target.id === 'rate') {
      const steps = [1, 1.25, 1.5, 2, 0.75];
      const next = steps[(steps.indexOf(audio.playbackRate) + 1) % steps.length] || 1;
      audio.playbackRate = next; e.target.textContent = next.toFixed(2).replace(/0$/, '') + '×';
      return;
    }
    const segEl = e.target.closest('[data-start]');
    if (segEl && curEp) {
      audio.currentTime = Number(segEl.dataset.start) / 1000;
      if (audio.paused) audio.play().catch(() => {});
      return;
    }
    // mobile collapsible cards (also keyboard-activatable via the toggle button)
    const head = e.target.closest('.collapsible .card-head');
    if (head && mobileMQ.matches) {
      const card = head.closest('.collapsible');
      card.classList.toggle('collapsed');
      const t = card.querySelector('.toggle');
      if (t) t.textContent = card.classList.contains('collapsed') ? '+' : '−';
    }
  });

  // tablist: arrow keys move between tabs
  app.addEventListener('keydown', (e) => {
    const tab = e.target.closest('.tab');
    if (tab && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) {
      e.preventDefault();
      const tabs = [...document.querySelectorAll('.tab')];
      const i = tabs.indexOf(tab);
      const next = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
      if (next) { next.focus(); next.click(); }
    }
  });

  // collapse rail cards by default on mobile after each detail render
  function applyMobileCollapse() {
    if (!mobileMQ.matches) return;
    document.querySelectorAll('.collapsible').forEach((c) => {
      c.classList.add('collapsed');
      const t = c.querySelector('.toggle'); if (t) t.textContent = '+';
    });
  }
  mobileMQ.addEventListener('change', () => { if (curEp) applyMobileCollapse(); });
  const _origRenderDetail = renderDetail;
  renderDetail = async function (id) { await _origRenderDetail(id); applyMobileCollapse(); };

  // ---------------- icons ----------------
  const ICON_PLAY = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
  const ICON_PAUSE = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>';
  const ICON_EXT = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 01-1 1H6a1 1 0 01-1-1V7a1 1 0 011-1h5"/></svg>';

  const markManualScroll = () => { suppressFollowUntil = Date.now() + 3000; };
  window.addEventListener('wheel', markManualScroll, { passive: true });
  window.addEventListener('touchmove', markManualScroll, { passive: true });

  window.addEventListener('hashchange', route);
  route();
})();
