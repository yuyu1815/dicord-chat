from typing import Any

from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """LangGraphワークフローの状態。

    Attributes:
        request: ユーザーのリクエスト文字列。
        guild_id: 対象サーバーのID。
        channel_id: リクエスト元チャンネルのID。
        user_id: リクエスト元ユーザーのID。
        user_permissions: ユーザーの権限一覧。
        todos: 実行予定のタスクリスト。
        investigation_results: 調査エージェントの結果。
        approval_id: 承認フローの識別子。
        approved: ユーザーが承認したかどうか。
        execution_results: 実行エージェントの結果。
        final_response: 最終的な応答文字列。
        error: エラーメッセージ。
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
