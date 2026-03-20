import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import AgentState

logger = logging.getLogger("discord_bot")


INVESTIGATION_TARGETS = [
    "server", "channel", "category", "thread", "forum",
    "message", "role", "permission", "member", "vc",
    "stage", "event", "automod", "invite", "webhook",
    "emoji", "sticker", "soundboard", "audit_log",
]

EXECUTION_TARGETS = [
    "server", "channel", "category", "thread", "forum",
    "message", "role", "permission", "member", "vc",
    "stage", "event", "automod", "invite", "webhook",
    "emoji", "sticker", "soundboard",
]

SYSTEM_PROMPT = """You are a Discord server management assistant.
Given a user request, determine which management areas are relevant and what actions are needed.

Respond ONLY with a JSON object with this structure:
{
  "investigation_targets": ["server", "channel", ...],
  "execution_candidates": [
    {"agent": "channel_execution", "action": "create", "params": {"name": "...", ...}}
  ]
}

Available investigation targets: {investigation_targets}
Available execution agents: {execution_targets}

Rules:
- Only include targets that are actually needed
- If the request is read-only (checking info), execution_candidates should be empty
- Be specific with params for execution candidates
- Only use agents that actually exist in the list above
"""


class MainAgent:
    """Orchestrator: parses requests, decomposes tasks, routes to agents."""

    def __init__(self, llm: BaseChatModel) -> None:
        self.llm = llm

    async def parse_request(self, state: AgentState) -> dict[str, Any]:
        """Use LLM to determine which agents to invoke and what actions to take."""
        if not state.get("request"):
            return {"investigation_targets": [], "execution_candidates": [], "todos": []}

        targets_str = ", ".join(INVESTIGATION_TARGETS)
        agents_str = ", ".join(f"{t}_execution" for t in EXECUTION_TARGETS)
        prompt = SYSTEM_PROMPT.format(
            investigation_targets=targets_str,
            execution_agents=agents_str,
        )

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=prompt),
                HumanMessage(content=state["request"]),
            ])
            import json
            return json.loads(response.content.strip().strip("```json").strip("```"))
        except Exception as e:
            logger.error("Failed to parse request with LLM: %s", e)
            return {"investigation_targets": [], "execution_candidates": [], "todos": []}

    def build_todos(self, parsed: dict[str, Any]) -> list[dict[str, Any]]:
        """Convert parsed results into structured todos."""
        todos: list[dict[str, Any]] = []
        for target in parsed.get("investigation_targets", []):
            todos.append({"agent": f"{target}_investigation", "action": "investigate", "params": {}})
        for candidate in parsed.get("execution_candidates", []):
            todos.append(candidate)
        return todos
