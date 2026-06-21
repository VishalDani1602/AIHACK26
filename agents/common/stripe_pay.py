"""Stripe Checkout helper for the CareLoop copay/deposit flow (test mode).

Follows the Fetch.ai agent-transaction pattern: an agent creates a Stripe Checkout
Session, the user pays on Stripe's hosted page, and the agent verifies the payment
server-side (payment_status == "paid") before completing the action. Prices are
computed server-side and never trusted from the client.

If STRIPE_SECRET_KEY is unset, payments are considered "not configured" and the
orchestrator gracefully skips the deposit step.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
DEPOSIT_USD = float(os.getenv("CARELOOP_DEPOSIT_USD", "25"))
BASE_URL = os.getenv("CARELOOP_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
CANCEL_URL = os.getenv("CARELOOP_CANCEL_URL", f"{BASE_URL}/?canceled=1")

_stripe = None
if STRIPE_SECRET_KEY:
    try:
        import stripe

        stripe.api_key = STRIPE_SECRET_KEY
        _stripe = stripe
    except Exception:  # pragma: no cover
        _stripe = None


def enabled() -> bool:
    return _stripe is not None


def create_checkout(amount_usd: float, description: str, session_id: str = "") -> Tuple[str, str]:
    """Create a hosted Stripe Checkout session. Returns (stripe_session_id, url).

    success_url points at /paid?sid=<frontend session> so the success page can
    signal the original CareLoop tab to auto-continue (book) without the user
    typing "done".
    """
    if not _stripe:
        raise RuntimeError("Stripe not configured (STRIPE_SECRET_KEY missing)")
    sid = quote((session_id or "").split(":")[-1])  # drop "voice:" prefix -> frontend session id
    success_url = f"{BASE_URL}/paid?sid={sid}" if sid else f"{BASE_URL}/paid"
    session = _stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": description[:250]},
                    "unit_amount": int(round(amount_usd * 100)),  # cents, server-side
                },
                "quantity": 1,
            }
        ],
        success_url=success_url,
        cancel_url=CANCEL_URL,
        metadata={"product": "careloop_booking_deposit"},
    )
    return session.id, session.url


def verify(stripe_session_id: str) -> Tuple[bool, str]:
    """Check whether a Checkout session has been paid. Returns (paid, status)."""
    if not _stripe:
        return False, "stripe_not_configured"
    try:
        session = _stripe.checkout.Session.retrieve(stripe_session_id)
        status = session.payment_status  # "paid" | "unpaid" | "no_payment_required"
        return status == "paid", status
    except Exception as exc:  # pragma: no cover
        return False, f"error:{exc}"
