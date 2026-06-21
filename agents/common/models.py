"""Shared message schemas for CareLoop agent-to-agent communication.

These are uAgents `Model` types (pydantic v1 under the hood) used both as the
on-the-wire messages between the orchestrator and the specialist agents, and as
the request/response models for the orchestrator's REST endpoint (voice app).
"""
from typing import List, Optional
from uagents import Model


# ---- Triage ----
class TriageRequest(Model):
    session_id: str
    symptoms: str
    patient_age: Optional[int] = None


class TriageResult(Model):
    session_id: str
    urgency: str               # "emergency" | "urgent" | "routine" | "self-care"
    recommended_specialty: str  # human-friendly, e.g. "Primary Care", "Cardiology"
    taxonomy: str               # NPPES taxonomy description used for provider search
    red_flags: List[str] = []
    advice: str = ""
    emergency: bool = False      # True -> 911 escalation, bypass booking
    condition: str = ""          # concise condition name if identifiable (drives evidence lookup)
    chronic: bool = False        # serious/chronic -> consult the clinical-evidence agent


# ---- Provider finder ----
class ProviderRequest(Model):
    session_id: str
    taxonomy: str
    city: str = ""
    state: str = ""
    postal_code: str = ""
    insurance: str = ""
    limit: int = 3


class Provider(Model):
    name: str
    specialty: str
    address: str
    phone: str = ""
    accepts_insurance: bool = True
    next_slot: str = ""         # synthesized availability (NPPES has no scheduling data)
    npi: str = ""


class ProviderResult(Model):
    session_id: str
    providers: List[Provider] = []
    note: str = ""


# ---- Cost estimator ----
class CostRequest(Model):
    session_id: str
    visit_type: str             # "primary_care" | "specialist" | "urgent_care" | "er"
    insurance: str = ""
    provider_seed: str = ""     # provider NPI/name -> per-provider price variance
    region: str = ""            # 2-letter state -> regional cost-of-care multiplier


class CostResult(Model):
    session_id: str
    estimate_low: float = 0.0
    estimate_high: float = 0.0
    explanation: str = ""


# ---- Scheduler / booking ----
class BookingRequest(Model):
    session_id: str
    provider_name: str
    provider_address: str = ""
    slot: str = ""
    patient_name: str = "the patient"
    reason: str = ""


class BookingResult(Model):
    session_id: str
    confirmation_code: str
    summary: str
    ics: str = ""               # iCalendar text for the appointment


# ---- Clinical evidence (trials + drug safety) ----
class Trial(Model):
    nct_id: str
    title: str
    status: str = ""
    phase: str = ""
    location: str = ""
    url: str = ""


class DrugNote(Model):
    drug: str
    info: str = ""
    url: str = ""


class EvidenceRequest(Model):
    session_id: str
    condition: str = ""
    medications: str = ""        # comma-separated
    city: str = ""
    state: str = ""
    limit: int = 3


class EvidenceResult(Model):
    session_id: str
    trials: List[Trial] = []
    drug_notes: List[DrugNote] = []
    note: str = ""


# ---- Payment (Stripe copay/deposit) ----
class PaymentLinkRequest(Model):
    session_id: str
    amount_usd: float
    description: str


class PaymentLinkResult(Model):
    session_id: str
    enabled: bool                # False if Stripe isn't configured -> skip payment
    checkout_url: str = ""
    stripe_session_id: str = ""
    amount_usd: float = 0.0


class PaymentVerifyRequest(Model):
    session_id: str
    stripe_session_id: str


class PaymentVerifyResult(Model):
    session_id: str
    paid: bool
    status: str = ""


# ---- Orchestrator REST (voice app <-> orchestrator) ----
class VoiceRequest(Model):
    session_id: str
    text: str


class VoiceResponse(Model):
    session_id: str
    reply: str
    stage: str = ""             # collecting | confirming | awaiting_payment | done | emergency
    emergency: bool = False
    card: Optional[dict] = None       # structured content for the UI (provider/trials/payment/booking/emergency)
    actions: Optional[List[dict]] = None  # quick-reply buttons: [{label, send, primary?}]
