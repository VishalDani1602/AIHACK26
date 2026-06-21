# CareLoop — Pitch script (3–4 min) + Judge Q&A

**Roles:** **S1 = product/host** · **S2 = technical** (drives the live demo).
**Setup before you start:** voice app open at `http://127.0.0.1:8080`, dashboard open in a
second tab at `/dashboard`, mic working. Lead with the **voice app** (it's local and
can't be broken by flaky Wi-Fi); show ASI:One only if the network is solid.

---

## The script (~600 words ≈ 3.5–4 min)

### 0:00 — Hook (S1)
"Raise your hand if you've ever had to find a doctor for a sick parent. Now imagine
doing it at 70, in your second language, scared. The hard part of healthcare usually
isn't the medicine — it's the **navigation**: *Who do I see? Is it urgent? Who's nearby
and takes my insurance? What'll it cost? How do I book it?* That maze is where people
give up, delay care, or end up in the ER. We built **CareLoop** to collapse that maze
into one calm conversation you can have **out loud, in your own language**."

### 0:30 — What it is (S1)
"CareLoop is a **voice-first team of AI agents** that takes you from a spoken symptom
all the way to a **booked appointment** — and it actually takes action, it's not a
chatbot. Let me show you."

### 0:45 — Live demo (S2 drives, S1 narrates)
1. **Voice golden path.** S2 taps the mic: *"My dad's had a bad cough and fever for five
   days, he's on Medicare in San Francisco."*
   → S1: "It transcribed that with Deepgram, **triaged** it with Claude, pulled a **real**
   San Francisco doctor from the government provider registry, and estimated the
   out-of-pocket cost for his plan — as a clean card with a **Book** button."
2. **Book + pay.** Tap **Book** → "It opens a real Stripe checkout for a refundable
   deposit. I pay…" (use test card) → "…and the original screen **auto-continues** to a
   confirmed booking with a calendar invite."
3. **Evidence (optional, if time).** *"My mom was just diagnosed with breast cancer."*
   → S1: "For serious conditions it surfaces **real recruiting clinical trials** near her
   and **drug-safety** notes — straight from ClinicalTrials.gov and openFDA."
4. **Safety.** *"I have crushing chest pain and can't breathe."* → S1: "Red flags never go
   to booking — it routes straight to **911**."
5. **Dashboard.** Switch tabs: "And this is live — seven agents, what each one does, who
   talks to whom, and real-time stats. **Triage runs on Claude**, the orchestrator on
   ASI:One."

### 2:30 — How it works / why it's hard (S2)
"Under the hood it's **seven uAgents on Fetch.ai's Agentverse**, discoverable and usable
from **ASI:One with no frontend at all**. An orchestrator parses intent and delegates,
agent-to-agent, to specialists: triage, provider-finder, cost, scheduler, payment, and
clinical-evidence. The interesting engineering decision: **most agents use no LLM** — they
call **real APIs** so they can't hallucinate a provider or a price. We only put a model
where judgment is needed: **ASI:One** for conversation, **Claude** for clinical triage.
**Redis** gives us a shared cache, a session store, and a Streams **audit trail** — every
clinical and payment decision is logged. And everything degrades gracefully: if an agent
or the network hiccups, it falls back and the demo never dies."

### 3:15 — Why it matters (S1)
"So in one minute, a scared caregiver went from a sentence to a booked, paid appointment —
by voice, with real providers, real evidence, and a real transaction. CareLoop uses
**Fetch.ai, Deepgram, Anthropic Claude, Redis, and Stripe** — each where it's genuinely
the right tool. It's built for the people who struggle with healthcare the most."

### 3:40 — Close (S1)
"Healthcare's navigation layer is broken. CareLoop is the agent that walks you through it —
in your voice, in your language, all the way to done. Thank you — we'd love your questions."

---

## Judge Q&A

### Why this project?
**Q: Why healthcare navigation?**
A: It's a universal, high-stakes pain that's *coordination*, not medicine — perfect for a
multi-agent system. And it disproportionately hurts the vulnerable (elderly, non-English,
low digital literacy), so good UX here is real impact, not a toy.

**Q: Who is it for?**
A: Caregivers and patients who'd rather *talk* than fill out forms — and anyone in a
moment of stress. Voice-first + multilingual is the access story.

### How is it different?
**Q: How is this different from Zocdoc / a hospital chatbot?**
A: Three ways. (1) **Voice-first and multilingual** — no app, no forms. (2) It's an
**agent that acts** end-to-end (triage → find → cost → pay → book), not a search box or
an FAQ bot. (3) **Clinical depth** — for serious conditions it pulls real recruiting
trials and drug-safety data, which consumer apps don't.

**Q: Isn't this just ChatGPT with a prompt?**
A: No. A single LLM would hallucinate providers, prices, and trials. We use **real
government/clinical APIs** (NPPES, ClinicalTrials.gov, openFDA, Stripe) for facts, and an
LLM only where judgment is needed. The value is the **orchestration + real data + real
action**, not the prose.

### Why not something else?
**Q: Why multi-agent instead of one agent with tools?**
A: Separation of concerns and resilience: each agent is independently testable,
swappable, and **independently discoverable/monetizable on Agentverse**, and one failing
agent falls back without taking down the flow. It's also the Fetch.ai-native design.

**Q: Why two LLMs — why not just ASI:One (or just Claude)?**
A: Right tool for each job. **ASI:One** is the Fetch-native model that powers the agent
ASI:One discovers and converses with. **Claude** is our pick for the one clinical-judgment
step (triage), where careful, safety-aware reasoning matters most. Triage falls back to
ASI:One if Claude is unavailable — it's a preference, not a hard dependency.

**Q: Why is the booking/availability mocked?**
A: There's no universal public API to actually reserve a clinic slot — that needs
per-provider EHR integrations (Epic, athenahealth). We were **honest**: provider names,
addresses, trials, drug data, and the Stripe charge are **real**; only the appointment
slot is synthesized and labeled as such. The architecture is ready to drop in a real
scheduling API.

**Q: Why voice? Adds complexity.**
A: Because our users *can't or won't* use forms — that's the whole point. Deepgram's
multilingual STT means a non-English speaker gets the same flow.

### Technical
**Q: What was hardest?**
A: Making it trustworthy and resilient: real-data edge cases (e.g., the provider registry
matches loosely across addresses, so we filter to the actual practice location), the
agent-to-agent payment flow with server-side verification, and graceful fallback at every
hop so a network blip never breaks the demo.

**Q: Does it scale?**
A: The agents are stateless workers; shared state lives in Redis, and provider/triage/
trials results are cached (we measured ~90×–850× speedups on repeats). Add more agents or
move them to a cloud VM with Redis Cloud — no code change.

**Q: Privacy / HIPAA?**
A: It's a navigation aid, not a covered entity, and it doesn't diagnose. For production:
encrypt session data, add consent, and use BAAs with model/data providers. The Redis
audit trail is already the backbone for compliance logging.

### Safety
**Q: What if it gives bad medical advice?**
A: It never diagnoses — it navigates. Hard-coded red-flag rules force **911 escalation
before any LLM call**, disclaimers are shown throughout, and triage only chooses a
specialty + urgency from a fixed list.

### Business
**Q: How would this make money?**
A: Provider-side (referrals/booking fees), payer/employer benefits navigation, or a
per-call agent fee via Fetch's payment protocol — the agents are already monetizable
primitives on Agentverse.

---

## If something breaks (backup plan)
- ASI:One/network flaky → demo entirely in the **local voice app** (immune to network).
- Mic issues → **type** the same messages (text input works identically).
- Mesh hiccup → `./scripts/demo.sh` re-launches everything in ~20s; the dashboard shows
  green when all 7 agents are live.
