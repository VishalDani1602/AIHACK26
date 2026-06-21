# CareLoop — a voice-first, multi-agent healthcare-access concierge

> Speak a health problem in plain language and CareLoop's team of AI agents
> **triages urgency → finds real in-network providers → estimates your
> out-of-pocket cost → books an appointment** — then reads the confirmation
> back to you by voice.

Built for the **UC Berkeley AI Hackathon 2026** on **Fetch.ai** (uAgents + ASI:One)
with a **Deepgram** voice layer. Developed with **Claude Code**.

⚠️ **CareLoop is a navigation aid, not a medical provider.** It does not diagnose.
Red-flag symptoms (chest pain, stroke signs, trouble breathing, etc.) are routed
straight to **911** and never to a booking.

---

## Why it matters
The hardest part of healthcare for many people — elderly patients, caregivers,
non-native English speakers, anyone in distress — isn't the medicine, it's the
**navigation**: *Who do I see? Is it urgent? Who's nearby and takes my insurance?
What will it cost? How do I book it?* CareLoop collapses that maze into one calm
conversation you can have **by voice, in your own language**.

## How it works (architecture)

```
                         ┌──────────────── ASI:One chat ────────────────┐
   🎙 Browser voice app  │   (Agent Chat Protocol — no frontend needed)  │
   (Deepgram STT/TTS)    └───────────────────────┬──────────────────────┘
          │  POST /voice (REST)                   │  ChatMessage
          ▼                                       ▼
   ┌─────────────────────────  Orchestrator Agent  ─────────────────────────┐
   │  ASI:One LLM: parse intent, manage the conversation, compose replies     │
   └───────┬───────────────┬───────────────┬───────────────┬────────────────┘
           │ send_and_receive (agent-to-agent messaging via Agentverse)
           ▼          ▼            ▼          ▼            ▼
   ┌─────────┐ ┌────────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐
   │ Triage  │ │ Provider-  │ │ Cost-   │ │ Scheduler│ │ Payment  │
   │ (911    │ │ Finder     │ │ Estimator│ │ (.ics +  │ │ (Stripe  │
   │  rules) │ │ (CMS NPPES)│ │         │ │  confirm)│ │  deposit)│
   └─────────┘ └────────────┘ └─────────┘ └──────────┘ └──────────┘
```

- **6 agents**, each registered on **Agentverse** with its own mailbox + profile.
- The **Orchestrator** speaks the **Agent Chat Protocol**, so the *entire workflow
  runs from ASI:One with no custom frontend* — then the Deepgram web app layers a
  natural voice experience on top of the same agent.
- **Real data:** providers come from the public **CMS NPPES NPI registry**.
- **Resilient:** every agent-to-agent call falls back to in-process logic, so a
  single agent hiccup never breaks the demo.
- **Redis** is shared infrastructure across all agent processes: a provider/triage
  cache (huge repeat-latency savings), a session store, a **Streams audit trail**,
  and live stat counters — all degrading gracefully if Redis is offline.

## The agents

| Agent | Address (derived from seed) | Role |
|-------|------------------------------|------|
| Orchestrator | `agent1qfxka5afzlk2wsp3agw77l7gz426d9vymwr9l4cfhy2gdvvhq2h8kn798uc` | ASI:One-facing brain; chat protocol + voice REST |
| Triage | `agent1q29ewatrgfnskvkk020y3p2n7qkl36xw293v4x74kpy49czdjqxrqxl9xpe` | Urgency + specialty, hard 911 red-flag rules |
| Provider-Finder | `agent1qdjaj2ctxsjs3vpt5j7uxk46vq9znrquhn9q8fkljqhjueqrr93nzwj3whq` | Real providers from CMS NPPES |
| Cost-Estimator | `agent1qtrge69qnynvpfwd7duw9pgjeffsmmlemflyz06v6v4r2yndtvcwq5k4sd6` | Plan-aware out-of-pocket estimate |
| Scheduler | `agent1q0d726utvqsgjmctt4etsclcapk9tvx75t7tlrcp0luyvsecyr7yz9ujgyf` | Confirmation + iCalendar invite |
| Payment | `agent1qdr7s04hzndeefr2tt085nt29q8jxklf8hne9yhchn63huey9eurczs5ux5` | Stripe Checkout deposit + server-side verify |

Profile URL pattern: `https://agentverse.ai/agents/details/<address>/profile`
(run `./venv/bin/python -m scripts.print_addresses` to reprint).

## Quick start

```bash
# 1. Install
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt

# 2. Configure keys
cp .env.example .env       # then fill in ASI1_API_KEY, AGENTVERSE_API_KEY, DEEPGRAM_API_KEY

# 3. Sanity check the whole pipeline with no network/mailbox needed
./venv/bin/python -m scripts.selftest

# 4. Start Redis (shared cache / sessions / audit trail / stats)
docker run -d --name careloop-redis -p 6379:6379 redis:7-alpine

# 5. Start all six agents (each in its own process + mailbox)
./scripts/run_all.sh

# 6. Auto-register every agent's mailbox on Agentverse (no browser clicks)
./venv/bin/python -m scripts.register_agents

# 7. Start the Deepgram voice web app
./venv/bin/uvicorn voice.backend:app --port 8080
#    -> open http://127.0.0.1:8080  and click "Click to talk"
```

ASI:One promo code: `BERKELEYAI` · Agentverse promo code: `BERKELEYAIAV`

## Try it

**Golden path** (books a real provider):
```
my dad has had a bad cough and a low fever for five days,
he's on Medicare and we're in Berkeley
```
→ "…I'd start with Primary Care … the best match near Berkeley is **Allison Aiken, M.D.**
at 2222 Bancroft Way with an opening in 2 days … estimated **$144–$207** with Medicare …
want me to book it?" → *"yes"* → **pay a refundable $25 deposit** via a real Stripe
Checkout link (test card `4242 4242 4242 4242`) → *"done"* → agent verifies payment →
✅ booked + calendar invite.

> If `STRIPE_SECRET_KEY` is not set, CareLoop skips the deposit and books directly.

**Emergency path** (routes to 911, no booking):
```
I'm having crushing chest pain and I can't breathe
```

## Tech
- **Fetch.ai uAgents** — multi-agent framework, Agentverse mailboxes, Almanac discovery
- **Agent Chat Protocol** — ASI:One discoverability & chat
- **ASI:One** (`asi1-mini`) — intent parsing, triage, reply composition
- **Deepgram** — Nova-3 STT (multilingual) + Aura-2 TTS
- **Stripe** — real (test-mode) Checkout for a refundable booking deposit, verified server-side
- **Redis** (beyond caching) — shared provider/triage cache (91×–853× faster on repeats),
  session store, **Streams audit trail** of every clinical/payment/booking decision, live stat counters
- **CMS NPPES NPI Registry** — real provider data
- **FastAPI** — voice web app backend

## Deliverables
- 🔗 ASI:One shared chat: _add link here_
- 🤖 Agentverse profiles: see the table above
- 🎬 Demo video: _add link here_
- 📦 This repo

## Repository layout
```
agents/           orchestrator + 4 specialists, shared logic/models/prompts, profile READMEs
voice/            FastAPI Deepgram bridge + click-to-talk web UI
data/             taxonomy map + illustrative cost model
scripts/          selftest, run_all.sh, print_addresses
```

## Safety & honesty
- Triage is **navigation, not diagnosis**; disclaimers shown throughout.
- Hard-coded red-flag rules force **911 escalation before any LLM call**.
- Provider names/addresses are **real (NPPES)**; appointment slots and insurance
  acceptance are **synthesized and labeled as estimates** — NPPES has no such data.

_Developed with Claude Code for the UC Berkeley AI Hackathon 2026._
