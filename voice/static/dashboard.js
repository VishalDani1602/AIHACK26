// CareLoop project dashboard — polls /api/dashboard and renders live state.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const displayPrefs = readDisplayPrefs();
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const kpiValues = new Map();
const cacheHistory = [];

function readDisplayPrefs() {
  try {
    return JSON.parse(localStorage.getItem("careloopDisplayPrefs") || "{}");
  } catch (e) {
    return {};
  }
}

document.body.classList.toggle("large-text", Boolean(displayPrefs.largeText));
document.body.classList.toggle("high-contrast", Boolean(displayPrefs.highContrast));
document.body.classList.toggle("dark-mode", Boolean(displayPrefs.darkMode));

function pct(hits, calls) {
  const tot = hits + calls;
  return tot ? Math.round((hits / tot) * 100) + "%" : "—";
}

function pctNumber(hits, calls) {
  const tot = hits + calls;
  return tot ? Math.round((hits / tot) * 100) : 0;
}

function renderSparkline(points) {
  const safePoints = points.length > 1 ? points : [0, points[0] || 0];
  const width = 120;
  const height = 26;
  const max = Math.max(100, ...safePoints);
  const step = width / Math.max(1, safePoints.length - 1);
  const coords = safePoints.map((value, index) => {
    const x = Math.round(index * step);
    const y = Math.round(height - (Math.min(value, max) / max) * height);
    return `${x},${y}`;
  });
  return `
    <svg class="sparkline" viewBox="0 0 ${width} ${height}" aria-hidden="true">
      <path d="M0,${height} L${coords.join(" L")} L${width},${height} Z"></path>
      <polyline points="${coords.join(" ")}"></polyline>
    </svg>
  `;
}

function animateKpis(cards) {
  cards.forEach((card) => {
    const el = document.querySelector(`[data-kpi-id="${card.id}"]`);
    if (!el) return;
    const from = kpiValues.has(card.id) ? kpiValues.get(card.id) : 0;
    const to = Number(card.value) || 0;
    const suffix = card.suffix || "";
    const prefix = card.prefix || "";
    const duration = reduceMotion.matches ? 0 : 700;
    const started = Date.now();
    const format = (value) => `${prefix}${Math.round(value)}${suffix}`;

    function tick() {
      const elapsed = Date.now() - started;
      const progress = duration ? Math.min(1, elapsed / duration) : 1;
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = format(from + (to - from) * eased);
      if (progress < 1) requestAnimationFrame(tick);
    }

    tick();
    kpiValues.set(card.id, to);
  });
}

function renderKpis(st) {
  const cacheHits = (st.nppes_cache_hit || 0) + (st.triage_cache_hit || 0) +
                    (st.ctgov_cache_hit || 0) + (st.openfda_cache_hit || 0);
  const cacheCalls = (st.nppes_api_call || 0) + (st.triage_llm_call || 0) +
                     (st.ctgov_api_call || 0) + (st.openfda_api_call || 0);
  const cacheRate = pctNumber(cacheHits, cacheCalls);
  cacheHistory.push(cacheRate);
  if (cacheHistory.length > 18) cacheHistory.shift();
  const cards = [
    { id: "bookings", value: st.bookings || 0, k: "Appointments booked" },
    { id: "emergencies", value: st.emergencies || 0, k: "911 escalations", alert: true },
    { id: "payments", value: st.payments_paid || 0, suffix: `/${st.payments_requested || 0}`, k: "Deposits paid / requested" },
    { id: "evidence", value: st.evidence_lookups || 0, k: "Clinical-evidence lookups" },
    { id: "cache", value: cacheRate, suffix: "%", k: "Redis cache hit-rate", sparkline: true },
  ];
  $("kpis").innerHTML = cards.map((c) =>
    `<div class="card kpi ${c.alert ? "alert" : ""}">
      <div>
        <div class="v" data-kpi-id="${esc(c.id)}">0${esc(c.suffix || "")}</div>
        <div class="k">${esc(c.k)}</div>
      </div>
      ${c.sparkline ? renderSparkline(cacheHistory) : ""}
    </div>`
  ).join("");
  animateKpis(cards);
}

function renderAgents(agents) {
  const up = agents.filter((a) => a.online).length;
  $("agentsUp").textContent = `(${up}/${agents.length} online)`;
  $("agents").innerHTML = agents.map((a) => `
    <div class="card agent">
      <div class="top"><span class="dot ${a.online ? "ok" : ""}"></span>
        <span class="name">${esc(a.name)}</span>
        <span class="muted">:${a.port}</span></div>
      <div class="role">${esc(a.role)}</div>
      <a href="https://agentverse.ai/agents/details/${esc(a.address)}/profile" target="_blank">${esc(a.address.slice(0, 30))}…</a>
    </div>`).join("");
}

function renderStack(stack) {
  $("stack").innerHTML = stack.map((g) => `
    <div class="card">
      <h3>${esc(g.group)}</h3>
      ${g.items.map((i) => `<span class="chip">${esc(i.name)} <span>— ${esc(i.detail)}</span></span>`).join("")}
    </div>`).join("");
}

function renderAudit(audit) {
  if (!audit.length) { $("audit").innerHTML = '<span class="muted">No events yet — run a conversation.</span>'; return; }
  $("audit").innerHTML = audit.map((e) => {
    const meta = Object.entries(e).filter(([k]) => !["id", "event"].includes(k))
      .map(([k, v]) => `${k}=${v}`).join("  ");
    const cls = e.event === "emergency" ? "emergency" : "";
    return `<div class="ev"><span class="badge ${cls}">${esc(e.event || "?")}</span><span class="meta">${esc(meta)}</span></div>`;
  }).join("");
}

function renderLLMs(llms, stats) {
  const claudeCount = (stats || {}).triage_engine_claude || 0;
  const claude = Boolean(llms.triage_via_claude);
  const pills = [
    `<span class="llm-pill"><b>Orchestrator</b> <span class="mini">${esc(llms.orchestrator || "ASI:One")}</span></span>`,
    `<span class="llm-pill ${claude ? "claude" : ""}"><b>Triage</b> <span class="mini">${esc(llms.triage || "ASI:One")}</span>` +
      (claudeCount ? ` <span class="mini">· ${claudeCount} calls</span>` : "") + `</span>`,
  ];
  $("llmbar").innerHTML = pills.join("");
}

function archNode(n, cls) {
  const dot = `<span class="dot ${n.online ? "ok" : ""}"></span>`;
  const uses = n.uses
    ? `<span class="arch-uses ${/claude/i.test(n.uses) ? "claude" : ""}">${esc(n.uses)}</span>` : "";
  return `<div class="arch-node ${cls || ""}"><div class="nm">${dot}${esc(n.name)}</div>` +
         `<div class="does">${esc(n.does || "")}</div>${uses}</div>`;
}

function renderArchitecture(a) {
  if (!a || !a.orchestrator) { $("arch").innerHTML = ""; return; }
  const entries = (a.entrypoints || []).map((e) =>
    `<div class="arch-node arch-entry"><div class="nm">${esc(e.name)}</div>` +
    `<div class="does">${esc(e.desc || "")}</div>` +
    (e.via ? `<span class="arch-uses">${esc(e.via)}</span>` : "") + `</div>`).join("");
  const specialists = (a.specialists || []).map((s) => archNode(s)).join("");
  const shared = (a.shared || []).map((s) =>
    `<span class="pill"><b>${esc(s.name)}</b> — ${esc(s.desc || "")}</span>`).join("");
  $("arch").innerHTML =
    `<div class="arch-row">${entries}</div>` +
    `<div class="arch-arrow">▼</div>` +
    archNode(a.orchestrator, "arch-orch") +
    `<div class="arch-arrow">▼&nbsp; orchestrates specialists via Agentverse (send_and_receive) &nbsp;▼</div>` +
    `<div class="arch-grid">${specialists}</div>` +
    `<div class="arch-arrow">shared infrastructure</div>` +
    `<div class="arch-shared">${shared}</div>`;
}

async function refresh() {
  try {
    const d = await (await fetch("/api/dashboard")).json();
    $("tagline").textContent = d.project.tagline;
    $("repo").href = d.project.repo;
    renderLLMs(d.llms || {}, d.redis.stats || {});
    renderArchitecture(d.architecture || {});
    renderKpis(d.redis.stats || {});
    renderAgents(d.agents || []);
    renderStack(d.stack || []);
    renderAudit(d.audit || []);
    const onlineAll = (d.agents || []).every((a) => a.online);
    $("liveDot").className = "dot " + (onlineAll ? "ok" : "");
    $("liveText").textContent = onlineAll
      ? `all systems live${d.redis.enabled ? " · redis" : ""}${d.health.deepgram ? " · deepgram" : ""}`
      : "degraded — some agents offline";
  } catch (e) {
    $("liveDot").className = "dot";
    $("liveText").textContent = "backend unreachable";
  }
}

refresh();
setInterval(refresh, 3000);
