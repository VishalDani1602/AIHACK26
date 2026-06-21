"""CareLoop Triage Agent.

Receives a TriageRequest, runs symptom triage (hard red-flag rules + ASI:One),
and replies with a TriageResult. Navigation only — never a diagnosis.
"""
from uagents import Agent, Context

from agents.common import config, logic
from agents.common.models import TriageRequest, TriageResult

agent = Agent(
    name="careloop-triage",
    seed=config.SEEDS["triage"],
    port=config.PORTS["triage"],
    mailbox=True,
    publish_agent_details=True,
)


@agent.on_message(model=TriageRequest, replies=TriageResult)
async def handle_triage(ctx: Context, sender: str, msg: TriageRequest):
    result = logic.triage(msg.session_id, msg.symptoms, msg.patient_age)
    ctx.logger.info(
        f"triage[{msg.session_id}] urgency={result.urgency} "
        f"specialty={result.recommended_specialty} emergency={result.emergency}"
    )
    await ctx.send(sender, result)


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Triage agent address: {agent.address}")


if __name__ == "__main__":
    agent.run()
