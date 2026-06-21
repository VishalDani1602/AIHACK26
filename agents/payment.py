"""CareLoop Payment Agent (Stripe, test mode).

Creates a Stripe Checkout session for a refundable booking deposit / copay and
verifies payment server-side before the appointment is confirmed. Implements the
Fetch.ai agent-transaction pattern: create checkout -> user pays -> verify paid.
"""
from uagents import Agent, Context

from agents.common import config, stripe_pay
from agents.common.models import (
    PaymentLinkRequest,
    PaymentLinkResult,
    PaymentVerifyRequest,
    PaymentVerifyResult,
)

agent = Agent(
    name="careloop-payment",
    seed=config.SEEDS["payment"],
    port=config.PORTS["payment"],
    mailbox=True,
    publish_agent_details=True,
    readme_path=config.readme("payment"),
    description="CareLoop Payment — Stripe Checkout for a refundable booking deposit; verifies payment before confirming.",
)


@agent.on_message(model=PaymentLinkRequest, replies=PaymentLinkResult)
async def handle_link(ctx: Context, sender: str, msg: PaymentLinkRequest):
    if not stripe_pay.enabled():
        ctx.logger.info(f"payment[{msg.session_id}] Stripe not configured -> skip")
        await ctx.send(sender, PaymentLinkResult(session_id=msg.session_id, enabled=False))
        return
    try:
        sid, url = stripe_pay.create_checkout(msg.amount_usd, msg.description)
        ctx.logger.info(f"payment[{msg.session_id}] checkout {sid} for ${msg.amount_usd}")
        await ctx.send(sender, PaymentLinkResult(
            session_id=msg.session_id, enabled=True, checkout_url=url,
            stripe_session_id=sid, amount_usd=msg.amount_usd))
    except Exception as exc:
        ctx.logger.warning(f"payment[{msg.session_id}] checkout failed: {exc}")
        await ctx.send(sender, PaymentLinkResult(session_id=msg.session_id, enabled=False))


@agent.on_message(model=PaymentVerifyRequest, replies=PaymentVerifyResult)
async def handle_verify(ctx: Context, sender: str, msg: PaymentVerifyRequest):
    paid, status = stripe_pay.verify(msg.stripe_session_id)
    ctx.logger.info(f"payment[{msg.session_id}] verify {msg.stripe_session_id} -> {status}")
    await ctx.send(sender, PaymentVerifyResult(session_id=msg.session_id, paid=paid, status=status))


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Payment agent address: {agent.address} (stripe enabled={stripe_pay.enabled()})")


if __name__ == "__main__":
    agent.run()
