"""CareLoop Scheduler Agent.

Receives a BookingRequest, creates a confirmation + an iCalendar invite, and
replies with a BookingResult. (Mock booking; the .ics is real and importable.)
"""
from uagents import Agent, Context

from agents.common import config, logic
from agents.common.models import BookingRequest, BookingResult

agent = Agent(
    name="careloop-scheduler",
    seed=config.SEEDS["scheduler"],
    port=config.PORTS["scheduler"],
    mailbox=True,
    publish_agent_details=True,
    readme_path=config.readme("scheduler"),
    description="CareLoop Scheduler — booking confirmation + real iCalendar (.ics) invite.",
)


@agent.on_message(model=BookingRequest, replies=BookingResult)
async def handle_booking(ctx: Context, sender: str, msg: BookingRequest):
    code, summary, ics = logic.book(
        msg.session_id, msg.provider_name, msg.provider_address, msg.slot,
        msg.patient_name, msg.reason)
    ctx.logger.info(f"scheduler[{msg.session_id}] booked {msg.provider_name} -> {code}")
    await ctx.send(sender, BookingResult(
        session_id=msg.session_id, confirmation_code=code, summary=summary, ics=ics))


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Scheduler agent address: {agent.address}")


if __name__ == "__main__":
    agent.run()
