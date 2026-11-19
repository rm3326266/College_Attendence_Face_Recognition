"""
Scheduler module for the Automatic Attendance System.
Determines whether the current time falls within a scanning window.
"""

from datetime import datetime
from config import TIME_WINDOWS


def is_within_time_window(now=None):
    """
    Check if the given time (or current time) is within any scanning window.
    Returns:
        (True, slot_label) if within a window.
        (False, None) if outside all windows.
    """
    if now is None:
        now = datetime.now()

    current_hour = now.hour
    current_minute = now.minute

    for start_h, start_m, end_h, end_m, label in TIME_WINDOWS:
        start_total = start_h * 60 + start_m
        end_total = end_h * 60 + end_m
        current_total = current_hour * 60 + current_minute

        if start_total <= current_total < end_total:
            return True, label

    return False, None


def get_current_time_slot():
    """
    Get the current time slot label, or None if outside all windows.
    Convenience wrapper around is_within_time_window.
    """
    _, label = is_within_time_window()
    return label


def get_next_window(now=None):
    """
    Get the next upcoming time window.
    Returns:
        (start_time_str, label) for the next window, or (None, None) if no more today.
    """
    if now is None:
        now = datetime.now()

    current_total = now.hour * 60 + now.minute

    for start_h, start_m, end_h, end_m, label in TIME_WINDOWS:
        start_total = start_h * 60 + start_m
        if start_total > current_total:
            start_str = f"{start_h:02d}:{start_m:02d}"
            return start_str, label

    return None, None


def get_seconds_until_next_window(now=None):
    """
    Get the number of seconds until the next time window starts.
    Returns:
        seconds (int) until next window, or None if no more windows today.
    """
    if now is None:
        now = datetime.now()

    current_seconds = now.hour * 3600 + now.minute * 60 + now.second

    for start_h, start_m, end_h, end_m, label in TIME_WINDOWS:
        start_seconds = start_h * 3600 + start_m * 60
        if start_seconds > current_seconds:
            return start_seconds - current_seconds

    return None


def get_seconds_remaining_in_window(now=None):
    """
    If currently in a window, return seconds remaining. Otherwise None.
    """
    if now is None:
        now = datetime.now()

    current_seconds = now.hour * 3600 + now.minute * 60 + now.second

    for start_h, start_m, end_h, end_m, label in TIME_WINDOWS:
        start_seconds = start_h * 3600 + start_m * 60
        end_seconds = end_h * 3600 + end_m * 60
        if start_seconds <= current_seconds < end_seconds:
            return end_seconds - current_seconds

    return None


def get_all_windows_status(now=None):
    """
    Get the status of all time windows (past, active, upcoming).
    Returns a list of dicts with window info and status.
    """
    if now is None:
        now = datetime.now()

    current_total = now.hour * 60 + now.minute
    windows = []

    for start_h, start_m, end_h, end_m, label in TIME_WINDOWS:
        start_total = start_h * 60 + start_m
        end_total = end_h * 60 + end_m

        if current_total >= end_total:
            status = "completed"
        elif start_total <= current_total < end_total:
            status = "active"
        else:
            status = "upcoming"

        windows.append({
            "label": label,
            "start": f"{start_h:02d}:{start_m:02d}",
            "end": f"{end_h:02d}:{end_m:02d}",
            "status": status
        })

    return windows


def get_full_time_status(now=None):
    """
    Get a comprehensive time status for the frontend.
    Returns a dict with current state, countdowns, and all window info.
    """
    if now is None:
        now = datetime.now()

    in_window, current_slot = is_within_time_window(now)
    next_start, next_label = get_next_window(now)
    windows = get_all_windows_status(now)

    result = {
        "current_time": now.strftime("%H:%M:%S"),
        "in_window": in_window,
        "current_slot": current_slot,
        "windows": windows
    }

    if in_window:
        remaining = get_seconds_remaining_in_window(now)
        result["remaining_seconds"] = remaining
        mins, secs = divmod(remaining, 60)
        result["remaining_display"] = f"{mins}m {secs}s"
    else:
        until_next = get_seconds_until_next_window(now)
        result["next_window_start"] = next_start
        result["next_window_label"] = next_label
        result["seconds_until_next"] = until_next
        if until_next:
            mins, secs = divmod(until_next, 60)
            result["until_next_display"] = f"{mins}m {secs}s"

    return result
