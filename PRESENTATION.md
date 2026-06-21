# CareLoop — Pitch script (3–4 min) + Judge Q&A

**Roles:** **A = product/host** · **B = technical** (drives the live demo).
**Setup:** voice app open at `http://127.0.0.1:8080`; dashboard open in a 2nd tab at
`/dashboard`; mic on. Pre-run one golden query so the cache is warm. Lead with the
**local voice app** (network can't break it); show ASI:One only if Wi-Fi is solid.

Stage directions are in [brackets]; everything else is spoken word-for-word.

---

## FULL SCRIPT (read aloud)

**A:** Quick show of hands — has anyone here ever had to find a doctor for a sick parent
or grandparent? Right. Now picture doing that at seventy years old, in your second
language, while you're scared. Here's the thing we kept coming back to: the hard part of
healthcare usually isn't the medicine — it's the **navigation**. Who do I even see? Is
this urgent? Who's nearby, who takes my insurance, what will it cost, and how do I
actually book it? That maze is where people give up, delay care, or just show up at the ER.

**A:** So we built **CareLoop** — a voice-first *team* of AI agents that takes you from a
spoken symptom all the way to a booked appointment. It doesn't just chat. It acts. [B] is
going to show you, live.

**B:** Thanks. Everything here is real and running. I'll just talk to it. [tap mic]
*"My dad's had a bad cough and a fever for five days. He's on Medicare, and we're in San
Francisco."* [release]

**B:** [as the card appears] So in a couple of seconds: Deepgram transcribed that; our
triage agent — running on Claude — decided this is primary care and not an emergency; and
we pulled a **real** San Francisco doctor from the federal provider registry, with a cost
estimate for his Medicare plan. It comes back as a card with a **Book** button.

**B:** I'll book it. [click Book] That opens a real **Stripe** checkout for a small
refundable deposit. I'll pay… [enter test card 4242…] …and watch the original screen — it
just **continued on its own**. We're booked, with a calendar invite. No dead end, no
copy-pasting a confirmation.

**A:** And it goes deeper when it needs to.

**B:** [tap mic] *"My mom was just diagnosed with early-stage breast cancer."* [release]

**A:** For a serious condition, CareLoop surfaces **real, currently-recruiting clinical
trials** near her from ClinicalTrials.gov, plus **drug-safety** information from the FDA —
options she can take to her doctor. A normal booking app doesn't do that.

**B:** And safety is built in. [tap mic] *"I'm having crushing chest pain and I can't
breathe."* [release; red banner shows] Red-flag symptoms never go to booking — it routes
straight to **911**, before any model even runs.

**B:** One last thing. [switch to dashboard tab] This is our live system board: **seven
agents**, what each one does, who talks to whom, and real-time stats. You can see triage
runs on **Claude**, and the orchestrator on **ASI:One**.

**B:** Architecturally: seven **uAgents on Fetch.ai's Agentverse**, fully usable from
**ASI:One with no frontend at all**. An orchestrator parses intent and delegates — agent
to agent — to specialists: triage, provider search, cost, scheduling, payment, and
clinical evidence. The deliberate choice is that **most agents use no language model** —
they call real APIs, so they can't invent a doctor or a price. We only put a model where
there's genuine judgment: ASI:One for the conversation, Claude for clinical triage. Redis
gives us caching, sessions, and an **audit trail** of every decision — and every step
degrades gracefully, so a hiccup never breaks the flow.

**A:** So in about a minute, a scared caregiver went from a single sentence to a booked,
paid appointment — by voice, with real providers, real medical evidence, and a real
transaction. CareLoop uses **Fetch.ai, Deepgram, Anthropic's Claude, Redis, and Stripe** —
each one exactly where it's the right tool.

**A:** Healthcare's navigation layer is broken. CareLoop is the agent that walks you
through it — in your voice, in your language, all the way to *done*. Thank you — we'd love
your questions.

---

## 60-SECOND VERSION (expo / hallway judging — A solo)

"The hardest part of healthcare isn't the medicine — it's the navigation: who to see,
is it urgent, who's nearby and takes my insurance, what's it cost, how do I book it.
CareLoop is a voice-first team of AI agents that does the whole thing. [tap mic] *'My dad
has a cough and fever for five days, he's on Medicare in San Francisco.'* It triages with
Claude, finds a **real** doctor from the federal registry, estimates the cost, and books
it with a Stripe deposit — and for serious conditions it even pulls real clinical trials
and drug-safety data. Seven agents on Fetch.ai, discoverable from ASI:One, with Deepgram
voice and a Redis audit trail. Crucially, most agents use **no LLM** — they call real
APIs, so they can't hallucinate a provider or a price. It's navigation for the people who
struggle with it most — elderly, non-English-speaking, scared. Want to try it?"

---

## Judge Q&A

### Why this project?
**Q: Why healthcare navigation?**
A: It's a universal, high-stakes *coordination* problem — not medicine — which is exactly
what multi-agent systems are good at. And it hurts the vulnerable most (elderly,
non-English, low digital literacy), so good UX here is real impact.

**Q: Who's it for?**
A: Caregivers and patients who'd rather *talk* than fill out forms, and anyone in a moment
of stress. Voice-first + multilingual is the access story.

### How is it different?
**Q: How is this different from Zocdoc / a hospital chatbot?**
A: (1) **Voice-first and multilingual** — no app, no forms. (2) It's an **agent that acts**
end-to-end (triage → find → cost → pay → book), not a search box or FAQ bot. (3) **Clinical
depth** — real recruiting trials + drug-safety for serious conditions.

**Q: Isn't this just ChatGPT with a prompt?**
A: No — a single LLM would hallucinate providers, prices, and trials. We use **real
government/clinical APIs** for facts (NPPES, ClinicalTrials.gov, openFDA, Stripe) and an
LLM only where judgment is needed. The value is orchestration + real data + real action.

### Why not something else?
**Q: Why multi-agent instead of one agent with tools?**
A: Separation of concerns + resilience — each agent is independently testable, swappable,
and **independently discoverable/monetizable on Agentverse**, and one failing agent falls
back without taking down the flow. It's also the Fetch.ai-native design.

**Q: Why two LLMs — why not just ASI:One or just Claude?**
A: Right tool per job. **ASI:One** is the Fetch-native model that powers the agent ASI:One
discovers and talks to. **Claude** is our pick for the one clinical-judgment step (triage),
where careful, safety-aware reasoning matters — and it falls back to ASI:One if Claude is
unavailable. So it's a preference, not a hard dependency.

**Q: Why is booking/availability mocked?**
A: There's no universal public API to reserve a clinic slot — that needs per-provider EHR
integrations (Epic, athenahealth). We were honest: provider names, addresses, trials, drug
data, and the Stripe charge are **real**; only the appointment slot is synthesized and
labeled. The architecture is ready to drop in a real scheduler.

**Q: Why voice — it adds complexity.**
A: Because our users can't or won't use forms — that's the point. Deepgram's multilingual
STT means a non-English speaker gets the same flow.

### Technical
**Q: What was hardest?**
A: Making it trustworthy and resilient — real-data edge cases (the provider registry
matches loosely across addresses, so we filter to the actual practice location), the
agent-to-agent payment with server-side verification, and graceful fallback at every hop.

**Q: Does it scale?**
A: Agents are stateless workers; shared state is in Redis; provider/triage/trials results
are cached (~90×–850× faster on repeats). Move agents to a cloud VM + Redis Cloud — no code
change.

**Q: Privacy / HIPAA?**
A: It's a navigation aid, not a covered entity, and it doesn't diagnose. For production:
encrypt session data, add consent, BAAs with providers. The Redis audit trail is already
the backbone for compliance logging.

### Safety
**Q: What if it gives bad medical advice?**
A: It never diagnoses — it navigates. Hard-coded red-flag rules force **911 before any LLM
call**; disclaimers throughout; triage only picks urgency + a specialty from a fixed list.

### Business
**Q: How does it make money?**
A: Provider-side referral/booking fees, payer/employer benefits navigation, or a per-call
agent fee via Fetch's payment protocol — the agents are already monetizable primitives.

---

## If something breaks (backup plan)
- ASI:One / network flaky → demo entirely in the **local voice app** (immune to network).
- Mic issues → **type** the same lines (text input works identically).
- Mesh hiccup → `./scripts/demo.sh` relaunches everything in ~20s; the dashboard goes
  green when all 7 agents are live.
