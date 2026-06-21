"""CareLoop Clinical-Evidence Agent.

When triage detects a serious/chronic condition, this agent surfaces real
recruiting clinical trials (ClinicalTrials.gov) and drug-safety info (openFDA).
Education/navigation only — options to discuss with a clinician, not advice.
"""
from uagents import Agent, Context

from agents.common import clinical, config
from agents.common.models import EvidenceRequest, EvidenceResult

agent = Agent(
    name="careloop-evidence",
    seed=config.SEEDS["evidence"],
    port=config.PORTS["evidence"],
    mailbox=True,
    publish_agent_details=True,
    readme_path=config.readme("evidence"),
    description="CareLoop Clinical-Evidence — real recruiting clinical trials (ClinicalTrials.gov) + drug-safety (openFDA) for serious/chronic conditions.",
)


@agent.on_message(model=EvidenceRequest, replies=EvidenceResult)
async def handle_evidence(ctx: Context, sender: str, msg: EvidenceRequest):
    trials, drug_notes = [], []
    try:
        if msg.condition:
            trials = clinical.search_trials(msg.condition, msg.state, msg.city, msg.limit)
    except Exception as exc:
        ctx.logger.warning(f"trials lookup failed: {exc}")
    for med in [m.strip() for m in (msg.medications or "").split(",") if m.strip()][:3]:
        try:
            drug_notes.extend(clinical.drug_safety(med))
        except Exception as exc:
            ctx.logger.warning(f"drug lookup failed for {med}: {exc}")

    ctx.logger.info(f"evidence[{msg.session_id}] condition='{msg.condition}' "
                    f"-> {len(trials)} trials, {len(drug_notes)} drug notes")
    note = "Live data: ClinicalTrials.gov + openFDA. Options to discuss with your clinician."
    await ctx.send(sender, EvidenceResult(
        session_id=msg.session_id, trials=trials, drug_notes=drug_notes, note=note))


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Evidence agent address: {agent.address}")


if __name__ == "__main__":
    agent.run()
