// CareLoop voice web app — click-to-talk, record-then-send.
const chat = document.getElementById("chat");
const micBtn = document.getElementById("mic");
const micLabel = micBtn.querySelector(".mic-label");
const statusEl = document.getElementById("status");
const viaEl = document.getElementById("via");
const langSel = document.getElementById("lang");
const player = document.getElementById("player");
const textInput = document.getElementById("textInput");
const sendBtn = document.getElementById("sendBtn");
const composer = document.querySelector(".composer");
const meterBars = Array.from(document.querySelectorAll(".voice-meter span"));

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
  bubble.className = "bubble";
  bubble.innerHTML = opts.emergency ? renderEmergency(text) : render(text);
  wrap.appendChild(bubble);
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
  return bubble;
}

function addThinkingBubble() {
  const wrap = document.createElement("div");
  wrap.className = "msg bot thinking";
  wrap.innerHTML = `
    <div class="bubble">
      <span>CareLoop is thinking</span>
      <span class="typing-dots" aria-hidden="true"><span></span><span></span><span></span></span>
    </div>
  `;
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
  return wrap;
}

// Minimal markdown: **bold**, clickable links, and newlines.
function render(t) {
  const esc = t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return esc
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>')
    .replace(/\n/g, "<br>");
}

function setStatus(s) { statusEl.textContent = s; }

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
    addMessage("bot", data.reply, { emergency: data.emergency });
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

function escapeAttr(value) {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
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
