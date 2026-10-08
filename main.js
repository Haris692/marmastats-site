(() => {
  "use strict";
  document.documentElement.classList.add("js");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  /* ---------------- language ---------------- */
  let lang = "en";
  const t = (k) => (I18N[lang] && I18N[lang][k]) ?? I18N.en[k] ?? k;

  function pickLang() {
    const q = new URLSearchParams(location.search).get("lang");
    if (q && I18N[q]) return q;
    try { const s = localStorage.getItem("mm-lang"); if (s && I18N[s]) return s; } catch (e) {}
    const n = (navigator.language || "en").slice(0, 2);
    return I18N[n] ? n : "en";
  }

  function setLang(l) {
    lang = l;
    const html = document.documentElement;
    html.lang = l;
    html.dir = l === "ar" ? "rtl" : "ltr";
    document.title = t("meta.title");
    $$("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    $$("[data-i18n-html]").forEach((el) => { el.innerHTML = t(el.dataset.i18nHtml); });
    $$(".lang button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === l)));
    $$("#shots img").forEach((img) => { img.src = `assets/shots/${img.dataset.shot}-${l}.jpg`; });
    $$(".door-shot img").forEach((img) => { img.src = `assets/shots/match-${l}.jpg`; });
    const cur = $(".tabs [aria-selected=true]");
    if (cur) $("#shot-cap").textContent = t("plat.cap." + cur.dataset.shot);
    buildMarquee();
    try { localStorage.setItem("mm-lang", l); } catch (e) {}
  }
  $$(".lang button").forEach((b) => b.addEventListener("click", () => setLang(b.dataset.lang)));

  function buildMarquee() {
    const words = t("marquee");
    const track = $("#marquee");
    if (!track) return;
    const html = words.map((w) => `<span>${w}</span>`).join("");
    track.innerHTML = html + html;
  }

  /* ---------------- nav / reveal / glow ---------------- */
  const nav = $("#nav");
  const onScroll = () => nav.classList.toggle("scrolled", scrollY > 8);
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      e.target.classList.add("in");
      io.unobserve(e.target);
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
  // stagger siblings
  const groups = new Map();
  $$(".reveal").forEach((el) => {
    const p = el.parentElement;
    const i = groups.get(p) || 0;
    groups.set(p, i + 1);
    el.style.setProperty("--d", `${Math.min(i, 6) * 0.08}s`);
    io.observe(el);
  });

  $$(".glow").forEach((el) => el.addEventListener("pointermove", (e) => {
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - r.left}px`);
    el.style.setProperty("--my", `${e.clientY - r.top}px`);
  }));

  /* steps progress line follows scroll */
  const steps = $("#steps");
  const stepEls = $$(".step", steps);
  function stepProgress() {
    const r = steps.getBoundingClientRect();
    const mid = innerHeight * 0.62;
    const p = Math.max(0, Math.min(1, (mid - r.top) / r.height));
    steps.style.setProperty("--progress", p.toFixed(3));
    stepEls.forEach((s) => {
      const sr = s.getBoundingClientRect();
      s.classList.toggle("lit", sr.top + 24 < mid);
    });
  }
  addEventListener("scroll", stepProgress, { passive: true });
  addEventListener("resize", stepProgress);
  stepProgress();

  /* counters */
  const cio = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      cio.unobserve(e.target);
      const el = e.target, end = +el.dataset.count;
      if (reduced || end === 0) { el.textContent = end; return; }
      const t0 = performance.now(), dur = 1400;
      const tick = (now) => {
        const k = Math.min(1, (now - t0) / dur);
        el.textContent = Math.round(end * (1 - Math.pow(1 - k, 3)));
        if (k < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
  }, { threshold: 0.6 });
  $$("[data-count]").forEach((el) => cio.observe(el));

  /* ---------------- platform tabs ---------------- */
  let autoShots = true;
  function showShot(name) {
    $$(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.shot === name)));
    $$("#shots img").forEach((img) => img.classList.toggle("on", img.dataset.shot === name));
    $("#shot-cap").textContent = t("plat.cap." + name);
  }
  $$(".tabs button").forEach((b) => b.addEventListener("click", () => { autoShots = false; showShot(b.dataset.shot); }));
  const order = ["match", "ligue", "joueur"];
  let shotIdx = 0, shotsVisible = false;
  new IntersectionObserver(([e]) => { shotsVisible = e.isIntersecting; }, { threshold: 0.3 }).observe($("#shots"));
  if (!reduced) setInterval(() => {
    if (!autoShots || !shotsVisible || document.hidden) return;
    shotIdx = (shotIdx + 1) % order.length;
    showShot(order[shotIdx]);
  }, 5000);

  /* ---------------- question card ---------------- */
  const askBtns = $$(".ask-btns button");
  askBtns.forEach((b) => b.addEventListener("click", () => {
    askBtns.forEach((x) => x.classList.toggle("chosen", x === b));
    const done = $("#ask-done");
    done.hidden = false;
    done.style.animation = "none"; void done.offsetWidth; done.style.animation = "";
  }));
  // hint: after a while, Kora "suggests" the answer like it would on the next match
  setTimeout(() => { if (!$(".ask-btns .chosen")) askBtns[0].classList.add("suggested"); }, 4000);

  /* clip: a 3-second loop of a shot going in */
  const clip = $("#clip");
  const cctx = clip.getContext("2d");
  function sizeCanvas(c) {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    const r = c.getBoundingClientRect();
    c.width = Math.max(1, Math.round(r.width * dpr));
    c.height = Math.max(1, Math.round(r.height * dpr));
    return dpr;
  }
  let clipDpr = sizeCanvas(clip);
  function drawClip(ms) {
    const W = clip.width, H = clip.height, k = (ms % 3000) / 3000;
    const g = cctx;
    g.clearRect(0, 0, W, H);
    // grass stripes
    for (let i = 0; i < 8; i++) {
      g.fillStyle = i % 2 ? "#0b2418" : "#0d2a1c";
      g.fillRect((i * W) / 8, 0, W / 8 + 1, H);
    }
    const u = W / 100;
    g.strokeStyle = "rgba(255,255,255,.35)"; g.lineWidth = 1.4 * clipDpr;
    // box + goal on the right
    g.strokeRect(70 * u, H * 0.18, 30 * u, H * 0.64);
    g.strokeRect(88 * u, H * 0.34, 12 * u, H * 0.32);
    g.fillStyle = "rgba(255,255,255,.08)";
    g.fillRect(97 * u, H * 0.4, 3 * u, H * 0.2);
    g.strokeStyle = "rgba(255,255,255,.8)"; g.strokeRect(97 * u, H * 0.4, 3 * u, H * 0.2);
    // players
    const dot = (x, y, c) => { g.beginPath(); g.arc(x, y, 4.2 * clipDpr, 0, 7); g.fillStyle = c; g.shadowColor = c; g.shadowBlur = 10 * clipDpr; g.fill(); g.shadowBlur = 0; };
    const shooterX = 62 + 10 * Math.min(k / 0.35, 1);
    dot(shooterX * u, H * 0.56, "#34d399");
    dot(55 * u, H * 0.3, "#34d399");
    dot(80 * u, H * (0.45 + 0.05 * Math.sin(k * 6)), "#a78bfa");
    dot(84 * u, H * 0.62, "#a78bfa");
    const gkY = 0.5 - 0.12 * Math.max(0, Math.min((k - 0.38) / 0.2, 1));
    dot(96 * u, H * gkY, "#fbbf24");
    // ball
    let bx, by;
    if (k < 0.35) { bx = shooterX + 1.2; by = 0.57; }
    else if (k < 0.62) { const s = (k - 0.35) / 0.27; bx = 73 + 25.5 * s; by = 0.57 - 0.12 * s - 0.08 * Math.sin(s * Math.PI); }
    else { bx = 98.5; by = 0.45; }
    g.beginPath(); g.arc(bx * u, H * by, 3 * clipDpr, 0, 7); g.fillStyle = "#fff"; g.shadowColor = "#fff"; g.shadowBlur = 12 * clipDpr; g.fill(); g.shadowBlur = 0;
    // net ripple
    if (k > 0.62 && k < 0.85) {
      const a = 1 - (k - 0.62) / 0.23;
      g.strokeStyle = `rgba(52,211,153,${a})`; g.lineWidth = 2 * clipDpr;
      g.beginPath(); g.arc(98.5 * u, H * 0.45, (1 - a) * 22 * clipDpr + 4, 0, 7); g.stroke();
    }
    // scanline sweep
    g.fillStyle = "rgba(34,211,238,.05)";
    g.fillRect(0, ((ms / 12) % (H + 40)) - 40, W, 40);
  }

  /* ---------------- hero pitch simulation ---------------- */
  const cv = $("#pitch");
  const ctx = cv.getContext("2d");
  let dpr = sizeCanvas(cv);
  addEventListener("resize", () => { dpr = sizeCanvas(cv); clipDpr = sizeCanvas(clip); draw(performance.now()); drawClip(reduced ? 1900 : performance.now()); });

  const L = 105, Wd = 68;
  const rnd = (a, b) => a + Math.random() * (b - a);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  // base shapes in "own-half" metres (x from own goal line), y across
  const F442 = [[4, 34], [20, 10], [17, 26], [17, 42], [20, 58], [38, 8], [34, 26], [34, 42], [38, 60], [52, 27], [54, 41]];
  const F433 = [[4, 34], [20, 9], [17, 26], [17, 42], [20, 59], [34, 22], [32, 34], [34, 46], [52, 10], [55, 34], [52, 58]];
  const teams = [
    { name: "green", color: "#34d399", dir: 1, shape: F442, players: [] },
    { name: "violet", color: "#a78bfa", dir: -1, shape: F433, players: [] }
  ];
  const nums = [1, 2, 4, 5, 3, 7, 6, 8, 11, 9, 10];
  teams.forEach((tm, ti) => tm.shape.forEach(([x, y], i) => {
    const px = tm.dir === 1 ? x : L - x;
    tm.players.push({ team: ti, i, n: nums[i], x: px, y, tx: px, ty: y, vx: 0, vy: 0, ph: Math.random() * 6 });
  }));
  const all = teams.flatMap((t) => t.players);
  const ball = { x: 52.5, y: 34, holder: teams[0].players[6], from: null, to: null, s: 0, dur: 0, kind: "pass", trail: [] };
  let poss = 0, possTime = [0, 0], nextAction = 1.2, matchSec = 23 * 60 + 41;
  let focusP = null, focusT = 0;

  function targets(dt) {
    const bx = ball.x, by = ball.y;
    teams.forEach((tm, ti) => {
      const attacking = poss === ti;
      // how far the block has moved up: follows the ball along the pitch
      const own = tm.dir === 1 ? bx : L - bx; // ball distance from own goal
      const push = clamp(own - 45, -22, 30) * 0.55 + (attacking ? 9 : -3);
      tm.players.forEach((p, k) => {
        let [sx, sy] = tm.shape[k];
        if (k === 0) { // keeper
          sx = 4 + clamp(push * 0.15, 0, 6);
          sy = 34 + (by - 34) * 0.25;
        } else {
          sx = 4 + (sx - 4) * (attacking ? 0.95 : 0.74) + push;
          sy = 34 + (sy - 34) * (attacking ? 1.05 : 0.72) + (by - 34) * (attacking ? 0.18 : 0.35);
        }
        p.ph += dt;
        sx += Math.sin(p.ph * 0.9 + k) * 1.2;
        sy += Math.cos(p.ph * 0.7 + k * 2) * 1.2;
        p.tx = tm.dir === 1 ? sx : L - sx;
        p.ty = sy;
      });
      // nearest defender presses the ball carrier
      if (!attacking && ball.holder) {
        let best = null, bd = 1e9;
        tm.players.forEach((p, k) => { if (k === 0) return; const d = Math.hypot(p.x - bx, p.y - by); if (d < bd) { bd = d; best = p; } });
        if (best) { best.tx = bx - tm.dir * 1.8; best.ty = by; }
      }
    });
    if (ball.holder) { // carrier dribbles forward
      const h = ball.holder, tm = teams[h.team];
      h.tx = clamp(h.x + tm.dir * 4, 6, L - 6);
      h.ty = h.y + Math.sin(h.ph) * 0.8;
    }
  }

  function move(dt) {
    all.forEach((p) => {
      const isH = ball.holder === p;
      const max = isH ? 5.2 : 6.6;
      let dx = p.tx - p.x, dy = p.ty - p.y;
      const d = Math.hypot(dx, dy) || 1;
      const want = Math.min(max, d * 1.4);
      const ax = (dx / d) * want - p.vx, ay = (dy / d) * want - p.vy;
      p.vx += ax * Math.min(1, dt * 3); p.vy += ay * Math.min(1, dt * 3);
      p.x = clamp(p.x + p.vx * dt, 0.5, L - 0.5);
      p.y = clamp(p.y + p.vy * dt, 0.5, Wd - 0.5);
    });
  }

  const feed = $("#feed");
  function log(kind, a, b) {
    if (!feed) return;
    const li = document.createElement("li");
    const m = Math.floor(matchSec / 60), s = Math.floor(matchSec % 60);
    const col = teams[a.team].color;
    const who = `#${a.n}` + (b ? ` → #${b.n}` : "");
    li.innerHTML = `<span class="t">${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}</span><i class="tag" style="background:${col}"></i><span>${t("feed." + kind)} · <bdi>${who}</bdi></span>`;
    feed.prepend(li);
    while (feed.children.length > 4) feed.lastChild.remove();
  }

  function act() {
    const h = ball.holder;
    if (!h) return;
    const tm = teams[h.team], opp = teams[1 - h.team];
    const towardGoal = tm.dir === 1 ? h.x : L - h.x;
    if (towardGoal > 80 && Math.random() < 0.55) { // shot
      const gx = tm.dir === 1 ? L : 0;
      ball.from = { x: ball.x, y: ball.y }; ball.to = { x: gx, y: 34 + rnd(-3, 3) };
      ball.kind = "shot"; ball.target = opp.players[0];
      ball.s = 0; ball.dur = Math.hypot(ball.to.x - ball.x, ball.to.y - ball.y) / 30;
      ball.holder = null; log("shot", h); focus(h);
      return;
    }
    // choose a team-mate, preferring forward options
    const opts = tm.players.filter((p) => p !== h && p.i !== 0).map((p) => {
      const fwd = (p.x - h.x) * tm.dir;
      const d = Math.hypot(p.x - h.x, p.y - h.y);
      return { p, w: Math.max(0.05, 1 + fwd / 12) * (d > 6 && d < 35 ? 1 : 0.15) };
    });
    let r = Math.random() * opts.reduce((s, o) => s + o.w, 0), to = opts[0].p;
    for (const o of opts) { if ((r -= o.w) <= 0) { to = o.p; break; } }
    let kind = "pass";
    if (Math.random() < 0.16) { // interception by nearest opponent to the pass line midpoint
      const mx = (h.x + to.x) / 2, my = (h.y + to.y) / 2;
      let best = opp.players[1], bd = 1e9;
      opp.players.forEach((p, k) => { if (!k) return; const d = Math.hypot(p.x - mx, p.y - my); if (d < bd) { bd = d; best = p; } });
      to = best; kind = "int";
    }
    ball.from = { x: ball.x, y: ball.y }; ball.target = to; ball.kind = kind;
    ball.to = { x: to.x, y: to.y };
    ball.s = 0; ball.dur = clamp(Math.hypot(to.x - ball.x, to.y - ball.y) / 22, 0.35, 1.6);
    ball.holder = null;
    if (kind === "pass") log("pass", h, to); else log("int", to);
    if (Math.random() < 0.3) focus(to);
  }
  function focus(p) { focusP = p; focusT = 2.2; }

  function step(dt) {
    matchSec += dt * 6;
    possTime[poss] += dt;
    targets(dt);
    move(dt);
    if (ball.holder) {
      const h = ball.holder, tm = teams[h.team];
      ball.x = h.x + tm.dir * 0.9; ball.y = h.y + 0.3;
      nextAction -= dt;
      if (nextAction <= 0) { act(); nextAction = rnd(0.9, 2.1); }
    } else if (ball.to) {
      ball.s += dt / ball.dur;
      const tgt = ball.target;
      if (ball.kind !== "shot" && tgt) { ball.to.x += (tgt.x - ball.to.x) * 0.2; ball.to.y += (tgt.y - ball.to.y) * 0.2; }
      const s = Math.min(1, ball.s), e = 1 - Math.pow(1 - s, 2);
      ball.x = ball.from.x + (ball.to.x - ball.from.x) * e;
      ball.y = ball.from.y + (ball.to.y - ball.from.y) * e;
      if (s >= 1) {
        if (ball.kind === "shot") { log("save", tgt); ball.holder = tgt; poss = tgt.team; }
        else { ball.holder = tgt; poss = tgt.team; }
        ball.to = null; nextAction = rnd(0.5, 1.2);
      }
    }
    ball.trail.push({ x: ball.x, y: ball.y });
    if (ball.trail.length > 26) ball.trail.shift();
    if (focusT > 0) focusT -= dt;
  }

  function hull(pts) {
    const p = pts.slice().sort((a, b) => a.x - b.x || a.y - b.y);
    if (p.length < 3) return p;
    const cross = (o, a, b) => (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
    const lo = [], up = [];
    for (const q of p) { while (lo.length >= 2 && cross(lo[lo.length - 2], lo[lo.length - 1], q) <= 0) lo.pop(); lo.push(q); }
    for (const q of p.reverse()) { while (up.length >= 2 && cross(up[up.length - 2], up[up.length - 1], q) <= 0) up.pop(); up.push(q); }
    return lo.slice(0, -1).concat(up.slice(0, -1));
  }

  function draw(now) {
    const W = cv.width, H = cv.height;
    const pad = 0.035 * W;
    const sx = (W - 2 * pad) / L, sy = (H - 2 * pad) / Wd;
    const X = (x) => pad + x * sx, Y = (y) => pad + y * sy;
    const g = ctx;
    g.clearRect(0, 0, W, H);
    // stripes
    const n = 14;
    for (let i = 0; i < n; i++) {
      g.fillStyle = i % 2 ? "#0a1f15" : "#0c2419";
      g.fillRect(X((i * L) / n), 0, (L / n) * sx + 1, H);
    }
    g.fillStyle = "rgba(0,0,0,.25)";
    g.fillRect(0, 0, W, pad); g.fillRect(0, H - pad, W, pad);
    // lines
    g.strokeStyle = "rgba(255,255,255,.28)"; g.lineWidth = 1.2 * dpr;
    g.strokeRect(X(0), Y(0), L * sx, Wd * sy);
    g.beginPath(); g.moveTo(X(52.5), Y(0)); g.lineTo(X(52.5), Y(Wd)); g.stroke();
    g.beginPath(); g.ellipse(X(52.5), Y(34), 9.15 * sx, 9.15 * sy, 0, 0, 7); g.stroke();
    [[0, 1], [L, -1]].forEach(([x0, d]) => {
      g.strokeRect(Math.min(X(x0), X(x0 + d * 16.5)), Y(13.84), 16.5 * sx, 40.32 * sy);
      g.strokeRect(Math.min(X(x0), X(x0 + d * 5.5)), Y(24.84), 5.5 * sx, 18.32 * sy);
      g.beginPath(); g.ellipse(X(x0 + d * 11), Y(34), 9.15 * sx, 9.15 * sy, 0, d > 0 ? -0.93 : Math.PI - 0.93, d > 0 ? 0.93 : Math.PI + 0.93); g.stroke();
    });

    // team shapes (convex hull of outfield players)
    teams.forEach((tm, ti) => {
      const h = hull(tm.players.slice(1).map((p) => ({ x: X(p.x), y: Y(p.y) })));
      g.beginPath(); h.forEach((q, i) => (i ? g.lineTo(q.x, q.y) : g.moveTo(q.x, q.y))); g.closePath();
      g.fillStyle = ti === 0 ? "rgba(52,211,153,.10)" : "rgba(167,139,250,.07)";
      g.fill();
      g.setLineDash([5 * dpr, 5 * dpr]);
      g.strokeStyle = ti === 0 ? "rgba(52,211,153,.55)" : "rgba(167,139,250,.35)";
      g.lineWidth = 1.2 * dpr; g.stroke(); g.setLineDash([]);
    });

    // green defensive line
    const gp = teams[0].players.slice(1).map((p) => p.x).sort((a, b) => a - b);
    const lineX = (gp[0] + gp[1] + gp[2] + gp[3]) / 4;
    g.strokeStyle = "rgba(34,211,238,.6)"; g.lineWidth = 1.4 * dpr;
    g.setLineDash([2 * dpr, 4 * dpr]);
    g.beginPath(); g.moveTo(X(lineX), Y(1)); g.lineTo(X(lineX), Y(Wd - 1)); g.stroke(); g.setLineDash([]);

    // ball trail
    g.beginPath();
    ball.trail.forEach((q, i) => (i ? g.lineTo(X(q.x), Y(q.y)) : g.moveTo(X(q.x), Y(q.y))));
    g.strokeStyle = "rgba(255,255,255,.22)"; g.lineWidth = 2 * dpr; g.stroke();

    // players
    const r = Math.max(3.2, 0.95 * sx);
    all.forEach((p) => {
      const tm = teams[p.team];
      const col = p.i === 0 ? "#fbbf24" : tm.color;
      const x = X(p.x), y = Y(p.y);
      g.beginPath(); g.arc(x, y, r, 0, 7);
      g.fillStyle = col; g.shadowColor = col; g.shadowBlur = 12 * dpr; g.fill(); g.shadowBlur = 0;
      // tracking brackets
      const b = r * 2.1, c = r * 0.9;
      g.strokeStyle = p === focusP && focusT > 0 ? "rgba(255,255,255,.95)" : "rgba(255,255,255,.22)";
      g.lineWidth = 1 * dpr;
      g.beginPath();
      [[-1, -1], [1, -1], [1, 1], [-1, 1]].forEach(([u, v]) => {
        g.moveTo(x + u * b, y + v * b - v * c); g.lineTo(x + u * b, y + v * b); g.lineTo(x + u * b - u * c, y + v * b);
      });
      g.stroke();
    });
    // focus label
    if (focusP && focusT > 0) {
      const x = X(focusP.x), y = Y(focusP.y) - r * 3.4;
      const label = `#${focusP.n}  ${(0.9 + Math.random() * 0.02 + focusP.i * 0.004).toFixed(2)}`;
      g.font = `600 ${11 * dpr}px Inter, sans-serif`;
      const w = g.measureText(label).width + 12 * dpr;
      g.globalAlpha = Math.min(1, focusT * 2);
      g.fillStyle = "rgba(6,9,18,.85)"; g.strokeStyle = teams[focusP.team].color;
      g.beginPath(); g.roundRect ? g.roundRect(x - w / 2, y - 10 * dpr, w, 18 * dpr, 5 * dpr) : g.rect(x - w / 2, y - 10 * dpr, w, 18 * dpr); g.fill(); g.stroke();
      g.fillStyle = "#fff"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(label, x, y - 1 * dpr);
      g.globalAlpha = 1;
    }
    // ball
    g.beginPath(); g.arc(X(ball.x), Y(ball.y), r * 0.62, 0, 7);
    g.fillStyle = "#fff"; g.shadowColor = "#fff"; g.shadowBlur = 14 * dpr; g.fill(); g.shadowBlur = 0;

    // radar sweep
    const sweep = ((now / 4000) % 1) * (W + 200) - 100;
    const grd = g.createLinearGradient(sweep - 80, 0, sweep, 0);
    grd.addColorStop(0, "rgba(34,211,238,0)"); grd.addColorStop(1, "rgba(34,211,238,.07)");
    g.fillStyle = grd; g.fillRect(sweep - 80, 0, 80, H);
  }

  // metrics in DOM, a few times per second
  const mBlock = $("#m-block"), mLine = $("#m-line"), mPoss = $("#m-poss"), clock = $("#clock");
  function metrics() {
    const ps = teams[0].players.slice(1);
    const xs = ps.map((p) => p.x), ys = ps.map((p) => p.y);
    const depth = Math.max(...xs) - Math.min(...xs), width = Math.max(...ys) - Math.min(...ys);
    const sorted = xs.slice().sort((a, b) => a - b);
    const line = (sorted[0] + sorted[1] + sorted[2] + sorted[3]) / 4;
    mBlock.textContent = `${Math.round(width)} × ${Math.round(depth)} m`;
    mLine.textContent = `${Math.round(line)} m`;
    const tot = possTime[0] + possTime[1] || 1;
    mPoss.textContent = `${Math.round((possTime[0] / tot) * 100)} %`;
    const m = Math.floor(matchSec / 60), s = Math.floor(matchSec % 60);
    clock.textContent = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  // warm the simulation so the first frame already looks like a match
  setLang(pickLang());
  for (let i = 0; i < 240; i++) step(1 / 30);
  possTime = [56, 44];
  metrics();
  draw(performance.now());
  drawClip(1900);

  let last = performance.now(), acc = 0, heroVisible = true, askVisible = false;
  new IntersectionObserver(([e]) => { heroVisible = e.isIntersecting; }, { threshold: 0 }).observe(cv);
  new IntersectionObserver(([e]) => { askVisible = e.isIntersecting; }, { threshold: 0 }).observe(clip);

  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (heroVisible && !document.hidden) {
      step(dt);
      draw(now);
      acc += dt;
      if (acc > 0.25) { metrics(); acc = 0; }
    }
    if (askVisible) drawClip(now);
    requestAnimationFrame(frame);
  }

  if (!reduced) requestAnimationFrame(frame);
})();
