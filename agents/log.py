"""リクエスト単位のログ出力。logs/<guild_id>/<user_id>/ に保存する。"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from graph.state import AgentState

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"

_agent_call_logger = logging.getLogger("discord_bot.agent_calls")


def _ensure_log_dir(state: AgentState) -> Path:
    """guild_id/user_id ごとのログディレクトリを作成して返す。"""
    guild_id = state.get("guild_id", 0)
    user_id = state.get("user_id", 0)
    log_dir = LOGS_DIR / str(guild_id) / str(user_id)
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_session_log_dir(state: AgentState) -> Path:
    """現在のセッションのログディレクトリを返す。"""
    return _ensure_log_dir(state)


def get_session_log_path(state: AgentState) -> Path:
    """現在のセッションのai_io JSONLパスを返す。"""
    log_dir = _ensure_log_dir(state)
    session_id = state.get("approval_id", "unknown")
    return log_dir / f"{session_id}_ai_io.jsonl"


def _write_jsonl_sync(path: Path, data: str) -> None:
    """JSONL行を同期でファイルに追記する（スレッドプールから呼び出す）。"""
    with path.open("a", encoding="utf-8") as f:
        f.write(data)


async def append_ai_jsonl(record: dict[str, Any], state: AgentState) -> None:
    """AIの送受信レコードをJSONLに追記する（非同期）。"""
    log_path = get_session_log_path(state)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    await asyncio.to_thread(_write_jsonl_sync, log_path, line)


async def log_ai_exchange(
    kind: str,
    state: AgentState,
    messages: list[Any],
    *,
    response_text: str | None = None,
    parsed: dict[str, Any] | None = None,
    error: str | None = None,
    usage: dict[str, Any] | None = None,
) -> None:
    """LLM送受信内容をJSONLで保存する（非同期）。"""
    record: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "user_id": state.get("user_id"),
        "guild_id": state.get("guild_id"),
        "approval_id": state.get("approval_id"),
        "messages": [
            {
                "type": message.__class__.__name__,
                "content": message.content,
            }
            for message in messages
        ],
    }
    if response_text is not None:
        record["response"] = response_text
    if parsed is not None:
        record["parsed"] = parsed
    if error is not None:
        record["error"] = error
    if usage is not None:
        record["usage"] = usage
    await append_ai_jsonl(record, state)


def _safe_dict(d: Any) -> dict[str, Any]:
    """JSONシリアライズ可能な辞書に変換する。"""
    if not isinstance(d, dict):
        return str(d)
    return {k: _safe_dict(v) if isinstance(v, (dict, list)) else v for k, v in d.items()}


async def log_agent_call(
    agent_name: str,
    phase: str,
    state: AgentState,
    *,
    guild: Any,
    action: str | None = None,
    result: Any = None,
) -> None:
    """エージェント呼び出しのデバッグログをJSONLに保存する（非同期）。"""
    todos = [
        {
            "action": todo.get("action"),
            "blocked": bool(todo.get("_blocked")),
            "params_keys": sorted(todo.get("params", {}).keys()),
        }
        for todo in state.get("todos", [])
        if todo.get("agent") == agent_name
    ]
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent_name,
        "phase": phase,
        "guild_id": getattr(guild, "id", None),
        "user_id": state.get("user_id"),
        "approval_id": state.get("approval_id"),
        "approval_status": state.get("approval_status"),
        "approved": state.get("approved"),
        "todo_count": len(todos),
        "todos": todos,
    }
    if action is not None:
        payload["action"] = action
    if isinstance(result, dict):
        payload["result_keys"] = sorted(result.keys())
        payload["success"] = result.get("success")

    # Write to per-session JSONL (offloaded to thread pool)
    log_path = get_session_log_path(state)
    try:
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        await asyncio.to_thread(_write_jsonl_sync, log_path, line)
    except (TypeError, ValueError):
        # Fallback: strip non-serializable fields
        safe = {k: v for k, v in payload.items() if not callable(v)}
        line = json.dumps(safe, ensure_ascii=False, default=str) + "\n"
        await asyncio.to_thread(_write_jsonl_sync, log_path, line)

    # Also emit via stdlib logger for console/filter-based routing (sync is fine)
    _agent_call_logger.info("agent_call %s", payload)
