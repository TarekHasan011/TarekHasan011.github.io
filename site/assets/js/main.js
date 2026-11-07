(() => {
  const root = document.documentElement;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  /* ---------------- Basic UI ---------------- */
  const year = $('#year');
  if (year) year.textContent = new Date().getFullYear();

  $('.theme-toggle')?.addEventListener('click', () => {
    const current = root.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    const next = current === 'dark' ? 'light' : 'dark';
    root.dataset.theme = next;
    try { localStorage.setItem('theme', next); } catch (e) {}
  });

  const toggle = $('.nav-toggle');
  const links = $('#nav-links');
  const closeNav = () => { links.classList.remove('is-open'); toggle.setAttribute('aria-expanded', 'false'); };
  toggle?.addEventListener('click', () => toggle.setAttribute('aria-expanded', String(links.classList.toggle('is-open'))));
  links?.addEventListener('click', e => { if (e.target.closest('a')) closeNav(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeNav(); });

  const header = $('.site-header');
  const onScroll = () => header.classList.toggle('is-scrolled', scrollY > 40);
  onScroll();
  addEventListener('scroll', onScroll, { passive: true });

  const navLinks = $$('.nav-links a[href^="#"]');
  const spy = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) navLinks.forEach(a => a.classList.toggle('is-active', a.getAttribute('href') === '#' + (entry.target.dataset.nav || entry.target.id)));
    });
  }, { rootMargin: '-45% 0px -50% 0px' });
  navLinks.map(a => $(a.getAttribute('href'))).filter(Boolean).forEach(s => spy.observe(s));
  $$('section[data-nav]').forEach(s => spy.observe(s)); // e.g. Education highlights "Experience & Education"

  const reveal = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) { entry.target.classList.add('is-visible'); reveal.unobserve(entry.target); }
    });
  }, { rootMargin: '0px 0px -8% 0px' });
  const observeReveals = scope => $$('.reveal:not(.is-visible)', scope).forEach(el => reveal.observe(el));
  observeReveals(document);

  /* ---------------- Medal tilt & tile spotlight ---------------- */
  if (!reduceMotion && matchMedia('(hover: hover)').matches) {
    $$('[data-tilt]').forEach(card => {
      card.addEventListener('pointermove', e => {
        const r = card.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5;
        card.style.transform = `perspective(900px) rotateY(${x * 8}deg) rotateX(${-y * 8}deg) translateY(-4px)`;
      });
      card.addEventListener('pointerleave', () => { card.style.transform = ''; });
    });
  }
  $$('.tile').forEach(tile => tile.addEventListener('pointermove', e => {
    const r = tile.getBoundingClientRect();
    tile.style.setProperty('--mx', `${e.clientX - r.left}px`);
    tile.style.setProperty('--my', `${e.clientY - r.top}px`);
  }));

  /* ---------------- Lightbox (images + videos) ---------------- */
  const box = $('.lightbox');
  const boxBody = $('.lightbox-body', box);
  const boxCap = $('.lightbox-caption', box);
  const openBox = (html, caption) => { boxBody.innerHTML = html; boxCap.textContent = caption || ''; box.showModal(); };
  box.addEventListener('close', () => { boxBody.innerHTML = ''; });
  $('.lightbox-close', box).addEventListener('click', () => box.close());
  box.addEventListener('click', e => { if (e.target === box) box.close(); });
  $$('[data-full]').forEach(el => el.addEventListener('click', () =>
    openBox(`<img src="${esc(el.dataset.full)}" alt="${esc($('img', el)?.alt)}">`, el.dataset.caption)));
  $$('.video-open').forEach(btn => btn.addEventListener('click', () =>
    openBox(`<iframe src="https://www.youtube-nocookie.com/embed/${esc(btn.dataset.yt)}?autoplay=1&rel=0${btn.dataset.start ? `&start=${parseInt(btn.dataset.start, 10)}` : ''}" title="${esc(btn.dataset.title)}" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen></iframe>`, btn.dataset.title)));

  /* ---------------- Count-up numbers ---------------- */
  const countTo = (el, to) => {
    const from = parseInt(el.textContent.replace(/\D/g, ''), 10) || 0;
    if (reduceMotion || from === to) { el.textContent = to; return; }
    const start = performance.now(), dur = 1400;
    const step = now => {
      const t = Math.min(1, (now - start) / dur), eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(from + (to - from) * eased);
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  const setLive = (key, value, { animate = true } = {}) => {
    $$(`[data-live="${key}"]`).forEach(el => {
      if (animate && typeof value === 'number') countTo(el, value); else el.textContent = value;
    });
  };
  // Hero numbers count up from zero on first load
  if (!reduceMotion) $$('.hstat .count').forEach(el => { el.textContent = '0'; countTo(el, +el.dataset.to); });

  /* ---------------- Live data ---------------- */
  const getJSON = async (...urls) => {
    for (const url of urls) {
      try {
        const r = await fetch(url, { cache: 'no-store' });
        if (r.ok) return { data: await r.json(), from: url };
      } catch (e) { /* try the next source */ }
    }
    return { data: null, from: null };
  };

  const ago = iso => {
    const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 60) return 'just now';
    if (s < 3600) return `${Math.round(s / 60)} min ago`;
    if (s < 86400) return `${Math.round(s / 3600)} h ago`;
    return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  };

  const norm = s => s.toLowerCase().replace(/[’']/g, "'").replace(/\s+/g, ' ').trim();
  const ME = /(Md\.? Tarek Hasan|\bMT Hasan\b)/;
  const boldMe = authors => esc(authors).replace(ME, '<b>Md. Tarek Hasan</b>');

  const titleKey = t => String(t || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
  function buildPubs(scholar, curated, journals, abstracts = {}) {
    const cur = Object.entries(curated).filter(([k]) => !k.startsWith('_'));
    return scholar.publications.map(p => {
      const title = norm(p.title);
      const match = cur.find(([k]) => title.startsWith(k));
      const c = match ? match[1] : {};
      const venue = c.venue || p.venue;
      const lv = norm(p.venue);
      const journal = journals.find(j => j.key === c.journal) || journals.find(j => lv.startsWith(j.match));
      const type = c.type || (/arxiv/i.test(p.venue) ? 'preprint' : journal ? 'journal' : 'conference');
      let authors = c.authors || p.authors;
      let authorsHTML = boldMe(authors);
      if (!ME.test(authors)) authorsHTML = esc(authors.replace(/,?\s*(\.\.\.|…)\s*$/, '')) + ', …, <b>Md. Tarek Hasan</b>, et al.';
      const arxiv = p.venue.match(/arXiv:(\d{4}\.\d{4,5})/i);
      const url = c.url || (arxiv ? `https://arxiv.org/abs/${arxiv[1]}` : p.scholar_url);
      const abstract = c.abstract || abstracts[titleKey(p.title)]?.abstract || '';
      return { ...p, venue, type, journal, authorsHTML, url, abstract, badges: c.badges || [], links: c.links || [], isNew: !match,
               firstAuthor: /^(Md\.? Tarek Hasan|MT Hasan)/.test(authors) };
    });
  }

  function journalChips(j) {
    if (!j) return '';
    const out = [];
    const sc = j.scopus;
    if (sc && sc.quartile) {
      const tip = `Scopus CiteScore ${sc.citescore ?? '–'} (${sc.citescore_year ?? ''}), best subject percentile ${sc.best_percentile ?? '–'}${sc.sjr ? `, SJR ${sc.sjr}` : ''}`;
      out.push(`<span class="pill pill-${sc.quartile.toLowerCase()}" title="${esc(tip)}">Scopus ${esc(sc.quartile)} <span class="mini-dot" aria-label="live"></span></span>`);
      if (sc.citescore) out.push(`<span class="metric-chip" title="Scopus CiteScore ${esc(sc.citescore_year)}"><span class="mini-dot" aria-hidden="true"></span>CiteScore ${esc(sc.citescore)}</span>`);
    } else if (j.jcr_quartile) {
      out.push(`<span class="pill pill-${j.jcr_quartile.toLowerCase()}" title="Quartile as recorded in the CV">${esc(j.jcr_quartile)}</span>`);
    }
    if (j.jcr_if) out.push(`<span class="metric-chip" title="Journal Impact Factor (Clarivate JCR), as recorded in the CV. No public API exists for live values.">Impact Factor ${esc(j.jcr_if)} <span class="src">JCR</span></span>`);
    if (j.openalex && j.openalex.two_year_mean_citedness) out.push(`<span class="metric-chip" title="2-year mean citedness from OpenAlex, fetched live. Same formula as an impact factor, on OpenAlex data."><span class="mini-dot" aria-hidden="true"></span>2-yr citedness ${esc(j.openalex.two_year_mean_citedness.toFixed(2))} <span class="src">OpenAlex</span></span>`);
    return out.join('');
  }

  const typeLabel = { journal: 'Journal', conference: 'Conference', preprint: 'Preprint' };
  let allPubs = [];
  let filter = 'all';
  let sortBy = 'year';

  function renderPubs() {
    const list = $('[data-live="pubs"]');
    const sorted = [...allPubs].sort((a, b) => sortBy === 'cites'
      ? (b.citations - a.citations) || ((b.year || 0) - (a.year || 0))
      : ((b.year || 0) - (a.year || 0)) || (b.citations - a.citations));
    list.innerHTML = sorted.map((p, i) => `
      <li class="pub reveal" data-type="${p.type}"${filter !== 'all' && p.type !== filter ? ' hidden' : ''}>
        <span class="pub-year">${esc(p.year ?? '')}</span>
        <div>
          <h3 class="pub-title"><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.title)}</a></h3>
          <p class="pub-authors">${p.authorsHTML}</p>
          <p class="pub-venue">${esc(p.venue)}</p>
          <p class="pub-tags">
            ${journalChips(p.journal)}
            ${p.badges.map(b => `<span class="pill ${b.tone === 'gold' ? 'pill-gold' : b.tone === 'outline' ? 'pill-outline' : ''}">${esc(b.label)}</span>`).join('')}
            <span class="pill">${typeLabel[p.type]}</span>
            ${p.firstAuthor ? '<span class="pill pill-outline">First author</span>' : ''}
            ${p.isNew ? '<span class="pill pub-new">New on Scholar</span>' : ''}
            ${p.links.map(l => `<a class="pub-link" href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)} ↗</a>`).join('')}
          </p>
          ${p.abstract ? `<button type="button" class="abs-toggle" aria-expanded="false" aria-controls="abs-${i}">
            <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M5 4h10l4 4v12H5z M14 4v5h5 M8 13h8 M8 17h6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>
            <span class="abs-open-label">Read abstract</span><span class="abs-close-label">Hide abstract</span>
            <svg class="abs-chev" viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </button>` : ''}
        </div>
        <a class="pub-cites" href="${esc(p.scholar_url)}" target="_blank" rel="noopener" style="text-decoration:none" aria-label="${p.citations} citations on Google Scholar"><b>${p.citations}</b><span>citations</span></a>
        ${p.abstract ? `<section class="abs-panel" id="abs-${i}" aria-label="Abstract: ${esc(p.title)}" hidden>
          <header class="abs-head">
            <span class="abs-kicker">Abstract</span>
            <span class="abs-meta">${esc(typeLabel[p.type])} · ${esc(p.year ?? '')}</span>
          </header>
          <p class="abs-text">${esc(p.abstract)}</p>
          <footer class="abs-foot">
            <a class="abs-read" href="${esc(p.url)}" target="_blank" rel="noopener">${/scholar\.google\./.test(p.url) ? 'View on Google Scholar' : 'Read the full paper'} <span aria-hidden="true">↗</span></a>
            <button type="button" class="abs-close" data-close="abs-${i}">Close</button>
          </footer>
        </section>` : ''}
      </li>`).join('');
    observeReveals(list);
    $$('.chip').forEach(chip => {
      const f = chip.dataset.filter;
      $('.count', chip).textContent = f === 'all' ? allPubs.length : allPubs.filter(p => p.type === f).length;
    });
  }

  // Abstract open / close (one listener for the whole list, so it survives re-sorting)
  $('[data-live="pubs"]').addEventListener('click', e => {
    const btn = e.target.closest('.abs-toggle, .abs-close');
    if (!btn) return;
    const li = btn.closest('.pub');
    const panel = $('.abs-panel', li), toggle = $('.abs-toggle', li);
    const open = btn.classList.contains('abs-close') ? false : panel.hidden;
    panel.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    li.classList.toggle('is-open', open);
    if (!open && btn.classList.contains('abs-close')) toggle.focus();
  });

  $$('.chip').forEach(chip => chip.addEventListener('click', () => {
    filter = chip.dataset.filter;
    $$('.chip').forEach(c => { c.classList.toggle('is-active', c === chip); c.setAttribute('aria-pressed', String(c === chip)); });
    $$('.pub').forEach(p => { p.hidden = filter !== 'all' && p.dataset.type !== filter; });
  }));
  $('[data-live="sort"]').addEventListener('change', e => { sortBy = e.target.value; renderPubs(); });

  function renderChart(series) {
    const bars = $('[data-live="chart"]');
    const max = Math.max(1, ...series.map(s => s.citations));
    bars.innerHTML = series.map(s => `
      <div class="bar" tabindex="0" aria-label="${s.year}: ${s.citations} citations">
        <span class="bar-tip">${s.year}: ${s.citations} citations</span>
        <span class="bar-val">${s.citations}</span>
        <span class="bar-fill" style="height:${Math.max(2, (s.citations / max) * 82)}%"></span>
        <span class="bar-year">${s.year}</span>
      </div>`).join('');
    $('[data-live="chart-table"] tbody').innerHTML = series.map(s => `<tr><td>${s.year}</td><td>${s.citations}</td></tr>`).join('');
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { bars.classList.add('is-drawn'); io.disconnect(); } });
    io.observe(bars);
  }

  function renderStatus(scholarRes) {
    const el = $('[data-live="sync-status"]');
    const d = scholarRes.data;
    if (!d) { el.innerHTML = '<span class="live-dot is-stale"></span>Could not reach Google Scholar'; return; }
    const viaServer = scholarRes.from.startsWith('/api/');
    let msg, stale = false;
    if (viaServer && d.status === 'live') msg = 'Synced with Google Scholar just now';
    else if (viaServer && d.status === 'cached') msg = `Synced with Google Scholar ${ago(d.fetched_at)}`;
    else {
      // Static hosting (GitHub Pages): data is refreshed by a daily job. Up to ~2 days old counts as current.
      const fresh = Date.now() - new Date(d.fetched_at).getTime() < 48 * 3600 * 1000;
      msg = fresh ? `Updated from Google Scholar ${ago(d.fetched_at)}` : `Showing saved Scholar data from ${ago(d.fetched_at)}`;
      stale = !fresh;
    }
    el.innerHTML = `<span class="live-dot${stale ? ' is-stale' : ''}" aria-hidden="true"></span>${esc(msg)}`;
    el.title = viaServer && d.status === 'cached' ? `To avoid being blocked by Google Scholar, a live check happens at most every 10 minutes (next in about ${Math.ceil((d.next_live_in_seconds || 0) / 60)} min).`
      : !viaServer ? 'Citations and publications are refreshed from Google Scholar once a day.' : (d.error || '');
    $('[data-live="citations-pill"]').textContent = `${d.metrics.citations} citations · ${stale ? 'saved' : viaServer ? 'live' : 'updated daily'} from Google Scholar`;
    $$('.live-pill .live-dot').forEach(dot => dot.classList.toggle('is-stale', stale));
  }

  async function loadLive() {
    const [scholarRes, journalsRes, curatedRes, abstractsRes] = await Promise.all([
      getJSON('/api/scholar', 'data/scholar-snapshot.json'),
      getJSON('/api/journals', 'data/journals-snapshot.json'),
      getJSON('data/curated.json'),
      getJSON('data/abstracts.json'),
    ]);
    renderStatus(scholarRes);
    const s = scholarRes.data;
    if (!s) return;
    const journals = journalsRes.data?.journals || [];
    allPubs = buildPubs(s, curatedRes.data || {}, journals, abstractsRes.data?.papers || {});

    const m = s.metrics;
    setLive('citations', m.citations);
    setLive('h_index', m.h_index);
    setLive('i10_index', m.i10_index);
    setLive('citations_recent_label', `${m.citations_recent} ${m.recent_label.toLowerCase()}`, { animate: false });
    setLive('pub_count', allPubs.length);
    const q1 = allPubs.filter(p => p.type === 'journal' && ((p.journal?.scopus?.quartile || p.journal?.jcr_quartile) === 'Q1')).length;
    setLive('q1_count', q1);
    setLive('top_cites', Math.max(0, ...allPubs.map(p => p.citations)));

    renderChart(s.citations_per_year || []);
    renderPubs();
  }
  loadLive();
})();
