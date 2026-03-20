"""Tests for agents/ratelimit.py"""

import time

from agents.ratelimit import check_rate_limit, record_edit, _history


def test_under_limit():
    assert check_rate_limit() is None


def test_at_limit():
    record_edit()
    record_edit()
    result = check_rate_limit()
    assert result is not None
    assert result["success"] is False


def test_window_expires():
    record_edit()
    record_edit()
    # 窓枠を過去にずらす
    now = time.monotonic()
    _history[:] = [now - 601, now - 600]
    assert check_rate_limit() is None


def test_one_edit_ok():
    record_edit()
    assert check_rate_limit() is None


def test_record_increments():
    assert len(_history) == 0
    record_edit()
    assert len(_history) == 1
    record_edit()
    assert len(_history) == 2
