"""CareLoop Cost-Estimator Agent.

Receives a CostRequest, applies a simplified plan cost-sharing model, and replies
with an out-of-pocket range. Always an estimate, never a quote.
"""
from uagents import Agent, Context

from agents.common import config, logic
from agents.common.models import CostRequest, CostResult

agent = Agent(
    name="careloop-cost-estimator",
    seed=config.SEEDS["cost"],
    port=config.PORTS["cost"],
    mailbox=True,
    publish_agent_details=True,
)


@agent.on_message(model=CostRequest, replies=CostResult)
async def handle_cost(ctx: Context, sender: str, msg: CostRequest):
    low, high, why = logic.estimate_cost(msg.visit_type, msg.insurance)
    ctx.logger.info(f"cost[{msg.session_id}] {msg.visit_type}/{msg.insurance} -> ${low}-${high}")
    await ctx.send(sender, CostResult(
        session_id=msg.session_id, estimate_low=low, estimate_high=high, explanation=why))


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Cost-estimator agent address: {agent.address}")


if __name__ == "__main__":
    agent.run()
