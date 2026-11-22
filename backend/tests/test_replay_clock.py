"""Stage 7: the replay clock rules (pure functions; no database)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from backend.replay.clock import ClockError, at, control, new_clock

T0 = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
FIRST, FINAL = date(2026, 6, 1), date(2026, 7, 31)


def fresh(start=None, speed=5.0):
    return new_clock(FIRST, FINAL, start, 1, speed)


def test_a_new_session_starts_paused_on_its_start_day_with_the_day_before_revealed():
    c = fresh()
    assert (c.virtual_date, c.revealed_through, c.status) == (FIRST, date(2026, 5, 31), "paused")
    assert fresh(date(2026, 7, 10)).revealed_through == date(2026, 7, 9)


@pytest.mark.parametrize("start", [date(2026, 5, 31), date(2026, 8, 1)])
def test_a_start_outside_june_july_is_refused(start):
    with pytest.raises(ClockError, match="between 2026-06-01 and 2026-07-31"):
        fresh(start)


def test_only_a_one_day_delay_is_accepted_and_the_reason_is_given():
    with pytest.raises(ClockError, match="one-day reporting delay"):
        new_clock(FIRST, FINAL, None, 2, 5.0)


def test_advance_next_week_and_select_date_move_forward():
    c = control(fresh(), "advance", T0)
    assert c.virtual_date == date(2026, 6, 2)
    c = control(c, "next_week", T0)
    assert c.virtual_date == date(2026, 6, 9) and c.revealed_through == date(2026, 6, 8)
    assert control(c, "select_date", T0, to=date(2026, 7, 1)).virtual_date == date(2026, 7, 1)


def test_a_session_never_moves_back_and_never_passes_the_end():
    c = control(fresh(), "next_week", T0)
    with pytest.raises(ClockError, match="only moves forward"):
        control(c, "select_date", T0, to=date(2026, 6, 2))
    end = control(c, "jump_to_end", T0)
    assert end.is_complete and end.status == "complete" and end.revealed_through == FINAL   # 31 Jul revealed, stop
    with pytest.raises(ClockError, match="complete"):
        control(end, "advance", T0)
    assert control(fresh(date(2026, 7, 30)), "advance", T0, days=50).revealed_through == FINAL  # clamped, no wrap


def test_playing_advances_one_day_per_speed_step_and_pause_stops_it():
    c = control(fresh(speed=5.0), "start", T0)
    assert at(c, T0 + timedelta(seconds=4.9)).virtual_date == FIRST            # not a full step yet
    later = at(c, T0 + timedelta(seconds=12))
    assert later.virtual_date == date(2026, 6, 3) and later.status == "playing"  # two whole steps; remainder kept
    paused = control(c, "pause", T0 + timedelta(seconds=12))
    assert at(paused, T0 + timedelta(hours=5)).virtual_date == date(2026, 6, 3)  # pause stops advancement


def test_playback_stops_at_completion():
    c = control(fresh(date(2026, 7, 30), speed=1.0), "start", T0)
    end = at(c, T0 + timedelta(hours=1))
    assert end.is_complete and end.status == "complete" and end.playing_since is None


def test_speed_changes_playback_only():
    c = control(fresh(), "set_speed", T0, speed_seconds=2)
    assert c.speed_seconds == 2 and c.virtual_date == FIRST
    with pytest.raises(ClockError, match="between 0.5 and 120"):
        control(c, "set_speed", T0, speed_seconds=0.1)
