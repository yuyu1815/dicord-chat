from typing import Any, Literal

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """LangGraphワークフローの状態。

    Attributes:
        request: ユーザーのリクエスト文字列。
        guild_id: 対象サーバーのID。
        channel_id: リクエスト元チャンネルのID。
        user_id: リクエスト元ユーザーのID。
        user_permissions: ユーザーの権限一覧。
        todos: 実行予定のタスクリスト（承認後に凍結）。
        investigation_results: 調査エージェントの結果。
        approval_id: 承認フローの識別子。
        approved: ユーザーが承認したかどうか。
        execution_results: 実行エージェントの結果。
        final_response: 最終的な応答文字列。
        error: エラーメッセージ。
        plan_status: 計画フェーズの状態。
        planning_iteration: 現在の計画ループ反復回数。
        max_planning_iterations: 計画ループの最大反復回数。
        planner_decision: プランナーの最新判断。
        planning_history: 計画ループの履歴。
        pending_investigation_todos: 実行待ちの調査タスクリスト。
        completed_investigation_agents: 完了済みの調査エージェント名。
        draft_todos: ドラフトのタスクリスト（承認前の作業用）。
        proposed_todos: 承認提示用のタスクリスト（凍結）。
        todos_version: todosのバージョン番号。
        approval_required: 実行承認が必要かどうか。
        approval_status: 承認の状態。
        approval_summary: 承認提示用のサマリー。
        investigation_summary: 調査結果のサマリー。
    """

    # 入力
    request: str
    guild_id: int
    channel_id: int
    user_id: int
    user_permissions: dict[str, bool]

    # 処理中
    todos: list[dict[str, Any]]
    investigation_results: dict[str, Any]

    # 承認
    approval_id: str
    approved: bool

    # 実行
    execution_results: dict[str, Any]

    # 出力
    final_response: str
    error: str | None

    # 計画ループ
    plan_status: Literal[
        "planning", "investigating", "ready_for_approval",
        "approved", "rejected", "executing", "completed", "error",
    ]
    planning_iteration: int
    max_planning_iterations: int
    planner_decision: dict[str, Any]
    planning_history: list[dict[str, Any]]
    pending_investigation_todos: list[dict[str, Any]]
    completed_investigation_agents: list[str]
    draft_todos: list[dict[str, Any]]
    proposed_todos: list[dict[str, Any]]
    todos_version: int
    approval_required: bool
    approval_status: Literal["pending", "approved", "rejected", "none"]
    approval_summary: str
    investigation_summary: str
