# CareLoop — Devpost submission

_Voice-first, multi-agent healthcare-access concierge. Fetch.ai uAgents + ASI:One + Deepgram._

## Inspiration
For millions of people the hardest part of healthcare isn't the medicine — it's the
**navigation**. An elderly parent, a caregiver juggling work, someone who speaks
English as a second language, or anyone scared in the moment all hit the same wall:
*Who do I see? Is this urgent? Who's nearby and takes my insurance? What will it
cost? How do I actually book it?* That maze is where people give up, delay care, or
end up in the ER. CareLoop turns it into one calm conversation you can have **out
loud, in your own language**.

## What it does
You describe a health concern in plain language (by **voice** or text). CareLoop:
1. **Triages** urgency and the right kind of clinician — with hard-coded red-flag
   rules that route emergencies straight to **911**, never to a booking.
2. **Finds real providers** near you via the public **CMS NPPES** registry.
3. **Estimates your out-of-pocket cost** based on your insurance type.
4. **Takes a refundable deposit** via a real **Stripe** Checkout (test mode) and
   verifies the payment server-side before confirming.
5. **Books the appointment** and produces a calendar invite — then reads the
   confirmation back to you by voice.

## How we built it
- **Fetch.ai uAgents**: six agents — an **Orchestrator** plus **Triage**,
  **Provider-Finder**, **Cost-Estimator**, **Scheduler**, and **Payment**
  specialists — each registered on **Agentverse** with its own mailbox and profile.
- **Stripe agent transaction**: the Payment agent creates a real (test-mode)
  Checkout session and verifies `payment_status == "paid"` server-side before the
  Scheduler confirms — a genuine intent→action transaction, not a mock.
- **Agent Chat Protocol + ASI:One**: the Orchestrator is discoverable and fully
  usable from ASI:One, so the **entire workflow runs in ASI:One chat with no
  custom frontend**. Agents coordinate through real agent-to-agent messaging
  (`send_and_receive`).
- **ASI:One LLM** (`asi1-mini`) parses intent, drives the multi-turn conversation,
  and runs triage reasoning.
- **Deepgram**: Nova-3 multilingual STT + Aura-2 TTS power a click-to-talk web app
  layered on top of the same Orchestrator — voice is the primary, essential interface.
- **CMS NPPES NPI Registry** for real, verifiable provider data.
- Built with **Claude Code**.

## Target users
Caregivers and patients who struggle with healthcare navigation — older adults,
non-native English speakers, people with low digital literacy, and anyone who'd
rather just *talk* to get help than fill out forms.

## Agent outcomes (intent → action)
A spoken sentence becomes a **triaged plan, a real provider match, a cost estimate,
a completed (test-mode) deposit payment, and a booked appointment with a calendar
invite** — concrete actions, not a chat.

## Mapping to the Fetch.ai judging criteria
- **Use of Fetch.ai tech (25%)** — 5 uAgents on Agentverse, Agent Chat Protocol,
  ASI:One discoverability + LLM, real agent-to-agent orchestration.
- **Functionality (25%)** — working end-to-end flow on real NPPES provider data.
- **Innovation (20%)** — voice-first + multilingual + multi-agent healthcare navigation.
- **Real-world impact (20%)** — care access for the people who struggle with it most.
- **UX (10%)** — natural voice conversation; also fully usable in ASI:One chat.

## What's next
Real scheduling/EHR integrations, live insurance-network checks, and telephony
(call a real number). The Stripe deposit already completes a real test-mode
transaction; next is applying it to the actual copay and refund-on-arrival.

---

## Deliverables (fill in before submitting)
- **ASI:One shared chat session:** _paste link_
- **Agentverse agent profiles:**
  - Orchestrator: https://agentverse.ai/agents/details/agent1qfxka5afzlk2wsp3agw77l7gz426d9vymwr9l4cfhy2gdvvhq2h8kn798uc/profile
  - Triage: https://agentverse.ai/agents/details/agent1q29ewatrgfnskvkk020y3p2n7qkl36xw293v4x74kpy49czdjqxrqxl9xpe/profile
  - Provider-Finder: https://agentverse.ai/agents/details/agent1qdjaj2ctxsjs3vpt5j7uxk46vq9znrquhn9q8fkljqhjueqrr93nzwj3whq/profile
  - Cost-Estimator: https://agentverse.ai/agents/details/agent1qtrge69qnynvpfwd7duw9pgjeffsmmlemflyz06v6v4r2yndtvcwq5k4sd6/profile
  - Scheduler: https://agentverse.ai/agents/details/agent1q0d726utvqsgjmctt4etsclcapk9tvx75t7tlrcp0luyvsecyr7yz9ujgyf/profile
  - Payment: https://agentverse.ai/agents/details/agent1qdr7s04hzndeefr2tt085nt29q8jxklf8hne9yhchn63huey9eurczs5ux5/profile
- **GitHub:** https://github.com/VishalDani1602/AIHACK26
- **Demo video (3–5 min):** _paste link_

## Demo script (for the video)
1. **Voice golden path** — open the web app, click to talk:
   *"My dad has had a bad cough and a low fever for five days, he's on Medicare and we're in Berkeley."*
   → CareLoop recommends a clinician, names a **real** Berkeley provider with an
   opening and a cost estimate, asks to book → say **"yes"** → it returns a **real
   Stripe Checkout link** for a refundable $25 deposit → pay with test card
   `4242 4242 4242 4242` → say **"done"** → agent verifies payment → hear the booking confirmation.
2. **Multilingual** — switch the language selector and ask in Spanish.
3. **Emergency** — *"I'm having crushing chest pain and I can't breathe"* → immediate **911** escalation, no booking.
4. **ASI:One (no frontend)** — run the same golden-path query in ASI:One chat to show
   the agents working without any custom UI. Show the Agentverse profiles.
