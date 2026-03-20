from langgraph.graph import END, StateGraph

from graph.state import AgentState


def build_workflow() -> StateGraph:
    """エージェントシステムのLangGraphステートマシンを構築する。

    Returns:
        構築された :class:`StateGraph` インスタンス。
    """
    workflow = StateGraph(AgentState)

    workflow.set_entry_point("wait_for_approval")

    def wait_for_approval(state: AgentState) -> dict[str, bool]:
        """ユーザーの承認状態を確認するゲートノード。"""
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
