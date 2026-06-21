"""Throwaway client that exercises the orchestrator's Agent Chat Protocol path
(the exact entry point ASI:One uses). Sends a ChatMessage, prints the reply, exits.

Run (with the mesh up):  ./venv/bin/python -m scripts.chat_client
"""
import os
import signal
from datetime import datetime, timezone
from uuid import uuid4

from uagents import Agent, Context
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent

from agents.common import config

client = Agent(
    name="careloop-chat-tester",
    seed="careloop-chat-tester-seed-2026",
    port=8009,
    endpoint=["http://127.0.0.1:8009/submit"],
)

ORCH = config.ADDRESSES["orchestrator"]
QUESTION = os.getenv(
    "CHAT_TEST_MSG",
    "my dad has had a bad cough and low fever for five days, he is on Medicare and we are in Berkeley",
)


@client.on_event("startup")
async def go(ctx: Context):
    msg = ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=QUESTION)],
    )
    ctx.logger.info(f"Sending ChatMessage to orchestrator {ORCH[:24]}…")
    reply, status = await ctx.send_and_receive(ORCH, msg, response_type=ChatMessage, timeout=70)
    if reply is not None:
        text = " ".join(c.text for c in reply.content if hasattr(c, "text"))
        ctx.logger.info("✅ CHAT PROTOCOL REPLY RECEIVED:")
        print("\n----- ChatMessage reply from orchestrator -----")
        print(text[:600])
        print("-----------------------------------------------\n")
    else:
        ctx.logger.error(f"❌ No ChatMessage reply: {status}")
    os.kill(os.getpid(), signal.SIGINT)


if __name__ == "__main__":
    client.run()
