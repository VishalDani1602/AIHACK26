// CareLoop voice web app — click-to-talk, record-then-send.
const chat = document.getElementById("chat");
const micBtn = document.getElementById("mic");
const micLabel = micBtn.querySelector(".mic-label");
const statusEl = document.getElementById("status");
const srUpdates = document.getElementById("srUpdates");
const viaEl = document.getElementById("via");
const langSel = document.getElementById("lang");
const player = document.getElementById("player");
const textInput = document.getElementById("textInput");
const sendBtn = document.getElementById("sendBtn");
const composer = document.querySelector(".composer");
const meterBars = Array.from(document.querySelectorAll(".voice-meter span"));
const largeTextToggle = document.getElementById("largeTextToggle");
const contrastToggle = document.getElementById("contrastToggle");
const reduceMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

let sessionId = "web-" + Math.random().toString(36).slice(2, 10);
let mediaRecorder = null;
let chunks = [];
let recording = false;
let busy = false;
let emergencyFocusTimer = null;
let audioContext = null;
let analyser = null;
let meterFrame = null;
let meterData = null;
const DISPLAY_PREF_KEY = "careloopDisplayPrefs";
const displayPrefs = readDisplayPrefs();

const EXAMPLE_PROMPTS = [
  "My dad has a bad cough and fever",
  "Find a cardiologist near me",
  "My mom was diagnosed with diabetes",
  "I have chest pain",
];

function addMessage(role, text, opts = {}) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + role + (opts.emergency ? " emergency" : "");
  const bubble = document.createElement("div");
  bubble.className = "bubble" + (opts.rich ? " rich-bubble" : "");
  bubble.innerHTML = opts.emergency ? renderEmergency(text) : renderMessageBody(text, opts);
  wrap.appendChild(bubble);
  chat.appendChild(wrap);
  scrollChatToEnd();
  return bubble;
}

function addThinkingBubble() {
  const wrap = document.createElement("div");
  wrap.className = "msg bot thinking";
  wrap.innerHTML = `
    <div class="bubble" role="status" aria-live="polite">
      <span class="thinking-label">CareLoop is thinking</span>
      <span class="typing-dots" aria-hidden="true"><span></span><span></span><span></span></span>
      <span class="thinking-skeleton" aria-hidden="true"><span></span><span></span></span>
    </div>
  `;
  chat.appendChild(wrap);
  scrollChatToEnd();
  return wrap;
}

// Minimal markdown: **bold**, clickable links, and newlines.
function render(t) {
  return escapeHtml(t)
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>')
    .replace(/\n/g, "<br>");
}

function renderMessageBody(text, opts = {}) {
  const cardsHtml = opts.cards?.length ? `<div class="card-stack">${opts.cards.map(renderCard).join("")}</div>` : "";
  const actionsHtml = opts.actions?.length ? renderActions(opts.actions) : "";
  if (!cardsHtml && !actionsHtml) return render(text);
  const summary = cardsHtml ? `<details class="reply-details"><summary>Conversation note</summary>${render(text)}</details>` : render(text);
  return `${summary}${cardsHtml}${actionsHtml}`;
}

function setStatus(s) { statusEl.textContent = s; }

function scrollChatToEnd() {
  requestAnimationFrame(() => {
    chat.scrollTo({
      top: chat.scrollHeight,
      behavior: reduceMotionQuery.matches ? "auto" : "smooth",
    });
  });
}

function playAudio(b64) {
  if (!b64) return;
  player.src = "data:audio/mpeg;base64," + b64;
  player.play().catch(() => {});
}

async function sendTurn(promise, opts = {}) {
  if (busy) return;
  busy = true;
  micBtn.classList.add("disabled");
  if (opts.userText) addMessage("user", opts.userText);
  const thinking = addThinkingBubble();
  try {
    const res = await promise;
    const data = await res.json();
    thinking.remove();
    if (data.error) { setStatus("Warning: " + data.error); return; }
    if (data.transcript && data.transcript !== opts.userText) addMessage("user", data.transcript);
    addBotReply(data);
    setEmergencyFocus(Boolean(data.emergency));
    viaEl.textContent = data.via ? "routed via: " + data.via : "";
    playAudio(data.audio);
    setStatus("");
  } catch (e) {
    thinking.remove();
    setStatus("Network error: " + e.message);
  } finally {
    busy = false;
    micBtn.classList.remove("disabled");
  }
}

function addBotReply(data) {
  announceBotReply(data.reply);
  if (data.emergency) {
    addMessage("bot", data.reply, { emergency: true });
    return;
  }
  const cards = collectCards(data);
  const actions = normalizeActions(data.actions) || inferActions(data, cards);
  addMessage("bot", data.reply, { cards, actions, rich: Boolean(cards.length || actions.length) });
}

function renderEmergency(text) {
  return `
    <section class="emergency-card" role="alert" aria-label="Emergency guidance">
      <div class="emergency-mark" aria-hidden="true">!</div>
      <div class="emergency-copy">
        <h2>Emergency care now</h2>
        <p>If this is happening now, call emergency services immediately.</p>
        <div class="emergency-detail">${render(text)}</div>
        <a class="call911" href="tel:911">Call 911</a>
      </div>
    </section>
  `;
}

function collectCards(data) {
  if (data.card) return [data.card];
  return [
    inferProviderCard(data.reply, data.stage),
    inferEvidenceCard(data.reply),
    inferPaymentCard(data.reply, data.stage),
    inferBookingCard(data.reply, data.stage),
  ].filter(Boolean);
}

function renderCard(card) {
  if (card.type === "provider") return renderProviderCard(card);
  if (card.type === "trials") return renderTrialsCard(card);
  if (card.type === "payment") return renderPaymentCard(card);
  if (card.type === "booking") return renderBookingCard(card);
  if (card.type === "cost") return renderCostChip(card.cost || card);
  return "";
}

function renderProviderCard(card) {
  const provider = card.provider || {};
  const cost = card.cost || {};
  const badge = provider.accepts_insurance === false ? "Confirm plan" : "Accepts your plan";
  const badgeClass = provider.accepts_insurance === false ? "warn" : "";
  return `
    <section class="care-card provider-card" aria-label="Recommended provider">
      <div class="card-title-row">
        <div>
          <h3>${escapeHtml(provider.name || "Recommended provider")}</h3>
          <p>${escapeHtml(provider.specialty || "Care provider")}</p>
        </div>
        <span class="plan-badge ${badgeClass}">${badge}</span>
      </div>
      <div class="card-rows">
        ${renderInfoRow("Address", provider.address)}
        ${renderInfoRow("Next", provider.next_slot)}
        ${cost.low || cost.high || cost.label ? renderInfoRow("Cost", renderCostChip(cost), true) : ""}
      </div>
    </section>
  `;
}

function renderTrialsCard(card) {
  const trials = card.trials || [];
  if (!trials.length) return "";
  return `
    <details class="care-card trial-group" open>
      <summary>Clinical evidence (${trials.length})</summary>
      <div class="trial-list">
        ${trials.map((trial) => `
          <a class="trial-card" href="${escapeAttr(trial.url || "#")}" target="_blank" rel="noopener">
            <span class="trial-title">${escapeHtml(trial.title || "Clinical trial")}</span>
            <span class="trial-meta">
              ${trial.phase ? `<span class="phase-chip">${escapeHtml(trial.phase)}</span>` : ""}
              ${escapeHtml(trial.location || "ClinicalTrials.gov")}
            </span>
          </a>
        `).join("")}
      </div>
    </details>
  `;
}

function renderPaymentCard(card) {
  const payment = card.payment || card;
  return `
    <section class="care-card payment-card" aria-label="Payment step">
      <h3>Hold the appointment</h3>
      <p>${escapeHtml(payment.amount_usd ? `Refundable deposit: $${payment.amount_usd}` : "Secure Stripe checkout")}</p>
      ${payment.checkout_url ? `<a class="card-link primary" href="${escapeAttr(payment.checkout_url)}" target="_blank" rel="noopener">Open Stripe checkout</a>` : ""}
    </section>
  `;
}

function renderBookingCard(card) {
  const booking = card.booking || card;
  return `
    <section class="care-card booking-card" aria-label="Booking confirmation">
      <div class="card-title-row">
        <div>
          <h3>Booking confirmed</h3>
          <p>${escapeHtml(booking.confirmation_code || "Confirmation ready")}</p>
        </div>
        <span class="plan-badge">Booked</span>
      </div>
      <div class="card-rows">
        ${renderInfoRow("Provider", booking.provider_name)}
        ${renderInfoRow("When", booking.date)}
        ${renderInfoRow("Where", booking.address)}
      </div>
      <a class="card-link primary" href="/api/ics/${encodeURIComponent(sessionId)}">Add to calendar</a>
    </section>
  `;
}

function renderCostChip(cost) {
  const low = Number(cost.low || cost.estimate_low || 0);
  const high = Number(cost.high || cost.estimate_high || 0);
  const label = cost.label || (low || high ? `$${low || high}-${high || low}` : "Cost estimate");
  const title = cost.explanation || "Estimate depends on copay, deductible, and coinsurance.";
  return `<span class="cost-chip" title="${escapeAttr(title)}">${escapeHtml(label)}</span>`;
}

function renderInfoRow(label, value, isHtml = false) {
  if (!value) return "";
  return `
    <div class="info-row">
      <span>${escapeHtml(label)}</span>
      <strong>${isHtml ? value : escapeHtml(value)}</strong>
    </div>
  `;
}

function renderActions(actions) {
  return `
    <div class="quick-actions">
      ${actions.map((action) => `
        <button type="button" data-send="${escapeAttr(action.send)}" class="${action.primary ? "primary" : ""}" aria-label="${escapeAttr(action.label)}">
          ${escapeHtml(action.label)}
        </button>
      `).join("")}
    </div>
  `;
}

function normalizeActions(actions) {
  if (!Array.isArray(actions) || !actions.length) return null;
  return actions.filter((action) => action?.label && action?.send);
}

function inferActions(data, cards) {
  if (data.stage === "confirming" && cards.some((card) => card.type === "provider")) {
    return [
      { label: "Book this", send: "yes", primary: true },
      { label: "Different time", send: "different time" },
      { label: "Another provider", send: "another provider" },
    ];
  }
  if (data.stage === "awaiting_payment" || cards.some((card) => card.type === "payment")) {
    return [
      { label: "Payment done", send: "done", primary: true },
      { label: "Skip deposit", send: "skip" },
    ];
  }
  return [];
}

function inferProviderCard(text, stage) {
  if (stage !== "confirming") return null;
  const match = text.match(/\*\*([^*]+)\*\*\s*\(([^)]+)\)\s+at\s+([\s\S]+?),\s+with an opening\s+\*\*([^*]+)\*\*/i);
  if (!match) return null;
  return {
    type: "provider",
    provider: {
      name: match[1],
      specialty: match[2],
      address: match[3].replace(/\s+/g, " ").trim(),
      next_slot: match[4],
      accepts_insurance: !/confirm they take your plan/i.test(text),
    },
    cost: inferCost(text),
  };
}

function inferCost(text) {
  const costMatch = text.match(/\$\s*(\d+(?:\.\d+)?)\s*[–-]\s*\$\s*(\d+(?:\.\d+)?)/);
  if (!costMatch) return {};
  const costContext = text.slice(costMatch.index + costMatch[0].length, costMatch.index + costMatch[0].length + 180);
  const planMatch = costContext.match(/With ([^(.]+)/i);
  const explanation = (text.match(/Estimated cost:[\s\S]*?\.\s*([^\n]+)/i) || [])[1] || "";
  return {
    low: Number(costMatch[1]),
    high: Number(costMatch[2]),
    label: `$${costMatch[1]}-$${costMatch[2]}${planMatch ? ` with ${planMatch[1].trim()}` : ""}`,
    explanation,
  };
}

function inferEvidenceCard(text) {
  const trials = [];
  const trialRegex = /Trial:\s*([^\n(]+?)\s*\(([^)]*)\)(?:\s*[\u2014-]\s*([^\n]+))?\n\s*(https?:\/\/[^\s<]+)/g;
  let match;
  while ((match = trialRegex.exec(text)) !== null) {
    trials.push({
      title: match[1].trim(),
      phase: match[2].trim(),
      location: (match[3] || "").trim(),
      url: match[4],
    });
  }
  return trials.length ? { type: "trials", trials } : null;
}

function inferPaymentCard(text, stage) {
  if (stage !== "awaiting_payment" && !/Stripe|deposit/i.test(text)) return null;
  const urls = text.match(/https?:\/\/[^\s<]+/g) || [];
  const checkoutUrl = urls.find((url) => url.includes("stripe")) || urls[0] || "";
  if (!checkoutUrl) return null;
  const amount = (text.match(/refundable \$(\d+(?:\.\d+)?) deposit/i) || [])[1];
  return { type: "payment", payment: { checkout_url: checkoutUrl, amount_usd: amount ? Number(amount) : 0 } };
}

function inferBookingCard(text, stage) {
  if (stage !== "done" && !/Confirmation CL-/i.test(text)) return null;
  const code = (text.match(/Confirmation\s+(CL-[A-Z0-9]+)/) || [])[1];
  if (!code) return null;
  const provider =
    (text.match(/Booked:\s*([\s\S]+?)\s*[\u2014-]\s*/) || [])[1]?.trim() ||
    (text.match(/Booked:\s*([\s\S]+?)\.\s*[A-Z][a-z]+day,/) || [])[1]?.trim() ||
    "";
  const address = (text.match(/Booked:[\s\S]+?[\u2014-]\s*([\s\S]+?)\.\s*[A-Z][a-z]+day,/) || [])[1]?.trim() || "";
  const date = (text.match(/\.\s*([A-Z][a-z]+day,[^.]+)\.\s*Confirmation/) || [])[1]?.trim() || "";
  return { type: "booking", booking: { confirmation_code: code, provider_name: provider, address, date } };
}

function renderPromptChips() {
  return `
    <div class="prompt-chips" aria-label="Example prompts">
      ${EXAMPLE_PROMPTS.map((prompt) => (
        `<button type="button" data-prompt="${escapeAttr(prompt)}">${render(prompt)}</button>`
      )).join("")}
    </div>
  `;
}

function clearPromptChips() {
  chat.querySelectorAll(".prompt-chips").forEach((el) => el.remove());
}

function escapeHtml(value) {
  return String(value || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function escapeAttr(value) {
  return String(value || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

function readDisplayPrefs() {
  try {
    return { largeText: false, highContrast: false, ...JSON.parse(localStorage.getItem(DISPLAY_PREF_KEY) || "{}") };
  } catch (e) {
    return { largeText: false, highContrast: false };
  }
}

function saveDisplayPrefs() {
  localStorage.setItem(DISPLAY_PREF_KEY, JSON.stringify(displayPrefs));
}

function applyDisplayPrefs() {
  document.body.classList.toggle("large-text", displayPrefs.largeText);
  document.body.classList.toggle("high-contrast", displayPrefs.highContrast);
  largeTextToggle?.setAttribute("aria-pressed", String(displayPrefs.largeText));
  contrastToggle?.setAttribute("aria-pressed", String(displayPrefs.highContrast));
}

function toggleDisplayPref(key) {
  displayPrefs[key] = !displayPrefs[key];
  saveDisplayPrefs();
  applyDisplayPrefs();
}

function plainText(value) {
  const div = document.createElement("div");
  div.innerHTML = render(value || "");
  return div.textContent.replace(/\s+/g, " ").trim();
}

function announceBotReply(text) {
  if (!srUpdates) return;
  srUpdates.textContent = "";
  window.setTimeout(() => {
    srUpdates.textContent = plainText(text).slice(0, 900);
  }, 20);
}

function setEmergencyFocus(active) {
  if (emergencyFocusTimer) clearTimeout(emergencyFocusTimer);
  composer.classList.toggle("composer-emergency", active);
  if (active) {
    emergencyFocusTimer = setTimeout(() => {
      composer.classList.remove("composer-emergency");
    }, 8000);
  }
}

async function sendText() {
  const text = textInput.value.trim();
  if (!text) return;
  textInput.value = "";
  clearPromptChips();
  setStatus("Thinking");
  await sendTurn(fetch("/api/text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, text }),
  }), { userText: text });
}

sendBtn.onclick = sendText;
textInput.addEventListener("keydown", (e) => { if (e.key === "Enter") sendText(); });
largeTextToggle?.addEventListener("click", () => toggleDisplayPref("largeText"));
contrastToggle?.addEventListener("click", () => toggleDisplayPref("highContrast"));
applyDisplayPrefs();

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    startVoiceMeter(stream);
    mediaRecorder = new MediaRecorder(stream, { mimeType: pickMime() });
    chunks = [];
    mediaRecorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      stopVoiceMeter();
      const blob = new Blob(chunks, { type: mediaRecorder.mimeType });
      setStatus("Transcribing and thinking");
      const lang = langSel.value;
      await sendTurn(fetch(`/api/converse?session_id=${sessionId}&language=${lang}`, {
        method: "POST",
        headers: { "Content-Type": blob.type },
        body: blob,
      }));
    };
    mediaRecorder.start();
    recording = true;
    micBtn.classList.add("recording");
    micBtn.setAttribute("aria-label", "Stop voice recording");
    micLabel.textContent = "Listening - tap to stop";
    setStatus("Recording");
  } catch (e) {
    setStatus("Microphone access denied: " + e.message);
  }
}

function stopRecording() {
  if (mediaRecorder && recording) {
    mediaRecorder.stop();
    recording = false;
    micBtn.classList.remove("recording");
    micBtn.setAttribute("aria-label", "Start voice recording");
    micLabel.textContent = "Speak";
  }
}

function startVoiceMeter(stream) {
  stopVoiceMeter();
  const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextCtor || !meterBars.length) return;
  try {
    audioContext = new AudioContextCtor();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 128;
    analyser.smoothingTimeConstant = 0.68;
    meterData = new Uint8Array(analyser.frequencyBinCount);
    audioContext.createMediaStreamSource(stream).connect(analyser);
    drawVoiceMeter();
  } catch (e) {
    stopVoiceMeter();
  }
}

function drawVoiceMeter() {
  if (!analyser || !meterData) return;
  analyser.getByteFrequencyData(meterData);
  const bandSize = Math.max(1, Math.floor(meterData.length / meterBars.length));
  meterBars.forEach((bar, index) => {
    const start = index * bandSize;
    const end = Math.min(meterData.length, start + bandSize);
    let total = 0;
    for (let i = start; i < end; i += 1) total += meterData[i];
    const level = total / Math.max(1, end - start) / 255;
    bar.style.transform = `scaleY(${Math.max(0.18, Math.min(1, level * 1.8))})`;
  });
  meterFrame = requestAnimationFrame(drawVoiceMeter);
}

function stopVoiceMeter() {
  if (meterFrame) cancelAnimationFrame(meterFrame);
  meterFrame = null;
  meterBars.forEach((bar) => { bar.style.transform = ""; });
  if (audioContext) audioContext.close().catch(() => {});
  audioContext = null;
  analyser = null;
  meterData = null;
}

function pickMime() {
  const prefs = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
  for (const m of prefs) if (window.MediaRecorder && MediaRecorder.isTypeSupported(m)) return m;
  return "";
}

micBtn.onclick = () => {
  if (busy) return;
  recording ? stopRecording() : startRecording();
};

chat.addEventListener("click", (event) => {
  const action = event.target.closest("[data-send]");
  if (action && !busy) {
    action.closest(".quick-actions")?.querySelectorAll("button").forEach((button) => {
      button.disabled = true;
    });
    textInput.value = action.dataset.send;
    sendText();
    return;
  }
  const chip = event.target.closest("[data-prompt]");
  if (!chip || busy) return;
  textInput.value = chip.dataset.prompt;
  sendText();
});

// New chat: fresh session id (server keys state by session, so this fully resets) + clear UI.
const GREETING_HTML =
  "Hi, I'm <b>CareLoop</b>. Tell me what's going on, who it is for, and where to search." +
  '<div class="note">Not medical advice. For an emergency, call 911.</div>';

function resetChat() {
  if (recording) stopRecording();
  setEmergencyFocus(false);
  sessionId = "web-" + Math.random().toString(36).slice(2, 10);
  chat.innerHTML = "";
  const wrap = document.createElement("div");
  wrap.className = "msg bot";
  wrap.innerHTML = '<div class="bubble">' + GREETING_HTML + "</div>";
  chat.appendChild(wrap);
  chat.insertAdjacentHTML("beforeend", renderPromptChips());
  scrollChatToEnd();
  setStatus("New conversation started");
  viaEl.textContent = "";
  textInput.value = "";
}
document.getElementById("newChat").onclick = resetChat;

// Surface backend config on load (helps during the demo).
fetch("/api/health").then((r) => r.json()).then((h) => {
  if (!h.deepgram_key) setStatus("Deepgram key missing - voice is disabled, typing still works.");
}).catch(() => {});

// Live Redis-backed stats (beyond caching: counters + cache hit-rate).
const statsEl = document.getElementById("stats");
async function pollStats() {
  try {
    const s = await (await fetch("/api/stats")).json();
    if (!s.redis) { statsEl.textContent = ""; return; }
    const st = s.stats || {};
    const hits = st.nppes_cache_hit || 0, calls = st.nppes_api_call || 0;
    const thits = st.triage_cache_hit || 0, tcalls = st.triage_llm_call || 0;
    statsEl.innerHTML =
      `Redis | bookings ${st.bookings || 0} | emergencies ${st.emergencies || 0} ` +
      `| deposits ${st.payments_paid || 0}/${st.payments_requested || 0} ` +
      `| provider cache ${hits}/${hits + calls} | triage cache ${thits}/${thits + tcalls}`;
  } catch (e) { /* ignore */ }
}
pollStats();
setInterval(pollStats, 4000);
