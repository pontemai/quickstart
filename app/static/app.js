// Quickstart page behavior.
//
// The page polls config.json every two seconds. Each process start reports a
// new boot_id, so a changed boot_id means the device restarted the service,
// usually because its config changed. While the service is down the polls fail
// and the page shows the device applying config. The drawing, status pill and
// activity log all follow one state: live, applying, success or lost.
(function () {
  const $ = (id) => document.getElementById(id);
  const boot = JSON.parse($('boot').textContent);
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const CONFIG_POLL_MS = 2000;
  const DEVICE_POLL_MS = 5000;
  const LOST_AFTER_MS = 120000;

  // ── Fig. 1: control plane wired to this device ─────────
  // Same isometric projection as the landing page's fleet drawing.
  const NS = 'http://www.w3.org/2000/svg';
  const U = 14;
  const C = U * Math.cos(Math.PI / 6);
  const S = U * 0.5;
  const Z = U * 0.82;
  const iso = (x, y, z = 0) => [(x - y) * C, (x + y) * S - z * Z];
  const bounds = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
  const pts = (...corners) => corners.map((c) => {
    const [px, py] = iso(...c);
    bounds.x0 = Math.min(bounds.x0, px); bounds.x1 = Math.max(bounds.x1, px);
    bounds.y0 = Math.min(bounds.y0, py); bounds.y1 = Math.max(bounds.y1, py);
    return px.toFixed(1) + ',' + py.toFixed(1);
  }).join(' ');

  function add(parent, name, attrs, text) {
    const node = document.createElementNS(NS, name);
    for (const key in attrs) node.setAttribute(key, attrs[key]);
    if (text != null) node.textContent = text;
    parent.appendChild(node);
    return node;
  }
  function box(g, x, y, z, w, d, h) {
    const t = z + h;
    add(g, 'polygon', { class: 'f f-l', points: pts([x, y + d, t], [x + w, y + d, t], [x + w, y + d, z], [x, y + d, z]) });
    add(g, 'polygon', { class: 'f f-r', points: pts([x + w, y, t], [x + w, y + d, t], [x + w, y + d, z], [x + w, y, z]) });
    add(g, 'polygon', { class: 'f f-t', points: pts([x, y, t], [x + w, y, t], [x + w, y + d, t], [x, y + d, t]) });
  }
  function label(parent, x, y, text, dy) {
    const [px, py] = iso(x, y, 0);
    return add(parent, 'text', { class: 'fig-label', x: px.toFixed(1), y: (py + dy).toFixed(1), 'text-anchor': 'middle' }, text);
  }

  const scene = $('scene');
  // Ground first so the boxes paint over it, back to front.
  add(scene, 'polygon', { class: 'plate', points: pts([7.5, 3.5, 0], [13.5, 3.5, 0], [13.5, 9.5, 0], [7.5, 9.5, 0]) });
  const wire = pts([3, 1.5, 0], [6, 1.5, 0], [6, 6.5, 0], [7.5, 6.5, 0]);
  add(scene, 'polyline', { class: 'link', points: wire });
  add(scene, 'polyline', { class: 'packet', points: wire, pathLength: 1 });

  const cp = add(scene, 'g', { class: 'cp' });
  box(cp, 0, 0, 0, 3, 3, 2.4);
  add(cp, 'polygon', { class: 'cp-mark', points: pts([1.1, 1.1, 2.4], [1.9, 1.1, 2.4], [1.9, 1.9, 2.4], [1.1, 1.9, 2.4]) });
  label(scene, 1.5, 3, 'Pontem', 26);

  // The device: a finned edge box with an antenna, like the landing page's "edge".
  const dev = add(scene, 'g', { class: 'dev' });
  box(dev, 9.2, 5.2, 0, 3, 2.6, 1.3);
  for (let k = 0; k < 5; k++) box(dev, 9.45 + k * 0.55, 5.5, 1.3, 0.22, 2.0, 0.28);
  add(dev, 'polyline', { class: 's', 'stroke-width': 1.25, points: pts([9.5, 5.45, 1.3], [9.5, 5.45, 3.6]) });
  const [tx, ty] = iso(9.5, 5.45, 3.6);
  add(dev, 'circle', { class: 'antenna-tip', cx: tx.toFixed(1), cy: ty.toFixed(1), r: 2.6 });
  const hostLabel = label(scene, 10.5, 9.5, 'your device', 22);

  const pad = 28;
  scene.setAttribute('viewBox', [
    bounds.x0 - pad, bounds.y0 - pad,
    bounds.x1 - bounds.x0 + pad * 2, bounds.y1 - bounds.y0 + pad * 2 + 10,
  ].map((n) => n.toFixed(1)).join(' '));

  // ── State ──────────────────────────────────────────────
  const STATUS = { live: 'Live', applying: 'Applying config', success: 'Updated', lost: 'Not reachable' };
  let state = 'live';
  let current = boot;
  let downSince = null;
  let successTimer = null;

  function setState(next) {
    state = next;
    document.body.dataset.state = next;
    $('status-text').textContent = STATUS[next];
  }

  function clock(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  }

  function logLine(tone, text) {
    const li = document.createElement('li');
    const time = document.createElement('time');
    time.textContent = clock(new Date());
    const msg = document.createElement('span');
    if (tone) msg.className = tone;
    msg.textContent = text;
    li.append(time, msg);
    const log = $('log');
    log.append(li);
    while (log.children.length > 4) log.firstElementChild.remove();
  }

  // Scramble from the old greeting into the new one, left to right.
  function showGreeting(text, animate) {
    const el = $('greeting');
    const kv = $('kv-greeting');
    kv.textContent = JSON.stringify(text);
    if (!animate) { el.textContent = text; return; }
    kv.classList.remove('flash'); void kv.offsetWidth; kv.classList.add('flash');
    el.classList.add('changed');
    setTimeout(() => el.classList.remove('changed'), 2500);
    if (reduced) { el.textContent = text; return; }
    const glyphs = '░▒▓<>/\\|=+*#_-';
    const chars = Array.from(text);
    const start = performance.now();
    const duration = Math.min(1400, 400 + chars.length * 40);
    (function frame(now) {
      const p = Math.min(1, (now - start) / duration);
      const settled = Math.floor(p * chars.length);
      el.textContent = chars.map((ch, i) =>
        i < settled || ch === ' ' ? ch : glyphs[(Math.random() * glyphs.length) | 0]
      ).join('');
      if (p < 1) requestAnimationFrame(frame);
      else el.textContent = text;
    })(start);
  }

  function renderMeta() {
    const started = new Date(current.started_at);
    const viewLink = $('view-in-pontem');
    viewLink.hidden = !current.device_url;
    if (current.device_url) viewLink.href = current.device_url;
    $('foot-device').textContent = current.device_id;
    $('foot-package').textContent = current.package_version ? 'quickstart v' + current.package_version : 'quickstart (local)';
    $('foot-started').textContent = started.toLocaleString([], { hour12: false });
    $('try-cmd').textContent =
      "pontem config override set GREETING='Your text' --namespace quickstart --scope device:" +
      current.device_id + ' --yes';
  }

  async function fetchJSON(path) {
    // redirect: manual, so an expired app-proxy session shows up as a redirect
    // instead of a cross-origin sign-in page the fetch can't read.
    const res = await fetch(path, { cache: 'no-store', redirect: 'manual' });
    if (res.type === 'opaqueredirect' || res.status === 401) throw new Error('signed-out');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }

  let polling = true;
  async function pollConfig() {
    if (!polling) return;
    let next;
    try {
      next = await fetchJSON('config.json');
    } catch (err) {
      if (err.message === 'signed-out') {
        polling = false;
        setState('lost');
        logLine('warn', 'Your Pontem session ended. Reload to sign in again.');
        return;
      }
      if (downSince === null) {
        downSince = Date.now();
        setState('applying');
        logLine('warn', 'Service went down, likely for a config change');
      } else if (state !== 'lost' && Date.now() - downSince > LOST_AFTER_MS) {
        setState('lost');
        logLine('warn', 'Still unreachable. Reload the page if this persists.');
      }
      return;
    }
    const wasDown = downSince !== null;
    downSince = null;
    if (next.boot_id !== current.boot_id) {
      const changed = next.greeting !== current.greeting;
      current = next;
      renderMeta();
      if (changed) {
        showGreeting(next.greeting, true);
        logLine('ok', 'Restarted with GREETING = ' + JSON.stringify(next.greeting));
      } else {
        logLine('ok', 'Service restarted, config unchanged');
      }
      setState('success');
      clearTimeout(successTimer);
      successTimer = setTimeout(() => { if (state === 'success') setState('live'); }, 3500);
    } else if (wasDown) {
      setState('live');
      logLine('', 'Reconnected');
    }
  }

  // ── Device panel ───────────────────────────────────────
  const ARCH = { aarch64: 'ARM64', x86_64: 'x86-64' };
  function gb(bytes) { return (bytes / 1024 ** 3).toFixed(1); }
  function uptime(s) {
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
    return d ? d + 'd ' + h + 'h' : h ? h + 'h ' + m + 'm' : m + 'm';
  }
  function renderSpec(info) {
    const rows = [
      ['Host', info.hostname, true],
      ['OS', info.os || 'Linux ' + info.kernel, true],
      ['CPU', info.cpu || ARCH[info.arch] || info.arch, true],
      ['Memory', info.mem_total ? gb(info.mem_total - info.mem_available) + ' / ' + gb(info.mem_total) + ' GB' : null, true],
      ['Cores', info.cores],
      ['Load', info.load1 != null ? info.load1.toFixed(2) : null],
      ['Uptime', info.uptime_s != null ? uptime(info.uptime_s) : null],
      ['Temp', info.temp_c != null ? info.temp_c + ' °C' : null],
    ];
    const spec = $('spec');
    spec.replaceChildren(...rows.map(([name, value, wide]) => {
      const cell = document.createElement('div');
      if (wide) cell.className = 'wide';
      const dt = document.createElement('dt');
      dt.textContent = name;
      const dd = document.createElement('dd');
      dd.textContent = value == null || value === '' ? '—' : String(value);
      dd.title = dd.textContent;
      cell.append(dt, dd);
      return cell;
    }));
    hostLabel.textContent = info.hostname;
    $('lead-host').textContent = info.hostname;
  }
  async function pollDevice() {
    try { renderSpec(await fetchJSON('device.json')); } catch (err) { /* keep the last reading */ }
  }

  // ── Try it ─────────────────────────────────────────────
  $('copy-btn').addEventListener('click', async () => {
    const btn = $('copy-btn');
    try {
      await navigator.clipboard.writeText($('try-cmd').textContent);
      btn.textContent = 'Copied';
    } catch (err) {
      // Plain-http device URLs have no clipboard API; select the text instead.
      const range = document.createRange();
      range.selectNodeContents($('try-cmd'));
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      btn.textContent = 'Selected';
    }
    setTimeout(() => { btn.textContent = 'Copy'; }, 1600);
  });

  // ── Start ──────────────────────────────────────────────
  if (boot.viewer) {
    const viewer = $('foot-viewer');
    viewer.querySelector('b').textContent = boot.viewer;
    viewer.hidden = false;
  }
  setState('live');
  showGreeting(boot.greeting, false);
  renderMeta();
  logLine('', 'Connected' + (boot.package_version ? ' · package v' + boot.package_version : ''));
  pollDevice();
  setInterval(pollConfig, CONFIG_POLL_MS);
  setInterval(pollDevice, DEVICE_POLL_MS);
})();
