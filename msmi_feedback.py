"""Leakage-safe expected-MSMI utility from mature public feedback.

The expected value is factorised into two directional acceptance estimates,
the observed date rate after mutual acceptance, and the observed on-time
second-meeting-intention rate after a date. It is a ranking estimate, not a
claim of calibrated pair-level probabilities.
"""

from __future__ import annotations

import hashlib
import json
import math

from directional_learning import (
    directional_features,
    model_is_ready,
    predict_direction,
)
from matching_core import transparent_pair_score


MAX_SEEN_EVENTS = 4096
MAX_PENDING_SECOND_EVENTS = 512


def _empty_state():
    return {
        "version": 1,
        "acceptance_response_events": 0,
        "acceptance_responses": 0,
        "date_labels": 0,
        "date_positive": 0,
        "second_labels": 0,
        "second_positive": 0,
        "seen_events": [],
        "date_days": {},
        "second_seen_members": {},
    }


def ensure_msmi_state(memory):
    current = memory.get("msmi_feedback")
    if not isinstance(current, dict) or current.get("version") != 1:
        current = _empty_state()
        memory["msmi_feedback"] = current
    for key, value in _empty_state().items():
        current.setdefault(key, value)
    if not isinstance(current.get("date_days"), dict):
        current["date_days"] = {}
    if not isinstance(current.get("second_seen_members"), dict):
        current["second_seen_members"] = {}
    for key in (
        "acceptance_response_events", "acceptance_responses",
        "date_labels", "date_positive", "second_labels", "second_positive",
    ):
        value = current.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            current[key] = 0
    if not isinstance(current.get("seen_events"), list):
        current["seen_events"] = []
    current["seen_events"] = [item for item in current["seen_events"] if isinstance(item, str)][-MAX_SEEN_EVENTS:]
    return current


def _fingerprint(event):
    fields = (
        "introduction_id", "member_id", "event", "value",
        "occurred_day", "observed_day", "missing_reason",
    )
    stable = {key: event.get(key) for key in fields}
    return hashlib.sha256(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _rate(successes, labels):
    """Beta(1, 1)-smoothed rate; safe at zero and all-success boundaries."""
    return (float(successes) + 1.0) / (float(labels) + 2.0)


def observe_msmi_feedback(state, memory):
    """Update only from released, explicit, mature outcome events.

    Null second-intention events are recorded for cleanup but never treated as
    a negative label. A late explicit yes is a zero for the on-time outcome,
    not a negative preference label.
    """
    learning = ensure_msmi_state(memory)
    day = int(state.get("day", 0))
    seen = set(learning.get("seen_events") or ())
    events = [
        event for event in (state.get("feedback") or ())
        if isinstance(event, dict)
        and isinstance(event.get("observed_day"), int)
        and event["observed_day"] <= day
    ]
    introductions = {
        str(item.get("introduction_id")): item
        for item in (state.get("introductions") or ())
        if isinstance(item, dict) and item.get("introduction_id") is not None
    }
    # Date events precede second-intention events in the outcome funnel. Sort
    # explicitly so this remains true even if a producer changes JSON order.
    events.sort(key=lambda event: (
        event.get("observed_day", 0),
        0 if event.get("event") == "date_happened" else 1,
        str(event.get("introduction_id", "")),
        str(event.get("member_id", "")),
    ))

    for event in events:
        if event.get("event") != "introduction_response":
            continue
        value = event.get("value")
        if value not in ("yes", "no", None):
            continue
        if value is None and event.get("missing_reason") != "no_response":
            continue
        intro = introductions.get(str(event.get("introduction_id")))
        if not intro or event.get("member_id") not in (intro.get("user_a"), intro.get("user_b")):
            continue
        fingerprint = _fingerprint(event)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        learning["acceptance_response_events"] += 1
        learning["acceptance_responses"] += int(value in ("yes", "no"))

    for event in events:
        if (
            event.get("event") != "date_happened"
            or event.get("member_id") is not None
            or not isinstance(event.get("value"), bool)
        ):
            continue
        fingerprint = _fingerprint(event)
        if fingerprint in seen:
            continue
        intro_id = event.get("introduction_id")
        intro = introductions.get(str(intro_id))
        assigned_day = intro.get("assigned_day") if intro else None
        occurred_day = event.get("occurred_day")
        if not isinstance(assigned_day, int) or not isinstance(occurred_day, int):
            continue
        if occurred_day < assigned_day:
            continue
        seen.add(fingerprint)
        label = int(event["value"] is True and occurred_day - assigned_day <= 30)
        learning["date_labels"] += 1
        learning["date_positive"] += label
        if intro_id is not None and label == 1:
            learning["date_days"][str(intro_id)] = occurred_day
        elif intro_id is not None:
            learning["date_days"].pop(str(intro_id), None)
            learning["second_seen_members"].pop(str(intro_id), None)

    for event in events:
        if event.get("event") != "second_meeting_intention":
            continue
        fingerprint = _fingerprint(event)
        if fingerprint in seen:
            continue
        intro_id = event.get("introduction_id")
        member_id = event.get("member_id")
        intro = introductions.get(str(intro_id))
        if not intro or member_id not in (intro.get("user_a"), intro.get("user_b")):
            continue
        date_day = learning["date_days"].get(str(intro_id))
        if date_day is None or member_id is None:
            continue
        seen.add(fingerprint)

        occurred_day = event.get("occurred_day")
        if event.get("value") in ("yes", "no") and isinstance(occurred_day, int):
            elapsed = occurred_day - date_day
            on_time_yes = int(
                event["value"] == "yes" and 0 <= elapsed <= 3
            )
        elif event.get("value") is None and event.get("missing_reason") == "no_response":
            # This is a zero for the evaluated MSMI outcome funnel, not a
            # negative preference label. Preference learning excludes it.
            on_time_yes = 0
        else:
            on_time_yes = None
        if on_time_yes is not None:
            learning["second_labels"] += 1
            learning["second_positive"] += on_time_yes

        key = str(intro_id)
        observed_members = set(learning["second_seen_members"].get(key, ()))
        observed_members.add(str(member_id))
        if len(observed_members) >= 2:
            learning["date_days"].pop(key, None)
            learning["second_seen_members"].pop(key, None)
        else:
            learning["second_seen_members"][key] = sorted(observed_members)

    learning["seen_events"] = sorted(seen)[-MAX_SEEN_EVENTS:]
    if len(learning["date_days"]) > MAX_PENDING_SECOND_EVENTS:
        keep = sorted(learning["date_days"].items(), key=lambda item: (item[1], item[0]))
        remove = keep[:len(keep) - MAX_PENDING_SECOND_EVENTS]
        for intro_id, _ in remove:
            learning["date_days"].pop(intro_id, None)
            learning["second_seen_members"].pop(intro_id, None)
    return learning


def expected_msmi_utility(left, right, acceptance_learning, outcome_learning):
    """Return a bounded factorised estimate of a pair's eventual MSMI chance."""
    labels = int(acceptance_learning.get("labels", 0))
    positives = int(acceptance_learning.get("positive_labels", 0))
    conditional_yes_rate = _rate(positives, labels)
    # Keep the transparent soft-alignment signal useful before feedback is
    # plentiful. It acts as a bounded relative modifier around the smoothed
    # global acceptance baseline; it is not interpreted as a calibrated
    # probability.
    alignment = transparent_pair_score(left, right)
    relative_alignment = (0.5 + 0.5 * alignment) / 0.75
    conditional_baseline = min(1.0, max(0.0, conditional_yes_rate * relative_alignment))
    if model_is_ready(acceptance_learning):
        scored = max(1, int(acceptance_learning.get("scored_labels", 0)))
        model_brier = float(acceptance_learning.get("brier_sum", 0.0)) / scored
        base_brier = float(acceptance_learning.get("baseline_brier_sum", 0.0)) / scored
        confidence = min(1.0, max(0.0, (base_brier - model_brier) / 0.05))
        left_conditional = conditional_baseline + confidence * (
            predict_direction(directional_features(left, right), acceptance_learning) - conditional_baseline
        )
        right_conditional = conditional_baseline + confidence * (
            predict_direction(directional_features(right, left), acceptance_learning) - conditional_baseline
        )
    else:
        left_conditional = right_conditional = conditional_baseline

    response_rate = _rate(
        outcome_learning.get("acceptance_responses", 0),
        outcome_learning.get("acceptance_response_events", 0),
    )
    left_to_right = response_rate * left_conditional
    right_to_left = response_rate * right_conditional

    date_rate = _rate(
        outcome_learning.get("date_positive", 0),
        outcome_learning.get("date_labels", 0),
    )
    second_rate = _rate(
        outcome_learning.get("second_positive", 0),
        outcome_learning.get("second_labels", 0),
    )
    value = left_to_right * right_to_left * date_rate * second_rate * second_rate
    if not math.isfinite(value):
        raise ValueError("non-finite expected MSMI utility")
    return round(min(1.0, max(0.0, value)), 10)


def msmi_model_diagnostics(outcome_learning):
    """Compact diagnostics suitable for policy memory and experiment reports."""
    return {
        "mature_intro_response_events": int(outcome_learning.get("acceptance_response_events", 0)),
        "intro_response_rate_smoothed": round(_rate(
            outcome_learning.get("acceptance_responses", 0),
            outcome_learning.get("acceptance_response_events", 0),
        ), 6),
        "date_labels": int(outcome_learning.get("date_labels", 0)),
        "date_rate_smoothed": round(_rate(
            outcome_learning.get("date_positive", 0),
            outcome_learning.get("date_labels", 0),
        ), 6),
        "on_time_second_labels": int(outcome_learning.get("second_labels", 0)),
        "on_time_second_rate_smoothed": round(_rate(
            outcome_learning.get("second_positive", 0),
            outcome_learning.get("second_labels", 0),
        ), 6),
        "pending_second_feedback": len(outcome_learning.get("date_days", {})),
        "utility_is_factorised_uncalibrated_estimate": True,
    }
