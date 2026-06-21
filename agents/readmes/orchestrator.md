# CareLoop Orchestrator

![domain:healthcare](https://img.shields.io/badge/domain-healthcare-2ea44f)
![tech:uagents](https://img.shields.io/badge/tech-uAgents-blue)
![llm:asi1](https://img.shields.io/badge/LLM-ASI%3AOne-7c3aed)

**The ASI:One-facing brain of CareLoop — a voice-first healthcare-access concierge.**

Describe a health concern in plain language and CareLoop coordinates a team of
agents to **triage urgency → find real in-network providers → estimate your
out-of-pocket cost → book an appointment**, then confirms it back to you.

> ⚠️ CareLoop is a **navigation aid, not a medical provider**. It does not give
> diagnoses. Emergencies are routed to 911.

## What it does
This agent implements the **Agent Chat Protocol**, so you can use the entire
workflow directly from ASI:One — no app required. It parses your intent with
ASI:One, then orchestrates four specialist agents via agent-to-agent messaging:

| Specialist | Role |
|------------|------|
| Triage | Urgency + recommended specialty (hard 911 red-flag rules) |
| Provider-Finder | Real providers from the CMS NPPES registry |
| Cost-Estimator | Plan-aware out-of-pocket estimate |
| Scheduler | Booking confirmation + calendar invite |

## Try it (in ASI:One)
```
my dad has had a bad cough and a low fever for five days,
he's on Medicare and we're in Berkeley
```
CareLoop will recommend a clinician, surface a real nearby provider with an
opening and an estimated cost, and book it when you say "yes".

Emergency example (routes to 911, no booking):
```
I'm having crushing chest pain and I can't breathe
```

## Input / Output
- **Input:** `ChatMessage` (free-text) — Agent Chat Protocol
- **Output:** `ChatMessage` — conversational reply; ends the session on booking or emergency

Also exposes a REST endpoint `POST /voice` (`VoiceRequest → VoiceResponse`) used by
the CareLoop Deepgram voice web app.

Built for the UC Berkeley AI Hackathon 2026 with Fetch.ai uAgents + ASI:One + Deepgram.
