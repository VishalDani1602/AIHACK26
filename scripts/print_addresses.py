"""Print the deterministic agent addresses (derived from seeds in config).

Use these for your Agentverse profiles / README. Run:
  ./venv/bin/python -m scripts.print_addresses
"""
from agents.common import config

print("CareLoop agent addresses (stable across restarts):\n")
for name, addr in config.ADDRESSES.items():
    print(f"  {name:13s} {addr}")
print(
    "\nAgentverse profile URL pattern:\n"
    "  https://agentverse.ai/agents/details/<address>/profile"
)
