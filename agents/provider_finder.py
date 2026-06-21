"""CareLoop Provider-Finder Agent.

Receives a ProviderRequest, queries the public CMS NPPES NPI registry for real
providers matching the taxonomy + location, and replies with a ProviderResult.
Availability / insurance acceptance are synthesized (NPPES has no such data).
"""
from uagents import Agent, Context

from agents.common import config, nppes
from agents.common.models import ProviderRequest, ProviderResult

agent = Agent(
    name="careloop-provider-finder",
    seed=config.SEEDS["provider"],
    port=config.PORTS["provider"],
    mailbox=True,
    publish_agent_details=True,
)


@agent.on_message(model=ProviderRequest, replies=ProviderResult)
async def handle_provider(ctx: Context, sender: str, msg: ProviderRequest):
    try:
        providers = nppes.search_providers(
            msg.taxonomy, msg.city, msg.state, msg.postal_code, msg.insurance, msg.limit
        )
        note = "Live provider data from the CMS NPPES NPI registry."
        if not providers:
            providers = nppes.fallback_providers(msg.taxonomy, msg.city, msg.limit)
            note = "No NPPES match — showing sample providers."
    except Exception as exc:
        ctx.logger.warning(f"NPPES lookup failed: {exc}; using fallback list")
        providers = nppes.fallback_providers(msg.taxonomy, msg.city, msg.limit)
        note = "NPPES unavailable — showing sample providers."

    ctx.logger.info(f"provider[{msg.session_id}] taxonomy={msg.taxonomy} -> {len(providers)} results")
    await ctx.send(sender, ProviderResult(session_id=msg.session_id, providers=providers, note=note))


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Provider-finder agent address: {agent.address}")


if __name__ == "__main__":
    agent.run()
