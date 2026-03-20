"""Tests for formatters.response module."""
from typing import Any

from formatters.response import (
    compute_todos_hash,
    format_execution_candidates,
    format_final_response,
    format_results,
    split_message,
)
from graph.state import AgentState


# --- compute_todos_hash tests ---


def test_compute_todos_hash_deterministic():
    """同じtodos入力から同じハッシュが生成されること。"""
    todos = [
        {"agent": "channel_execution", "action": "create", "params": {"name": "test"}},
    ]
    h1 = compute_todos_hash(todos)
    h2 = compute_todos_hash(todos)
    assert h1 == h2
    assert isinstance(h1, str)
    assert len(h1) == 16


def test_compute_todos_hash_differs_for_different_todos():
    """異なるtodos入力から異なるハッシュが生成されること。"""
    todos_a = [{"agent": "channel_execution", "action": "create", "params": {"name": "a"}}]
    todos_b = [{"agent": "channel_execution", "action": "create", "params": {"name": "b"}}]
    assert compute_todos_hash(todos_a) != compute_todos_hash(todos_b)


def test_compute_todos_hash_empty_list():
    """空リストでもハッシュが生成されること。"""
    h = compute_todos_hash([])
    assert isinstance(h, str)
    assert len(h) == 16


def test_compute_todos_hash_key_order_invariant():
    """辞書のキー順序が異なっても同じハッシュが生成されること。"""
    import json

    todos_a = [{"params": json.loads('{"z": 1, "a": 2}')}]
    todos_b = [{"params": json.loads('{"a": 2, "z": 1}')}]
    assert compute_todos_hash(todos_a) == compute_todos_hash(todos_b)


# --- format_results tests ---


def test_format_results_empty():
    """空の結果の場合は空文字列を返すこと。"""
    assert format_results({}, title="Title") == ""


def test_format_results_with_list_value():
    """リスト値の結果が正しくフォーマットされること。"""
    results = {"channel": ["ch1", "ch2", "ch3"]}
    text = format_results(results, title="Results")
    assert "**Results**" in text
    assert "- channel:" in text
    assert "  - ch1" in text


def test_format_results_truncates_long_list():
    """10件を超えるリストは省略表示されること。"""
    items = list(range(15))
    results = {"data": items}
    text = format_results(results, title="Data")
    assert "  - 0" in text
    assert "  - 9" in text
    assert "... and 5 more" in text


def test_format_results_with_dict_value():
    """辞書値の結果が正しくフォーマットされること。"""
    results = {"role": {"count": 5, "name": "admin"}}
    text = format_results(results, title="Roles")
    assert "  - count: 5" in text
    assert "  - name: admin" in text


def test_format_results_with_error():
    """エラーを含む結果が正しくフォーマットされること。"""
    results = {"agent": {"error": "API failure"}}
    text = format_results(results, title="Errors")
    assert "ERROR - API failure" in text


def test_format_results_permission_denied():
    """permission_deniedが正しくフォーマットされること。"""
    results = {
        "agent": {
            "permission_denied": [{"action": "create", "message": "no perms"}],
            "other_key": "value",
        },
    }
    text = format_results(results, title="Results")
    assert ":x: create: no perms" in text
    assert "other_key: value" in text
    # permission_denied key itself should not appear as a line item
    assert "  - permission_denied:" not in text


def test_format_results_truncates_long_values():
    """100文字を超える値は省略表示されること。"""
    results = {"key": {"long_value": "x" * 150}}
    text = format_results(results, title="Test")
    assert "..." in text


# --- format_execution_candidates tests ---


def test_format_execution_candidates_empty():
    """タスクリストが空の場合は空文字列を返すこと。"""
    assert format_execution_candidates([]) == ""


def test_format_execution_candidates_filters_investigation():
    """調査タスクが除外されること。"""
    todos = [
        {"agent": "channel_investigation", "action": "investigate", "params": {}},
    ]
    assert format_execution_candidates(todos) == ""


def test_format_execution_candidates_execution_only():
    """実行タスクのみがフォーマットされること。"""
    todos = [
        {"agent": "channel_execution", "action": "create", "params": {"name": "test"}},
    ]
    text = format_execution_candidates(todos)
    assert "Pending Execution" in text
    assert "[channel_execution] create(name=test)" in text


def test_format_execution_candidates_mixed():
    """調査と実行が混在する場合、実行のみが表示されること。"""
    todos = [
        {"agent": "channel_investigation", "action": "investigate", "params": {}},
        {"agent": "channel_execution", "action": "create", "params": {"name": "test"}},
    ]
    text = format_execution_candidates(todos)
    assert "Pending Execution" in text
    assert "channel_execution" in text
    assert "channel_investigation" not in text


def test_format_execution_candidates_multiple():
    """複数の実行タスクが番号付きでフォーマットされること。"""
    todos = [
        {"agent": "channel_execution", "action": "create", "params": {"name": "a"}},
        {"agent": "role_execution", "action": "delete", "params": {"name": "b"}},
    ]
    text = format_execution_candidates(todos)
    assert "1. [channel_execution]" in text
    assert "2. [role_execution]" in text


# --- format_final_response tests ---


def test_format_final_response_with_execution_results():
    """実行結果を含む最終状態がフォーマットされること。"""
    state: AgentState = {
        "execution_results": {
            "channel_execution": {"success": True, "details": "Created"},
        },
        "final_response": "All done.",
    }
    text = format_final_response(state)
    assert "Execution Results" in text
    assert "channel_execution:" in text
    assert "All done." in text


def test_format_final_response_empty_state():
    """空の状態ではデフォルトテキストが返ること。"""
    text = format_final_response({})
    assert text == "Done."


def test_format_final_response_done_dot():
    """final_responseがDone.のみの場合はデフォルトテキストが返ること。"""
    state: AgentState = {"final_response": "Done."}
    assert format_final_response(state) == "Done."


def test_format_final_response_no_execution_results():
    """実行結果がない場合はfinal_responseが使われること。"""
    state: AgentState = {"final_response": "Investigation complete."}
    text = format_final_response(state)
    assert text == "Investigation complete."
    assert "Execution Results" not in text


# --- split_message tests ---


def test_split_message_short_text():
    """短いテキストは分割されないこと。"""
    assert split_message("hello", max_length=1900) == ["hello"]


def test_split_message_exact_length():
    """上限ちょうどのテキストは分割されないこと。"""
    text = "a" * 1900
    assert split_message(text, max_length=1900) == [text]


def test_split_message_one_over():
    """上限+1のテキストは分割されること。"""
    text = "a" * 1901
    chunks = split_message(text, max_length=1900)
    assert len(chunks) == 2
    assert all(len(c) <= 1900 for c in chunks)
    assert "".join(chunks) == text


def test_split_message_splits_at_newline():
    """改行位置で分割されること。"""
    # Build text where first line is short, second block is near max_length,
    # forcing a split that prefers the newline boundary.
    line1 = "aaa\n"
    line2 = "b" * 1895
    line3 = "\nccc"
    text = line1 + line2 + line3
    chunks = split_message(text, max_length=1900)
    assert len(chunks) >= 2
    # First chunk contains the first line
    assert "aaa" in chunks[0]


def test_split_message_no_newline_splits_hard():
    """改行がない場合はハードスプリットされること。"""
    text = "a" * 3800
    chunks = split_message(text, max_length=1900)
    assert len(chunks) == 2
    assert "".join(chunks) == text


def test_split_message_reconstruction():
    """分割後のチャンクを結合しても元のテキストになること（改行はストリップされるため単純結合とは限らない）。"""
    text = "line1\nline2\nline3"
    chunks = split_message(text, max_length=8)
    # Each chunk should be within limit
    assert all(len(c) <= 8 for c in chunks)
    # Content should be preserved (allowing for stripped leading newlines)
    joined = "\n".join(chunks)
    assert "line1" in joined
    assert "line2" in joined
    assert "line3" in joined


def test_split_message_default_max_length():
    """デフォルトのmax_lengthで分割されること。"""
    text = "x" * 2000
    chunks = split_message(text)
    assert all(len(c) <= 1900 for c in chunks)


# --- Backward compatibility tests ---


def test_cog_agent_cog_aliases_exist():
    """cogs.agent_cogに後方互換エイリアスが存在すること。"""
    from cogs.agent_cog import (
        _compute_todos_hash,
        _format_execution_candidates,
        _format_final_response,
        _format_results,
        _split_message,
    )
    assert callable(_compute_todos_hash)
    assert callable(_format_final_response)
    assert callable(_format_results)
    assert callable(_format_execution_candidates)
    assert callable(_split_message)


def test_cog_aliases_point_to_same_functions():
    """エイリアスがformatters.responseの関数と同一であること。"""
    from cogs.agent_cog import (
        _compute_todos_hash as cog_hash,
        _format_final_response as cog_final,
        _format_results as cog_results,
        _format_execution_candidates as cog_exec,
        _split_message as cog_split,
    )

    assert cog_hash is compute_todos_hash
    assert cog_final is format_final_response
    assert cog_results is format_results
    assert cog_exec is format_execution_candidates
    assert cog_split is split_message
