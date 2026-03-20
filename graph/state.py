from typing import Any

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """LangGraph workflow state."""

    # Input
    request: str
    guild_id: int
    channel_id: int
    user_id: int
    user_permissions: dict[str, bool]

    # Processing
    todos: list[dict[str, Any]]
    investigation_results: dict[str, Any]

    # Approval
    approval_id: str
    approved: bool

    # Execution
    execution_results: dict[str, Any]

    # Output
    final_response: str
    error: str | None
