"""Discord向けのレスポンスフォーマット関数群。

cogs.agent_cog から抽出された純粋関数。Discordオブジェクトへの依持たず、
テキスト変換とメッセージ分割のみを担当する。
"""
import hashlib
import json
import logging
from typing import Any

from graph.state import (
    AgentState,
    TodoProgress,
    TODO_STATUS_EMOJI,
    is_execution_todo,
)
from i18n import t

logger = logging.getLogger("discord_bot")


def compute_todos_hash(todos: list[dict[str, Any]]) -> str:
    """承認対象タスクリストの整合性チェック用ハッシュを計算する。

    Args:
        todos: 凍結された実行タスクリスト。

    Returns:
        SHA-256 16進数ダイジェスト文字列（先頭16文字）。
    """
    payload = json.dumps(todos, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def format_final_response(state: AgentState) -> str:
    """最終状態からDiscord向けのレスポンスを構築する。

    Args:
        state: ワークフローの最終状態。

    Returns:
        フォーマットされた文字列。
    """
    locale = state.get("locale", "en")
    parts = []

    investigation_summary = state.get("investigation_summary", "")
    if investigation_summary:
        parts.append(investigation_summary)

    execution_results = state.get("execution_results", {})
    if execution_results:
        parts.append(format_results(execution_results, title=t("fmt.execution_results", locale=locale), locale=locale))

    final_response = state.get("final_response", "")
    if final_response and final_response != t("fmt.done", locale=locale):
        parts.append(final_response)

    return "\n".join(parts) if parts else t("fmt.done", locale=locale)


def format_results(results: dict[str, Any], title: str, locale: str = "en") -> str:
    """調査/実行結果をDiscord向けにフォーマットする。

    Args:
        results: エージェントの実行結果。
        title: セクションタイトル。
        locale: 言語コード。

    Returns:
        フォーマットされた文字列。
    """
    if not results:
        return ""

    lines = [f"**{title}**\n"]
    for key, value in results.items():
        if isinstance(value, dict) and "error" in value:
            lines.append(f"- {key}: {t('fmt.error_marker', locale=locale, error=value['error'])}")
            continue
        lines.append(f"- {key}:")
        if isinstance(value, list):
            for item in value[:10]:
                lines.append(f"  - {item}")
            if len(value) > 10:
                lines.append(f"  - {t('fmt.and_more', locale=locale, count=len(value) - 10)}")
        elif isinstance(value, dict):
            denied = value.get("permission_denied", [])
            if denied:
                for d in denied:
                    lines.append(f"  - :x: {d['action']}: {d['message']}")
            for k, v in value.items():
                if k == "permission_denied":
                    continue
                text = str(v)
                if len(text) > 100:
                    text = text[:100] + "..."
                lines.append(f"  - {k}: {text}")

    return "\n".join(lines)


def format_execution_candidates(todos: list[dict[str, Any]], locale: str = "en") -> str:
    """ユーザー確認用の実行候補リストをフォーマットする。

    Args:
        todos: 全タスクリスト。
        locale: 言語コード。

    Returns:
        フォーマットされた文字列。
    """
    execution_todos = [t for t in todos if is_execution_todo(t)]
    if not execution_todos:
        return ""

    lines = [t("fmt.pending_execution", locale=locale)]
    for i, todo in enumerate(execution_todos, 1):
        action = todo.get("action", "unknown")
        params = todo.get("params", {})
        agent = todo.get("agent", "unknown")
        param_str = ", ".join(f"{k}={v}" for k, v in params.items())
        lines.append(f"{i}. [{agent}] {action}({param_str})")

    return "\n".join(lines)


def split_message(text: str, max_length: int = 1900) -> list[str]:
    """Discordのメッセージ上限に合わせてテキストを分割する。

    Args:
        text: 分割対象の文字列。
        max_length: チャンクの最大長。

    Returns:
        分割された文字列のリスト。
    """
    if len(text) <= max_length:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_length)
        if split_at == -1:
            split_at = max_length
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


def format_progress_plan(
    request: str,
    todo_progress: list[TodoProgress],
    locale: str = "en",
) -> str:
    """Plan message 本文を生成する。絵文字付き checklist を含む。

    Args:
        request: ユーザーのリクエスト文字列。
        todo_progress: 各 todo の進捗リスト。
        locale: 言語コード。

    Returns:
        フォーマットされた plan メッセージ本文。
    """
    parts = [t("cog.request_header", locale=locale, request=request)]

    if todo_progress:
        header = t("fmt.pending_execution", locale=locale)
        lines = [header]
        for i, tp in enumerate(todo_progress, 1):
            emoji = TODO_STATUS_EMOJI.get(tp.get("status", "pending"), "\u23f3")
            label = tp.get("label", "unknown")
            lines.append(f"{emoji} {i}. {label}")
        parts.append("\n".join(lines))

    return "\n".join(parts)


def format_thread_progress_event(
    event: dict[str, Any],
    locale: str = "en",
) -> str:
    """スレッド内の逐次ログ文面を生成する。

    Args:
        event: 進捗イベント辞書。
            必須キー: ``type`` (``"start"``, ``"success"``, ``"error"``)。
            任意キー: ``agent``, ``label``, ``detail``。
        locale: 言語コード。

    Returns:
        フォーマットされたログ文字列。
    """
    event_type = event.get("type", "")
    label = event.get("label", "")
    detail = event.get("detail", "")

    if event_type == "start":
        return t("progress.agent_start", locale=locale, label=label)
    if event_type == "success":
        return t("progress.agent_success", locale=locale, label=label)
    if event_type == "error":
        return t("progress.agent_error", locale=locale, label=label, detail=detail)
    return f"Unknown event: {event_type or 'none'}"
