import copy
import json
import math
import unittest

from matching_core import (
    FEASIBLE,
    INFEASIBLE,
    UNRESOLVED,
    WeightedEdge,
    build_weighted_edges,
    enumerate_legal_questions,
    evaluate_pair,
    exact_component_matching,
    extract_score_features,
    fallback_component_matching,
    get_strategy,
    initialise_memory,
    parse_observation,
    rank_count_based_questions,
    safe_ask_batch,
    safe_match_batch,
    select_count_based_asks,
    select_global_matching,
    transparent_pair_score,
    validate_ask_batch,
    validate_match_batch,
)


HARD_DEFAULTS = {
    "age_min": 21,
    "age_max": 46,
    "who_to_meet": ["woman", "man", "non_binary"],
    "relationship_structure": "monogamous",
    "smoking": "no",
    "partner_smoking": "any",
    "has_children": False,
    "partner_children": "any",
    "wants_children": "unsure",
    "acceptable_zones": ["zone_a"],
    "schedule": ["weekend_day"],
}

SOFT_DEFAULTS = {
    "relationship_goal": "long_term",
    "relationship_pace": "steady",
    "lifestyle": "mixed",
    "conversations": "ideas",
    "emotional_availability": "ready",
    "space_for_relationship": "moderate",
    "relocate": "unsure",
}


def member(member_id, gender="woman", age=30, pool="pool", fields=None, statuses=None, available=True):
    values = {**HARD_DEFAULTS, **SOFT_DEFAULTS}
    if fields:
        values.update(fields)
    field_status = {key: ("observed" if value is not None else "not_asked") for key, value in values.items()}
    if statuses:
        field_status.update(statuses)
    return {
        "member_id": member_id,
        "pool_id": pool,
        "synthetic": True,
        "age": age,
        "gender": gender,
        "zone": "zone_a",
        "arrived_day": 0,
        "available": available,
        "fields": values,
        "field_status": field_status,
        "field_observed_day": {key: (0 if value is not None else None) for key, value in values.items()},
        "source": "synthetic_questionnaire",
    }


def state(*members, day=0, budget=12, introductions=None, ask_log=None):
    return {
        "schema_version": "1.0.0",
        "synthetic": True,
        "day": day,
        "ask_budget_remaining": budget,
        "members": list(members),
        "introductions": list(introductions or []),
        "feedback": [],
        "ask_log": list(ask_log or []),
    }


class ObservationAndFeasibilityTests(unittest.TestCase):
    def observation(self, *members, **kwargs):
        return parse_observation(state(*members, **kwargs))

    def test_parser_sorts_members_and_extracts_visible_state(self):
        parsed = self.observation(member("b"), member("a"), day=7, budget=5)
        self.assertEqual([item["member_id"] for item in parsed.members], ["a", "b"])
        self.assertEqual((parsed.day, parsed.ask_budget), (7, 5))

    def test_valid_reciprocal_pair(self):
        a, b = member("a"), member("b", gender="man")
        self.assertEqual(evaluate_pair(self.observation(a, b), a, b).status, FEASIBLE)

    def test_one_sided_hard_conflict(self):
        a = member("a", fields={"who_to_meet": ["woman"]})
        b = member("b", gender="man")
        result = evaluate_pair(self.observation(a, b), a, b)
        self.assertEqual(result.status, INFEASIBLE)
        self.assertIn("who_to_meet", result.reasons)

    def test_two_sided_hard_conflict(self):
        a = member("a", fields={"who_to_meet": ["woman"], "wants_children": "yes"})
        b = member("b", gender="man", fields={"who_to_meet": ["man"], "wants_children": "no"})
        result = evaluate_pair(self.observation(a, b), a, b)
        self.assertEqual(result.status, INFEASIBLE)
        self.assertTrue({"who_to_meet", "children_plans"}.issubset(result.reasons))

    def test_missing_required_field_is_unresolved(self):
        a, b = member("a", fields={"age_min": None}), member("b", gender="man")
        result = evaluate_pair(self.observation(a, b), a, b)
        self.assertEqual(result.status, UNRESOLVED)
        self.assertIn(("a", "age_min"), result.missing_requirements)

    def test_multiple_missing_fields_are_reported(self):
        a = member("a", fields={"age_min": None, "schedule": None})
        b = member("b", gender="man", fields={"partner_smoking": None})
        missing = evaluate_pair(self.observation(a, b), a, b).missing_requirements
        self.assertEqual(missing, (("a", "age_min"), ("a", "schedule"), ("b", "partner_smoking")))

    def test_known_conflict_dominates_missingness(self):
        a = member("a", fields={"age_min": None, "who_to_meet": ["woman"]})
        b = member("b", gender="man")
        self.assertEqual(evaluate_pair(self.observation(a, b), a, b).status, INFEASIBLE)

    def test_unavailable_member_is_infeasible(self):
        a, b = member("a", available=False), member("b", gender="man")
        self.assertIn("unavailable", evaluate_pair(self.observation(a, b), a, b).reasons)

    def test_wrong_pool_is_infeasible(self):
        a, b = member("a"), member("b", gender="man", pool="other")
        self.assertIn("different_pool", evaluate_pair(self.observation(a, b), a, b).reasons)

    def test_previously_introduced_pair_is_infeasible(self):
        a, b = member("a"), member("b", gender="man")
        intro = {"user_a": "a", "user_b": "b"}
        result = evaluate_pair(self.observation(a, b, introductions=[intro]), a, b)
        self.assertIn("repeated_pair", result.reasons)

    def test_each_pair_level_hard_constraint(self):
        cases = [
            ({"age_max": 25}, {}, "age"),
            ({"acceptable_zones": ["zone_b"]}, {}, "geography"),
            ({"partner_smoking": "no_smoking"}, {"smoking": "occasionally"}, "smoking"),
            ({"partner_children": "no_children"}, {"has_children": True}, "children_present"),
            ({"relationship_structure": "monogamous"}, {"relationship_structure": "non_monogamous"}, "relationship_structure"),
            ({"schedule": ["weekday_evening"]}, {"schedule": ["weekend_day"]}, "schedule"),
        ]
        for left_fields, right_fields, reason in cases:
            with self.subTest(reason=reason):
                a = member("a", age=30, fields=left_fields)
                b = member("b", gender="man", age=30, fields=right_fields)
                self.assertIn(reason, evaluate_pair(self.observation(a, b), a, b).reasons)


class ScoringAndAskTests(unittest.TestCase):
    def test_score_feature_extraction_is_transparent(self):
        a, b = member("a"), member("b", gender="man")
        features = extract_score_features(a, b)
        self.assertEqual(features["soft_matches"]["relationship_goal"], 1.0)
        self.assertEqual(features["schedule_overlap"], 1.0)

    def test_missing_soft_field_contributes_zero_not_match(self):
        a = member("a", fields={"relationship_goal": None})
        b = member("b", gender="man")
        self.assertEqual(extract_score_features(a, b)["soft_matches"]["relationship_goal"], 0.0)

    def test_observed_mismatch_is_worse_than_missing_for_outcome_signal(self):
        missing = member("a", fields={"relationship_goal": None})
        mismatch = member("b", fields={"relationship_goal": "exploring"})
        target = member("c", gender="man", fields={"relationship_goal": "long_term"})
        self.assertGreater(transparent_pair_score(missing, target), transparent_pair_score(mismatch, target))

    def test_outcome_signal_outranks_irrelevant_soft_agreement(self):
        target = member("target", gender="man")
        goal_match = member(
            "goal",
            fields={
                "emotional_availability": "taking_time",
                "space_for_relationship": "limited",
                "relocate": "yes",
            },
        )
        irrelevant_match = member("irrelevant", fields={"relationship_goal": "exploring"})
        self.assertGreater(transparent_pair_score(goal_match, target), transparent_pair_score(irrelevant_match, target))

    def test_score_is_finite_and_deterministic(self):
        a, b = member("a"), member("b", gender="man")
        first = transparent_pair_score(a, b)
        self.assertEqual(first, transparent_pair_score(copy.deepcopy(a), copy.deepcopy(b)))
        self.assertTrue(math.isfinite(first))

    def test_only_feasible_pairs_become_weighted_edges(self):
        a = member("a", fields={"age_min": None})
        b = member("b", gender="man")
        parsed = parse_observation(state(a, b))
        self.assertEqual(build_weighted_edges(parsed), ())

    def test_feasible_low_signal_pair_remains_an_edge(self):
        a = member("a", fields={field: None for field in SOFT_DEFAULTS})
        b = member("b", gender="man", fields={field: None for field in SOFT_DEFAULTS})
        edges = build_weighted_edges(parse_observation(state(a, b)))
        self.assertEqual(len(edges), 1)
        self.assertGreater(edges[0].weight, 0.0)

    def test_question_costs_and_budget_are_respected(self):
        members = [member(chr(97 + i), gender="man" if i % 2 else "woman", fields={"age_min": None}) for i in range(8)]
        parsed = parse_observation(state(*members, budget=5))
        asks = select_count_based_asks(parsed)
        self.assertLessEqual(validate_ask_batch(parsed, asks), 5)

    def test_duplicate_question_is_rejected(self):
        a, b = member("a", fields={"age_min": None}), member("b", gender="man")
        parsed = parse_observation(state(a, b))
        ask = {"member_id": "a", "field": "constraints"}
        with self.assertRaises(ValueError):
            validate_ask_batch(parsed, [ask, ask])

    def test_prior_or_pending_question_is_not_enumerated(self):
        a, b = member("a", fields={"age_min": None}), member("b", gender="man")
        log = [{"member_id": "a", "field": "constraints"}]
        parsed = parse_observation(state(a, b, ask_log=log))
        self.assertNotIn(("a", "constraints"), enumerate_legal_questions(parsed))

    def test_declined_field_is_not_reasked(self):
        a = member("a", fields={"age_min": None}, statuses={"age_min": "declined"})
        b = member("b", gender="man")
        self.assertNotIn(("a", "constraints"), enumerate_legal_questions(parse_observation(state(a, b))))

    def test_missing_information_does_not_create_match(self):
        a, b = member("a", fields={"age_min": None}), member("b", gender="man")
        parsed = parse_observation(state(a, b))
        self.assertTrue(any(item.member_id == "a" for item in rank_count_based_questions(parsed)))
        self.assertEqual(build_weighted_edges(parsed), ())

    def test_count_based_ranking_is_deterministic(self):
        members = [member("c", fields={"age_min": None}), member("b", gender="man"), member("a", fields={"age_min": None})]
        first = select_count_based_asks(parse_observation(state(*members)))
        second = select_count_based_asks(parse_observation(state(*reversed(members))))
        self.assertEqual(first, second)

    def test_soft_only_missingness_is_not_selected_by_feasibility_baseline(self):
        a = member("a", fields={"relationship_goal": None})
        b = member("b", gender="man")
        parsed = parse_observation(state(a, b))
        self.assertIn(("a", "relationship_goal"), enumerate_legal_questions(parsed))
        self.assertEqual(select_count_based_asks(parsed), [])

    def test_ask_action_schema_is_exact(self):
        a, b = member("a", fields={"age_min": None}), member("b", gender="man")
        asks = select_count_based_asks(parse_observation(state(a, b)))
        self.assertTrue(all(set(ask) == {"member_id", "field"} for ask in asks))

    def test_invalid_internal_asks_fail_closed(self):
        parsed = parse_observation(state(member("a")))
        self.assertEqual(safe_ask_batch(parsed, [{"member_id": "missing", "field": "constraints"}]), [])


class MatchingAndValidationTests(unittest.TestCase):
    def test_known_exact_optimum_beats_greedy_counterexample(self):
        edges = (
            WeightedEdge("a", "b", 6.0),
            WeightedEdge("c", "d", 6.0),
            WeightedEdge("a", "c", 10.0),
        )
        weight, pairs = exact_component_matching(("a", "b", "c", "d"), edges)
        self.assertEqual((weight, pairs), (12.0, (("a", "b"), ("c", "d"))))
        greedy_weight, _ = fallback_component_matching(edges)
        self.assertEqual(greedy_weight, 10.0)

    def test_equal_weight_matching_prefers_more_introductions(self):
        edges = (
            WeightedEdge("a", "b", 1.0),
            WeightedEdge("a", "c", 0.5),
            WeightedEdge("b", "d", 0.5),
        )
        weight, pairs = exact_component_matching(("a", "b", "c", "d"), edges)
        self.assertEqual(weight, 1.0)
        self.assertEqual(pairs, (("a", "c"), ("b", "d")))

    def test_general_graph_triangle(self):
        edges = (WeightedEdge("a", "b", 2), WeightedEdge("b", "c", 3), WeightedEdge("a", "c", 4))
        result = select_global_matching(edges)
        self.assertEqual(result.pairs, (("a", "c"),))

    def test_no_overlapping_selected_pairs(self):
        edges = tuple(WeightedEdge(a, b, value) for a, b, value in (("a", "b", 5), ("a", "c", 4), ("c", "d", 3)))
        pairs = select_global_matching(edges).pairs
        flat = [item for pair in pairs for item in pair]
        self.assertEqual(len(flat), len(set(flat)))

    def test_empty_graph(self):
        self.assertEqual(select_global_matching(()).pairs, ())

    def test_disconnected_graph_combines_components(self):
        edges = (WeightedEdge("a", "b", 2), WeightedEdge("c", "d", 3))
        result = select_global_matching(edges)
        self.assertEqual(result.pairs, (("a", "b"), ("c", "d")))
        self.assertEqual(result.exact_components, 2)

    def test_zero_and_negative_edges_are_not_selected(self):
        edges = (WeightedEdge("a", "b", 0), WeightedEdge("c", "d", -2))
        self.assertEqual(select_global_matching(edges).pairs, ())

    def test_large_component_uses_bounded_fallback(self):
        nodes = [f"n{i:02d}" for i in range(24)]
        edges = tuple(WeightedEdge(nodes[i], nodes[(i + 1) % len(nodes)], 1.0) for i in range(len(nodes)))
        result = select_global_matching(edges, exact_component_limit=10)
        self.assertEqual(result.fallback_components, 1)
        flat = [item for pair in result.pairs for item in pair]
        self.assertEqual(len(flat), len(set(flat)))

    def test_tie_breaking_is_deterministic(self):
        edges = (WeightedEdge("a", "b", 1), WeightedEdge("a", "c", 1), WeightedEdge("b", "d", 1), WeightedEdge("c", "d", 1))
        first = select_global_matching(edges).pairs
        second = select_global_matching(tuple(reversed(edges))).pairs
        self.assertEqual(first, second)

    def test_duplicate_member_in_batch_is_rejected(self):
        members = [member("a"), member("b", gender="man"), member("c")]
        parsed = parse_observation(state(*members))
        with self.assertRaises(ValueError):
            validate_match_batch(parsed, [["a", "b"], ["a", "c"]])

    def test_unresolved_pair_is_rejected_at_final_validation(self):
        a, b = member("a", fields={"age_min": None}), member("b", gender="man")
        parsed = parse_observation(state(a, b))
        with self.assertRaises(ValueError):
            validate_match_batch(parsed, [["a", "b"]])

    def test_invalid_proposal_uses_legal_greedy_fallback(self):
        a, b = member("a"), member("b", gender="man")
        parsed = parse_observation(state(a, b))
        edges = build_weighted_edges(parsed)
        self.assertEqual(safe_match_batch(parsed, [["a", "missing"]], edges), [["a", "b"]])

    def test_future_modes_fail_clearly(self):
        with self.assertRaises(NotImplementedError):
            get_strategy("joint_question_voi")

    def test_memory_is_json_serializable_and_bounded(self):
        memory = initialise_memory(None, "foundation")
        encoded = json.dumps(memory, allow_nan=False)
        self.assertLess(len(encoded.encode()), 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
