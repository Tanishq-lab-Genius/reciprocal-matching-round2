"""Leakage-safe online learning from explicit directional acceptance feedback.

Only action-time observable features and released yes/no feedback are used.
Unknown and censored responses never become negative labels.
"""

from __future__ import annotations

import hashlib
import json
import math

from matching_core import transparent_pair_score


SOFT_CATEGORIES = {
    "relationship_goal": ("long_term", "exploring"),
    "relationship_pace": ("slow", "steady", "quick"),
    "lifestyle": ("quiet", "mixed", "social"),
    "conversations": ("ideas", "stories", "practical", "playful"),
    "emotional_availability": ("ready", "taking_time"),
    "space_for_relationship": ("limited", "moderate", "ample"),
    "relocate": ("yes", "no", "unsure"),
}
FEATURE_COUNT = 10 + sum(5 + 2 * len(values) for values in SOFT_CATEGORIES.values())
MIN_LABELS = 40
MAX_PENDING_ACTIONS = 256
MAX_LINKED_INTRODUCTIONS = 256
MAX_SEEN_EVENTS = 2048


def _empty_state():
    return {
        "version": 2,
        "weights": [0.0] * FEATURE_COUNT,
        "labels": 0,
        "positive_labels": 0,
        "negative_labels": 0,
        "seen_events": [],
        "pending_actions": [],
        "introductions": {},
        "brier_sum": 0.0,
        "baseline_brier_sum": 0.0,
        "log_loss_sum": 0.0,
        "scored_labels": 0,
        "direction_scores": {
            "left_to_right": {"scored_labels": 0, "brier_sum": 0.0},
            "right_to_left": {"scored_labels": 0, "brier_sum": 0.0},
        },
    }


def ensure_learning_state(memory):
    current = memory.get("directional_learning")
    if not isinstance(current, dict) or current.get("version") != 2:
        current = _empty_state()
        memory["directional_learning"] = current
    if len(current.get("weights", ())) != FEATURE_COUNT:
        current = _empty_state()
        memory["directional_learning"] = current
    direction_scores = current.get("direction_scores")
    if not isinstance(direction_scores, dict):
        direction_scores = {}
        current["direction_scores"] = direction_scores
    for direction in ("left_to_right", "right_to_left"):
        bucket = direction_scores.get(direction)
        if not isinstance(bucket, dict):
            bucket = {}
            direction_scores[direction] = bucket
        bucket.setdefault("scored_labels", 0)
        bucket.setdefault("brier_sum", 0.0)
    return current


def directional_features(source, target):
    """Encode one person's observable profile relative to the proposed partner."""
    source_fields = source.get("fields") or {}
    target_fields = target.get("fields") or {}
    source_age = float(source.get("age", 0))
    target_age = float(target.get("age", 0))
    source_min = source_fields.get("age_min")
    source_max = source_fields.get("age_max")
    age_range = max(1.0, float((source_max or source_age) - (source_min or source_age)))
    lower_margin = (target_age - float(source_min)) / age_range if source_min is not None else 0.0
    upper_margin = (float(source_max) - target_age) / age_range if source_max is not None else 0.0
    source_schedule = set(source_fields.get("schedule") or ())
    target_schedule = set(target_fields.get("schedule") or ())
    schedule_union = source_schedule.union(target_schedule)
    source_status = source.get("field_status") or {}
    target_status = target.get("field_status") or {}

    values = [
        1.0,
        max(-1.0, min(1.0, (target_age - source_age) / 25.0)),
        min(1.0, abs(target_age - source_age) / 25.0),
        max(-1.0, min(1.0, lower_margin)),
        max(-1.0, min(1.0, upper_margin)),
        float(source.get("zone") == target.get("zone")),
        len(source_schedule.intersection(target_schedule)) / max(1, len(schedule_union)),
        float(source_fields.get("relationship_structure") == target_fields.get("relationship_structure")),
        float(source_fields.get("wants_children") == target_fields.get("wants_children")),
        float(source_fields.get("wants_children") is None or target_fields.get("wants_children") is None),
    ]
    for field in SOFT_CATEGORIES:
        source_value = source_fields.get(field)
        target_value = target_fields.get(field)
        both_known = source_value is not None and target_value is not None
        values.extend((
            float(both_known and source_value == target_value),
            float(both_known and source_value != target_value),
            float(source_value is None or target_value is None),
            float(source_value is None and source_status.get(field) == "declined"),
            float(target_value is None and target_status.get(field) == "declined"),
        ))
        values.extend(float(source_value == option) for option in SOFT_CATEGORIES[field])
        values.extend(float(target_value == option) for option in SOFT_CATEGORIES[field])
    if len(values) != FEATURE_COUNT:
        raise ValueError("directional feature schema mismatch")
    return values


def _sigmoid(logit):
    clipped = max(-8.0, min(8.0, float(logit)))
    return 1.0 / (1.0 + math.exp(-clipped))


def predict_direction(features, learning):
    weights = learning["weights"]
    return _sigmoid(sum(weight * value for weight, value in zip(weights, features)))


def model_is_ready(learning):
    count = int(learning.get("scored_labels", 0))
    if count <= 0:
        return False
    model_brier = float(learning.get("brier_sum", 0.0)) / count
    baseline_brier = float(learning.get("baseline_brier_sum", 0.0)) / count
    return (
        learning.get("labels", 0) >= MIN_LABELS
        and learning.get("positive_labels", 0) >= 5
        and learning.get("negative_labels", 0) >= 5
        and count >= MIN_LABELS
        and model_brier + 0.005 < baseline_brier
    )


def feedback_pair_score(left, right, learning):
    """Blend visible compatibility with the more cautious directional estimate."""
    if not model_is_ready(learning):
        return transparent_pair_score(left, right)
    model_brier = learning["brier_sum"] / learning["scored_labels"]
    baseline_brier = learning["baseline_brier_sum"] / learning["scored_labels"]
    confidence = min(1.0, max(0.0, (baseline_brier - model_brier) / 0.05))
    forward = 0.5 + confidence * (predict_direction(directional_features(left, right), learning) - 0.5)
    reverse = 0.5 + confidence * (predict_direction(directional_features(right, left), learning) - 0.5)
    return round(transparent_pair_score(left, right) + 2.0 * min(forward, reverse), 10)


def _action_key(day, left_id, right_id):
    return json.dumps([int(day), *sorted((str(left_id), str(right_id)))], separators=(",", ":"))


def record_actions(observation, pairs, memory):
    """Save both directional feature vectors before any response can be known."""
    learning = ensure_learning_state(memory)
    by_id = observation.members_by_id
    pending = learning["pending_actions"]
    for pair in pairs:
        left_id, right_id = sorted(pair)
        left, right = by_id[left_id], by_id[right_id]
        pending.append({
            "key": _action_key(observation.day, left_id, right_id),
            "day": observation.day,
            "left": left_id,
            "right": right_id,
            "left_to_right": directional_features(left, right),
            "right_to_left": directional_features(right, left),
        })
    if len(pending) > MAX_PENDING_ACTIONS:
        del pending[:-MAX_PENDING_ACTIONS]


def _event_fingerprint(event):
    stable = {
        key: event.get(key)
        for key in ("introduction_id", "member_id", "event", "value", "occurred_day", "observed_day", "missing_reason")
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _update_logistic_model(learning, features, label):
    weights = learning["weights"]
    probability = predict_direction(features, learning)
    baseline_probability = (learning["positive_labels"] + 1.0) / (learning["labels"] + 2.0)
    clipped_probability = max(1e-8, min(1.0 - 1e-8, probability))
    learning["brier_sum"] += (probability - label) ** 2
    learning["baseline_brier_sum"] += (baseline_probability - label) ** 2
    learning["log_loss_sum"] += -(
        label * math.log(clipped_probability)
        + (1.0 - label) * math.log(1.0 - clipped_probability)
    )
    learning["scored_labels"] += 1

    step = 0.12 / math.sqrt(1.0 + learning["labels"] / 20.0)
    error = probability - label
    for index, value in enumerate(features):
        regularization = 0.0 if index == 0 else 0.002 * weights[index]
        weights[index] = max(-3.0, min(3.0, weights[index] - step * (error * value + regularization)))
    learning["labels"] += 1
    learning["positive_labels"] += int(label == 1.0)
    learning["negative_labels"] += int(label == 0.0)
    return probability


def observe_feedback(state, memory):
    """Link new introductions and train only on released, explicit yes/no labels."""
    learning = ensure_learning_state(memory)
    day = int(state.get("day", 0))
    pending_by_key = {item["key"]: item for item in learning["pending_actions"]}
    intro_rows = learning["introductions"]
    consumed_keys = set()
    for intro in state.get("introductions") or ():
        intro_id = intro.get("introduction_id")
        assigned_day = intro.get("assigned_day")
        endpoints = (intro.get("user_a"), intro.get("user_b"))
        if intro_id is None or assigned_day is None or not all(isinstance(value, str) for value in endpoints):
            continue
        left_id, right_id = sorted(endpoints)
        action = pending_by_key.get(_action_key(assigned_day, left_id, right_id))
        if intro_id is not None and action is not None:
            intro_rows.setdefault(str(intro_id), {
                "left": left_id,
                "right": right_id,
                "left_to_right": action["left_to_right"],
                "right_to_left": action["right_to_left"],
                "observed_members": [],
            })
            consumed_keys.add(action["key"])
    learning["pending_actions"] = [
        item for item in learning["pending_actions"]
        if item["key"] not in consumed_keys and item["day"] >= day - 1
    ][-MAX_PENDING_ACTIONS:]

    seen = set(learning["seen_events"])
    for event in state.get("feedback") or ():
        if event.get("event") != "introduction_response" or event.get("value") not in ("yes", "no"):
            continue
        observed_day = event.get("observed_day")
        if not isinstance(observed_day, int) or observed_day > day:
            continue
        intro_id = str(event.get("introduction_id"))
        row = intro_rows.get(intro_id)
        if row is None:
            continue
        fingerprint = _event_fingerprint(event)
        if fingerprint in seen:
            continue
        member_id = event.get("member_id")
        if member_id == row["left"]:
            features = row["left_to_right"]
            direction = "left_to_right"
        elif member_id == row["right"]:
            features = row["right_to_left"]
            direction = "right_to_left"
        else:
            continue
        seen.add(fingerprint)
        label = 1.0 if event["value"] == "yes" else 0.0
        probability = _update_logistic_model(learning, features, label)
        directional_bucket = learning["direction_scores"][direction]
        directional_bucket["scored_labels"] += 1
        directional_bucket["brier_sum"] += (probability - label) ** 2
        row["observed_members"].append(member_id)
        if len(set(row["observed_members"])) >= 2:
            intro_rows.pop(intro_id, None)

    learning["seen_events"] = sorted(seen)[-MAX_SEEN_EVENTS:]
    if len(intro_rows) > MAX_LINKED_INTRODUCTIONS:
        oldest = sorted(intro_rows, key=lambda key: (intro_rows[key].get("left", ""), key))
        for intro_id in oldest[:len(intro_rows) - MAX_LINKED_INTRODUCTIONS]:
            intro_rows.pop(intro_id, None)
    learning["last_observation_day"] = day


def capture_match_action(observation, pairs, memory):
    record_actions(observation, pairs, memory)
    encoded_size = len(json.dumps(memory, allow_nan=False, separators=(",", ":")).encode())
    if encoded_size > 1024 * 1024:
        # Trim old diagnostic fingerprints and snapshots before rejecting a state.
        learning = ensure_learning_state(memory)
        learning["seen_events"] = learning["seen_events"][-512:]
        learning["introductions"] = dict(list(learning["introductions"].items())[-64:])
        learning["pending_actions"] = learning["pending_actions"][-64:]
        if len(json.dumps(memory, allow_nan=False, separators=(",", ":")).encode()) > 1024 * 1024:
            raise ValueError("directional feedback memory exceeds the official 1 MiB limit")
