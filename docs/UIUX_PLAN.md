# CareLoop — Best UI/UX Plan (execution spec for the frontend)

Goal: win **Best UI/UX**. This is a build spec for the frontend owner. Backend
changes (structured card responses) will be provided on request — see the API
contract below.

---

## 1. The winning thesis — "the most accessible healthcare interface"

CareLoop's users are **elderly, low-digital-literacy, non-English-first, or scared
in the moment**. Judges reward UX that visibly serves real users over UX that is
merely pretty. Every decision below should ladder up to: *calm, obvious, low-friction,
voice-first, multilingual, accessible.* Say this out loud in the demo.

Maps to typical Best-UI/UX rubric: **Clarity · Polish/cohesion · Delight ·
Accessibility · Responsiveness · Memorable identity.**

---

## 2. Current state (B+ → needs these to reach A)

Strengths: clean light "clinical paper" theme, consistent cards, dual voice+text
input, live stats line, dashboard, responsive layout.

Gaps holding it back:
1. Bot replies are **plain-text bubbles** (provider/cost/trials are prose — not scannable or actionable).
2. **Thin voice feedback** while recording (pulsing button + the word "Recording" only).
3. **No in-chat "thinking" state.**
4. **No action buttons** — user must type/say "yes" to book (friction + fragile on stage).
5. **Emergency is a text bubble**, not a commanding banner with one-tap Call 911.
6. **First-run friction** — blank prompt, nothing to tap.
7. **Accessibility not explicit** — and it's the product's whole mission.

---

## 3. Tier 1 — difference-makers (build first)

### 3.1 Rich, interactive message cards  *(needs backend contract in §6)*
Replace the prose reply with structured cards when the backend provides them:

- **Provider card**
  - Title row: provider **name** + specialty.
  - Rows: 📍 address · 🗓️ next slot · 💲 estimated cost range.
  - Badge: green "Accepts your plan" / amber "Confirm plan".
  - **Action buttons:** `Book this` (primary) · `Different time` · `Another provider`.
- **Trial cards** (clinical evidence): each = title, `Phase` chip, location, opens
  ClinicalTrials.gov in a new tab. Collapsible "Clinical evidence (N)" group.
- **Cost chip / mini-breakdown:** `$144–$207 with Medicare` with a tooltip explaining copay/deductible.
- **Booking confirmation card:** ✅ provider + date + confirmation code + **Add to calendar** (download the `.ics`).

Action buttons send the corresponding text to the backend (`Book this` → "yes",
`Another provider` → "another provider", `Different time` → "a different time"),
so the existing conversation logic is reused.

### 3.2 Live voice visualization  *(frontend-only)*
- While recording, show a **real-time level meter / waveform** using Web Audio
  `AnalyserNode` on the mic `MediaStream` (the app already has the stream).
- Replace the static "Recording" text with an animated listening state.
- After release, show a **"🤖 CareLoop is thinking…" typing bubble** in the chat
  (animated dots) until the reply arrives — remove it when the bubble renders.

### 3.3 One-tap Emergency  *(frontend-only — `data.emergency` already exists)*
- On `emergency === true`, render a full-width **red banner card**: ⚠️ headline,
  one or two calm next-steps, and a large **Call 911** button (`<a href="tel:911">`).
- Suppress the normal composer affordances briefly to make 911 the obvious action.

### 3.4 Example prompt chips  *(frontend-only)*
- On first load (empty chat), show 3–4 tappable chips under the greeting:
  - "My dad has a bad cough and fever"
  - "Find a cardiologist near me"
  - "My mom was diagnosed with diabetes"
  - "I have chest pain" (demonstrates the 911 path)
- Tapping a chip fills + sends it. Lowers friction; great for the video.

---

## 4. Tier 2 — polish + the accessibility story (a demo talking point)

### 4.1 Accessibility pass (WCAG AA)
- `aria-live="polite"` region that announces each bot reply for screen readers.
- `aria-label`s on the mic, send, new-chat, language, and nav buttons; `role`s where needed.
- Visible `:focus-visible` rings on every interactive element (some exist — make consistent).
- Honor `prefers-reduced-motion` (disable pulse/waveform animation).
- **Large-text + High-contrast toggle** in the header (persist in `localStorage`).
- Verify contrast ≥ 4.5:1 for text, ≥ 3:1 for UI (the green `--accent` on white is fine; check muted greys).
- Hit targets ≥ 44×44px (mic/send already large; check chips/nav).

### 4.2 Micro-interactions
- Messages **fade + slide in** (respecting reduced-motion); smooth autoscroll to newest.
- Button press/active feedback; refined recording pulse; subtle card hover lift.
- Skeleton/shimmer for the "thinking" bubble.

### 4.3 Identity polish
- A more distinctive wordmark/logo than the generic `⊕` (e.g., a looping "care loop" mark).
- Lock a spacing scale (4/8/12/16/24) and type scale; audit inconsistent margins.

---

## 5. Tier 3 — flourishes (only if ahead)
- Dark-mode toggle.
- Multilingual flourish: show the **detected language** on a reply; basic **RTL** support (Arabic/Hebrew) — strong tie to the multilingual differentiator.
- Dashboard: animated count-up on KPIs, tiny sparklines on cache hit-rate.
- A short hero header / first-frame for the demo video.

---

## 6. Backend API contract for the interactive cards — ✅ IMPLEMENTED

**Status: live.** `/api/text` and `/api/converse` (and the orchestrator `/voice`)
now return additive `card` + `actions` fields alongside `reply`. The text `reply`
still works for the ASI:One path and as a fallback. Frontend can stop regex-parsing
the prose and render from `card`/`actions` directly.

**Final shapes shipped** (slightly refined from the original proposal below):
- `card.type` ∈ `provider | payment | booking | emergency`
- **provider**: `card.provider{name,specialty,address,phone,next_slot,accepts_insurance}`,
  `card.cost{low,high,explanation}`, `card.insurance_known` (bool — only show the
  "Accepts your plan" badge when `true`), and when present `card.trials[]` +
  `card.drug_notes[{drug,info,url}]`.
- **payment**: `card.payment{checkout_url, amount_usd}`.
- **booking**: `card.booking{confirmation_code, provider, address, slot, deposit_paid, ics}`
  — `ics` is the raw iCalendar text; build an "Add to calendar" download via a Blob
  (no separate endpoint needed).
- **emergency**: `card.emergency{detail, red_flags[]}` (render the red banner + a
  `tel:911` button).
- `actions`: `[{label, send, primary?}]` — on tap, POST `send` to `/api/text`.
  Provider → Book this/Different time/Another provider; Payment → I've paid/Skip
  deposit; Booking → New request.

**Request-side input — insurance plan selector (NEW).** Both `/api/text` and
`/api/converse` now accept an optional **`insurance`** value
(`medicare|medicaid|ppo|hmo|high_deductible|uninsured`); `/api/text` takes it in the
JSON body, `/api/converse` as a `?insurance=` query param. Add a **plan `<select>`**
next to the Language selector and send the chosen value with each turn (like
`language`). Selecting a plan with empty text re-evaluates and updates the cost on
the current provider card. The agent also asks for the plan conversationally when
it's missing, so cost is plan-specific either way.

Original proposal (for reference):

```jsonc
{
  "session_id": "web-abc",
  "reply": "…existing prose (fallback / TTS)…",
  "stage": "confirming",           // collecting | confirming | awaiting_payment | done | emergency
  "emergency": false,
  "card": {                          // present when there's something structured to show
    "type": "provider",             // provider | trials | booking | payment | emergency
    "provider": {
      "name": "Allison Aiken, M.D.",
      "specialty": "Family Medicine",
      "address": "2222 Bancroft Way, Berkeley, CA",
      "next_slot": "in 2 days at 3:45 PM",
      "accepts_insurance": true
    },
    "cost": { "low": 144, "high": 207, "explanation": "With Medicare…" },
    "trials": [
      { "nct_id": "NCT…", "title": "…", "phase": "Phase 3", "location": "…", "url": "https://clinicaltrials.gov/study/NCT…" }
    ],
    "payment": { "checkout_url": "https://checkout.stripe.com/…", "amount_usd": 25 },
    "booking": { "confirmation_code": "CL-XXXX", "ics_download_url": "/api/ics/<session>" }
  },
  "actions": [                       // quick-reply buttons to render
    { "label": "Book this", "send": "yes", "primary": true },
    { "label": "Different time", "send": "a different time" },
    { "label": "Another provider", "send": "another provider" }
  ]
}
```

Notes for the frontend:
- If `card`/`actions` are absent, render `reply` as today (graceful).
- `actions[].send` is the text to POST back to `/api/text` (or `/voice`) on tap.
- I'll also add a small **`GET /api/ics/<session>`** endpoint so "Add to calendar"
  can download the real `.ics` the scheduler already generates.

When you're ready for the cards, ping me and I'll ship the backend fields +
the `.ics` endpoint; you build the card components against this contract.

---

## 7. Suggested build order (frontend owner)
1. Emergency banner + Call 911  *(tiny, high impact, no backend)*
2. Example chips  *(tiny, no backend)*
3. Typing indicator + voice waveform  *(no backend)*
4. Accessibility pass + large-text toggle  *(no backend; big judging signal)*
5. Interactive cards + action buttons  *(consume §6 contract — ask me to enable backend)*
6. Micro-interactions + identity polish
7. Tier 3 if time

## 8. Show it in the demo
- Open with the **example chip** tap (instant, no typing).
- Speak a symptom → **live waveform** → **typing bubble** → **provider card with Book button**.
- Tap **Book** → Stripe deposit → confirmation card with **Add to calendar**.
- Say a serious condition → **trial cards**.
- Trigger **chest pain** → red banner + **Call 911**.
- Toggle **Large text / High contrast** and mention the accessibility mission.
- Cut to the **/dashboard** to show the system is real and live.
