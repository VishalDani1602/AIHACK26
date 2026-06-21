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

const sessionId = "web-" + Math.random().toString(36).slice(2, 10);
let mediaRecorder = null;
let chunks = [];
let recording = false;
let busy = false;

function addMessage(role, text, opts = {}) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + role + (opts.emergency ? " emergency" : "");
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = render(text);
  wrap.appendChild(bubble);
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
  return bubble;
}

// Minimal markdown: **bold** and newlines.
function render(t) {
  const esc = t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return esc.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\n/g, "<br>");
}

function setStatus(s) { statusEl.textContent = s; }

function playAudio(b64) {
  if (!b64) return;
  player.src = "data:audio/mpeg;base64," + b64;
  player.play().catch(() => {});
}

async function sendTurn(promise) {
  if (busy) return;
  busy = true;
  micBtn.classList.add("disabled");
  try {
    const res = await promise;
    const data = await res.json();
    if (data.error) { setStatus("⚠️ " + data.error); return; }
    if (data.transcript) addMessage("user", data.transcript);
    addMessage("bot", data.reply, { emergency: data.emergency });
    viaEl.textContent = data.via ? "routed via: " + data.via : "";
    playAudio(data.audio);
    setStatus("");
  } catch (e) {
    setStatus("⚠️ Network error: " + e.message);
  } finally {
    busy = false;
    micBtn.classList.remove("disabled");
  }
}

async function sendText() {
  const text = textInput.value.trim();
  if (!text) return;
  textInput.value = "";
  setStatus("Thinking…");
  await sendTurn(fetch("/api/text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, text }),
  }));
}

sendBtn.onclick = sendText;
textInput.addEventListener("keydown", (e) => { if (e.key === "Enter") sendText(); });

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream, { mimeType: pickMime() });
    chunks = [];
    mediaRecorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunks, { type: mediaRecorder.mimeType });
      setStatus("Transcribing & thinking…");
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
    micLabel.textContent = "Listening… click to stop";
    setStatus("Recording…");
  } catch (e) {
    setStatus("⚠️ Microphone access denied: " + e.message);
  }
}

function stopRecording() {
  if (mediaRecorder && recording) {
    mediaRecorder.stop();
    recording = false;
    micBtn.classList.remove("recording");
    micLabel.textContent = "Click to talk";
  }
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

// Surface backend config on load (helps during the demo).
fetch("/api/health").then((r) => r.json()).then((h) => {
  if (!h.deepgram_key) setStatus("⚠️ DEEPGRAM_API_KEY not set — voice is disabled, typing still works.");
}).catch(() => {});
