from langgraph.graph import END, StateGraph

from graph.state import AgentState


def build_workflow() -> StateGraph:
    """Build the LangGraph state machine for the agent system."""
    workflow = StateGraph(AgentState)

    workflow.set_entry_point("wait_for_approval")

    def wait_for_approval(state: AgentState) -> dict[str, bool]:
        """Gate node: check if user has approved execution."""
        approved = state.get("approved", False)
        return {"approved": approved}

    workflow.add_node("wait_for_approval", wait_for_approval)

    workflow.add_conditional_edges(
        "wait_for_approval",
        lambda state: "executed" if state.get("approved") else "ended",
        {
            "executed": END,
            "ended": END,
        },
    )

    return workflow
