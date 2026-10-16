"""Active Sequential Reciprocal Matching Part 1 policy entry point for interface version 1.0.0."""

import argparse
import json
import sys

from matching_core import (
    build_ask_decision,
    build_match_action,
    get_strategy,
    initialise_memory,
    parse_observation,
)
from directional_learning import (
    capture_match_action,
    ensure_learning_state,
    feedback_pair_score,
    model_is_ready,
    observe_feedback,
)
from msmi_feedback import (
    ensure_msmi_state,
    expected_msmi_utility,
    msmi_model_diagnostics,
    observe_msmi_feedback,
)


DEFAULT_STRATEGY = "selective_joint_voi"


def _record_ask_diagnostics(memory, diagnostics):
    foundation = memory["foundation"]
    aggregate = foundation.setdefault(
        "ask_diagnostics",
        {"ask_calls": 0, "solver_calls": 0, "fallbacks": 0, "evaluated": 0, "scenarios": 0},
    )
    aggregate["ask_calls"] += 1
    aggregate["solver_calls"] += int(diagnostics.get("solver_calls", 0))
    aggregate["fallbacks"] += int(bool(diagnostics.get("fallback_used")))
    aggregate["evaluated"] += int(diagnostics.get("evaluated", 0))
    aggregate["scenarios"] += int(diagnostics.get("scenarios", 0))
    aggregate["last"] = diagnostics


def decide(request, strategy_name=DEFAULT_STRATEGY):
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    phase = request.get("phase")
    observation = parse_observation(request.get("state"))
    config = get_strategy(strategy_name)
    memory = initialise_memory(request.get("memory"), config.name)
    learning = None
    if config.scoring_mode in ("feedback", "msmi_feedback"):
        learning = ensure_learning_state(memory)
        observe_feedback(request.get("state") or {}, memory)
    msmi_learning = None
    if config.scoring_mode == "msmi_feedback":
        msmi_learning = ensure_msmi_state(memory)
        observe_msmi_feedback(request.get("state") or {}, memory)
        feedback_diagnostics = msmi_model_diagnostics(msmi_learning)
        feedback_diagnostics["directional_labels"] = int(learning.get("labels", 0))
        feedback_diagnostics["directional_model_ready"] = model_is_ready(learning)
        memory["foundation"]["msmi_feedback_diagnostics"] = feedback_diagnostics
    if phase == "ask":
        ask_scorer = None
        if config.scoring_mode == "msmi_feedback":
            ask_scorer = lambda left, right: expected_msmi_utility(
                left, right, learning, msmi_learning,
            )
        asks, diagnostics = build_ask_decision(observation, config, scorer=ask_scorer)
        _record_ask_diagnostics(memory, diagnostics)
        return {"asks": asks, "memory": memory}
    if phase == "match":
        scorer = None
        if config.scoring_mode == "feedback":
            scorer = lambda left, right: feedback_pair_score(left, right, learning)
            if model_is_ready(learning):
                learning["active_match_calls"] = int(learning.get("active_match_calls", 0)) + 1
        elif config.scoring_mode == "msmi_feedback":
            scorer = lambda left, right: expected_msmi_utility(
                left, right, learning, msmi_learning,
            )
            if model_is_ready(learning):
                learning["active_match_calls"] = int(learning.get("active_match_calls", 0)) + 1
        pairs = build_match_action(observation, config, scorer=scorer)
        if config.scoring_mode in ("feedback", "msmi_feedback"):
            capture_match_action(observation, pairs, memory)
        return {"pairs": pairs, "memory": memory}
    raise ValueError("phase must be ask or match")


def run_cli(default_strategy=DEFAULT_STRATEGY):
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default="greedy")
    parser.add_argument("--strategy", default=default_strategy)
    args = parser.parse_args()
    request = json.load(sys.stdin)
    json.dump(
        decide(request, strategy_name=args.strategy),
        sys.stdout,
        allow_nan=False,
        separators=(",", ":"),
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    run_cli()
