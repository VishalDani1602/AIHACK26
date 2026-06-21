// CareLoop project dashboard — polls /api/dashboard and renders live state.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const displayPrefs = readDisplayPrefs();

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

function renderKpis(st) {
  const cacheHits = (st.nppes_cache_hit || 0) + (st.triage_cache_hit || 0) +
                    (st.ctgov_cache_hit || 0) + (st.openfda_cache_hit || 0);
  const cacheCalls = (st.nppes_api_call || 0) + (st.triage_llm_call || 0) +
                     (st.ctgov_api_call || 0) + (st.openfda_api_call || 0);
  const cards = [
    { v: st.bookings || 0, k: "Appointments booked" },
    { v: st.emergencies || 0, k: "911 escalations", alert: true },
    { v: `${st.payments_paid || 0}/${st.payments_requested || 0}`, k: "Deposits paid / requested" },
    { v: st.evidence_lookups || 0, k: "Clinical-evidence lookups" },
    { v: pct(cacheHits, cacheCalls), k: "Redis cache hit-rate" },
  ];
  $("kpis").innerHTML = cards.map((c) =>
    `<div class="card kpi ${c.alert ? "alert" : ""}"><div class="v">${esc(c.v)}</div><div class="k">${esc(c.k)}</div></div>`
  ).join("");
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

async function refresh() {
  try {
    const d = await (await fetch("/api/dashboard")).json();
    $("tagline").textContent = d.project.tagline;
    $("repo").href = d.project.repo;
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
