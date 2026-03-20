"""Tests for agents/ratelimit.py"""

import time

from agents.ratelimit import check_rate_limit, record_edit, _history

CH_A = 100
CH_B = 200


def test_under_limit():
    assert check_rate_limit(CH_A) is None


def test_at_limit():
    record_edit(CH_A)
    record_edit(CH_A)
    result = check_rate_limit(CH_A)
    assert result is not None
    assert result["success"] is False


def test_different_channels_independent():
    record_edit(CH_A)
    record_edit(CH_A)
    # CH_A is at limit, but CH_B should be fine
    assert check_rate_limit(CH_B) is None


def test_window_expires():
    record_edit(CH_A)
    record_edit(CH_A)
    now = time.monotonic()
    _history[CH_A][:] = [now - 601, now - 600]
    assert check_rate_limit(CH_A) is None


def test_one_edit_ok():
    record_edit(CH_A)
    assert check_rate_limit(CH_A) is None


def test_record_creates_channel_key():
    record_edit(CH_A)
    assert CH_A in _history
    assert len(_history[CH_A]) == 1
