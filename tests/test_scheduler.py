"""Pure scheduler unit tests, no application/server required."""
from datetime import datetime

import pytest

from scheduler import (
    get_all_windows_status,
    get_current_time_slot,
    get_full_time_status,
    get_next_window,
    get_seconds_remaining_in_window,
    get_seconds_until_next_window,
    is_within_time_window,
)


@pytest.mark.parametrize("when,expected", [
    (datetime(2026, 1, 5, 9, 59), False),
    (datetime(2026, 1, 5, 10, 0), True),
    (datetime(2026, 1, 5, 10, 14), True),
    (datetime(2026, 1, 5, 10, 15), False),
    (datetime(2026, 1, 5, 12, 5), True),
    (datetime(2026, 1, 5, 13, 30), False),
    (datetime(2026, 1, 5, 16, 14), True),
    (datetime(2026, 1, 5, 16, 15), False),
])
def test_window_boundaries(when, expected):
    assert is_within_time_window(when)[0] is expected


def test_in_window_returns_correct_slot():
    active, label = is_within_time_window(datetime(2026, 1, 5, 11, 5))
    assert active is True
    assert label == "11:00 AM - 11:15 AM"


def test_next_window_and_end_of_day():
    assert get_next_window(datetime(2026, 1, 5, 9, 30)) == (
        "10:00", "10:00 AM - 10:15 AM"
    )
    assert get_next_window(datetime(2026, 1, 5, 16, 20)) == (None, None)


def test_countdown_to_window():
    assert get_seconds_until_next_window(datetime(2026, 1, 5, 9, 59, 30)) == 30
    assert get_seconds_until_next_window(datetime(2026, 1, 5, 17, 0)) is None


def test_countdown_during_window():
    assert get_seconds_remaining_in_window(datetime(2026, 1, 5, 10, 14, 30)) == 30
    assert get_seconds_remaining_in_window(datetime(2026, 1, 5, 10, 15)) is None


def test_all_windows_progress():
    statuses = get_all_windows_status(datetime(2026, 1, 5, 11, 7))
    assert len(statuses) == 6
    assert statuses[0]["status"] == "completed"
    assert statuses[1]["status"] == "active"
    assert statuses[2]["status"] == "upcoming"


def test_full_status_inside_and_outside_window():
    active = get_full_time_status(datetime(2026, 1, 5, 10, 5))
    assert active["in_window"] is True
    assert active["remaining_seconds"] == 600
    inactive = get_full_time_status(datetime(2026, 1, 5, 9, 50))
    assert inactive["in_window"] is False
    assert inactive["seconds_until_next"] == 600


def test_current_slot_wrapper(monkeypatch):
    import scheduler
    monkeypatch.setattr(scheduler, "is_within_time_window", lambda: (True, "TEST SLOT"))
    assert get_current_time_slot() == "TEST SLOT"
