import uuid
from typing import Any, Literal

from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# Agent-kind classification
# ---------------------------------------------------------------------------

AgentKind = Literal["investigation", "execution"]


# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------

TodoStatus = Literal["pending", "approved", "in_progress", "completed", "failed", "skipped"]

TODO_STATUS_EMOJI: dict[TodoStatus, str] = {
    "pending": "\u23f3",       # ⏳
    "approved": "\u23f3",      # ⏳
    "in_progress": "\U0001f504",  # 🔄
    "completed": "\u2705",     # ✅
    "failed": "\u274c",        # ❌
    "skipped": "\u23ed\ufe0f", # ⏭️
}


class TodoProgress(TypedDict, total=True):
    """Single todo item for progress display.

    Attributes:
        todo_id: Unique identifier for this todo (short UUID).
        agent: Agent name (e.g. ``"channel_execution"``).
        action: Action name.
        params: Action parameters.
        status: Current status emoji key.
        label: Human-readable label for display (max ~40 chars).
    """
    todo_id: str
    agent: str
    action: str
    params: dict[str, Any]
    status: TodoStatus
    label: str


def build_todo_progress(todos: list["Todo"]) -> list[TodoProgress]:
    """Create a list of TodoProgress from execution todos.

    Each item gets a unique ``todo_id`` (8-char hex from UUID) so that
    even multiple todos for the same agent can be tracked independently.

    Args:
        todos: Execution todo list (usually ``proposed_todos``).

    Returns:
        List of TodoProgress with ``status="pending"``.
    """
    result: list[TodoProgress] = []
    for todo in todos:
        agent = todo.get("agent", "unknown")
        action = todo.get("action", "unknown")
        params = todo.get("params", {})
        todo_id = uuid.uuid4().hex[:8]
        # Short label: action + optional name param, capped at 40 chars
        name = params.get("name")
        if name:
            label = f"{action}({name})"
        else:
            label = action
        if len(label) > 40:
            label = label[:37] + "..."
        result.append({
            "todo_id": todo_id,
            "agent": agent,
            "action": action,
            "params": params,
            "status": "pending",
            "label": label,
        })
    return result


def classify_agent_kind(agent_name: str) -> AgentKind | None:
    """エージェント名から種別（investigation / execution）を判定する。

    Args:
        agent_name: ``"channel_investigation"`` や ``"role_execution"`` 等。

    Returns:
        ``"investigation"`` または ``"execution"``。判定不能な場合は ``None``。
    """
    if agent_name.endswith("_investigation"):
        return "investigation"
    if agent_name.endswith("_execution"):
        return "execution"
    return None


def agent_target_from_name(agent_name: str) -> str:
    """エージェント名からターゲット部分を取り出す。

    例: ``"channel_investigation"`` -> ``"channel"``

    Args:
        agent_name: エージェント名。

    Returns:
        ターゲット文字列。変換できない場合はそのまま返す。
    """
    for suffix in ("_investigation", "_execution"):
        if agent_name.endswith(suffix):
            return agent_name[: -len(suffix)]
    return agent_name


# ---------------------------------------------------------------------------
# Todo helpers
# ---------------------------------------------------------------------------

class Todo(TypedDict, total=False):
    """ワークフロー内の単一タスク項目。

    Attributes:
        agent: エージェント名（例: ``"channel_execution"``）。
        action: 実行アクション名。
        params: アクションに渡すパラメータ。
        _blocked: 内部で権限不足を示すフラグ。
    """
    agent: str
    action: str
    params: dict[str, Any]
    _blocked: bool


def is_execution_todo(todo: Todo) -> bool:
    """todoが実行タスクかどうかを判定する。

    ``todo["agent"]`` に ``"investigation"`` を含まない場合に ``True``。

    Args:
        todo: 判定対象のタスク辞書。

    Returns:
        実行タスクの場合 ``True``。
    """
    return "investigation" not in todo.get("agent", "")


def is_investigation_todo(todo: Todo) -> bool:
    """todoが調査タスクかどうかを判定する。

    Args:
        todo: 判定対象のタスク辞書。

    Returns:
        調査タスクの場合 ``True``。
    """
    return "investigation" in todo.get("agent", "")


# ---------------------------------------------------------------------------
# Planner decision status constants
# ---------------------------------------------------------------------------

PLANNER_STATUS_NEED_INVESTIGATION: Literal["need_investigation"] = "need_investigation"
PLANNER_STATUS_READY_FOR_APPROVAL: Literal["ready_for_approval"] = "ready_for_approval"
PLANNER_STATUS_DONE_NO_EXECUTION: Literal["done_no_execution"] = "done_no_execution"
PLANNER_STATUS_NEED_HISTORY_DETAIL: Literal["need_history_detail"] = "need_history_detail"
PLANNER_STATUS_ERROR: Literal["error"] = "error"

VALID_PLANNER_STATUSES: frozenset[str] = frozenset({
    PLANNER_STATUS_NEED_INVESTIGATION,
    PLANNER_STATUS_READY_FOR_APPROVAL,
    PLANNER_STATUS_DONE_NO_EXECUTION,
    PLANNER_STATUS_NEED_HISTORY_DETAIL,
    PLANNER_STATUS_ERROR,
})


# ---------------------------------------------------------------------------
# Workflow state
# ---------------------------------------------------------------------------

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
        progress_plan_message_id: 進捗表示用 plan メッセージのID。
        progress_thread_id: 進捗ログ用スレッドのID。
        progress_events: 進捗イベントのログ。
        todo_progress: 各 todo の進捗表示用データ。
    """

    # 入力
    request: str
    guild_id: int
    channel_id: int
    user_id: int
    user_permissions: dict[str, bool]
    locale: str
    bot: Any

    # 会話履歴
    conversation_history: list[dict[str, Any]]
    history_detail: str

    # 処理中
    todos: list[Todo]
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
        "done_no_execution",
        "approved", "rejected", "executing", "completed",
        "completed_with_errors", "error",
    ]
    planning_iteration: int
    max_planning_iterations: int
    planner_decision: dict[str, Any]
    planning_history: list[dict[str, Any]]
    pending_investigation_todos: list[Todo]
    completed_investigation_agents: list[str]
    draft_todos: list[Todo]
    proposed_todos: list[Todo]
    todos_version: int
    approval_required: bool
    approval_status: Literal["pending", "approved", "rejected", "none"]
    approval_summary: str
    investigation_summary: str

    # 進捗表示
    progress_plan_message_id: int
    progress_thread_id: int
    progress_events: list[dict[str, Any]]
    todo_progress: list[TodoProgress]
