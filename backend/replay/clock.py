"""The replay clock as pure functions (no database, no wall clock of its own), so every rule is testable.

State: virtual_date D = "the start of day D". With a reporting delay of d days, rides through D - d are revealed.
The run covers target days first..final. The clock runs from `first` up to `final`; one step past `final` is the
"complete" state, which reveals the final day's rides and stops there (spec 9.14.4: stop and show completion,
never wrap into an unsupported period).

While playing, the clock advances one virtual day every `speed_seconds` of wall-clock time; speed changes the
playback rate only, never the time unit of the observations (spec 9.14.1).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

ACTIONS = ("start", "pause", "advance", "next_week", "jump_to_end", "select_date", "set_speed")


class ClockError(ValueError):
    """An invalid control request (the API answers 422 with this message)."""


@dataclass(frozen=True)
class Clock:
    start_date: date
    virtual_date: date
    final_date: date
    delay: int
    speed_seconds: float
    status: str                       # paused | playing | complete
    playing_since: datetime | None

    @property
    def complete_date(self) -> date:  # the virtual date of the "complete" state
        return self.final_date + timedelta(days=self.delay)

    @property
    def revealed_through(self) -> date:
        return self.virtual_date - timedelta(days=self.delay)

    @property
    def is_complete(self) -> bool:
        return self.virtual_date >= self.complete_date


def _move(c: Clock, days: int) -> Clock:
    target = min(c.virtual_date + timedelta(days=days), c.complete_date)
    done = target >= c.complete_date
    return replace(c, virtual_date=target, status="complete" if done else c.status,
                   playing_since=None if done else c.playing_since)


def at(c: Clock, now: datetime) -> Clock:
    """The clock as it stands at `now`: while playing, whole elapsed steps are applied (the remainder is kept)."""
    if c.status != "playing" or c.playing_since is None:
        return c
    steps = int((now - c.playing_since).total_seconds() // c.speed_seconds)
    if steps <= 0:
        return c
    moved = _move(c, steps)
    if moved.status == "playing":
        moved = replace(moved, playing_since=c.playing_since + timedelta(seconds=steps * c.speed_seconds))
    return moved


def control(c: Clock, action: str, now: datetime, *, days: int | None = None, to: date | None = None,
            speed_seconds: float | None = None) -> Clock:
    """Apply one control to the clock as it stands at `now`. Reset is not here: it creates a new session."""
    if action not in ACTIONS:
        raise ClockError(f"unknown action {action!r}; use one of {', '.join(ACTIONS)} (or reset)")
    c = at(c, now)
    if action == "set_speed":
        if speed_seconds is None or not 0.5 <= speed_seconds <= 120:
            raise ClockError("speed must be between 0.5 and 120 seconds per virtual day")
        return replace(c, speed_seconds=float(speed_seconds), playing_since=now if c.status == "playing" else None)
    if c.is_complete:
        if action in ("pause",):
            return c
        raise ClockError("the replay is complete (the final supported day is revealed); reset to start again")
    if action == "start":
        return replace(c, status="playing", playing_since=now)
    if action == "pause":
        return replace(c, status="paused", playing_since=None)
    if action == "advance":
        n = 1 if days is None else days
        if n < 1:
            raise ClockError("advance moves forward by at least one day")
        return _keep_playing(_move(c, n), now)
    if action == "next_week":
        return _keep_playing(_move(c, 7), now)
    if action == "jump_to_end":
        return _move(c, (c.complete_date - c.virtual_date).days)
    # select_date: forward only within this session (going back would un-reveal data; reset starts a new session)
    if to is None:
        raise ClockError("select_date needs a date")
    if to < c.virtual_date:
        raise ClockError(f"a session only moves forward; {to} is before the current day {c.virtual_date}. "
                         "Reset with that start date instead")
    if to > c.final_date:
        raise ClockError(f"{to} is after the last supported day {c.final_date}")
    return _keep_playing(_move(c, (to - c.virtual_date).days), now)


def _keep_playing(c: Clock, now: datetime) -> Clock:
    """A manual step while playing restarts the playback timer, so the next automatic step is a full step away."""
    return replace(c, playing_since=now) if c.status == "playing" else c


def new_clock(first: date, final: date, start: date | None, delay: int, speed_seconds: float) -> Clock:
    s = first if start is None else start
    if not first <= s <= final:
        raise ClockError(f"the start date must be between {first} and {final}")
    if delay != 1:
        raise ClockError("only a one-day reporting delay is supported: the frozen model was built for it, and another "
                         "delay needs rebuilt features and a newly evaluated model")
    if not 0.5 <= speed_seconds <= 120:
        raise ClockError("speed must be between 0.5 and 120 seconds per virtual day")
    return Clock(s, s, final, delay, float(speed_seconds), "paused", None)
