# CareLoop Payment Agent

![domain:healthcare](https://img.shields.io/badge/domain-healthcare-2ea44f)
![payment:stripe](https://img.shields.io/badge/payment-Stripe-635bff)

Handles a **refundable booking deposit / copay** via **Stripe Checkout** (test
mode), following the Fetch.ai agent-transaction pattern: the agent creates a
Checkout session, the user pays on Stripe's hosted page, and the agent verifies
the payment **server-side** (`payment_status == "paid"`) before the appointment is
confirmed. The price is computed server-side and never trusted from the client.

If Stripe isn't configured, the agent reports `enabled=false` and the orchestrator
gracefully skips the deposit.

## Input / Output
- **PaymentLinkRequest** `{ session_id, amount_usd, description }` →
  **PaymentLinkResult** `{ enabled, checkout_url, stripe_session_id, amount_usd }`
- **PaymentVerifyRequest** `{ session_id, stripe_session_id }` →
  **PaymentVerifyResult** `{ paid, status }`

Test card: `4242 4242 4242 4242`, any future expiry, any CVC.

Part of the **CareLoop** multi-agent system (UC Berkeley AI Hackathon 2026).
