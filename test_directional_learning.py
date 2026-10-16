import copy
import unittest

from directional_learning import (
    FEATURE_COUNT,
    _empty_state,
    directional_features,
    ensure_learning_state,
    feedback_pair_score,
    observe_feedback,
    predict_direction,
    record_actions,
)
from matching_core import build_match_action, get_strategy, parse_observation, transparent_pair_score
from test_matching_core import member, state


class DirectionalLearningTests(unittest.TestCase):
    def test_direction_features_distinguish_who_is_accepting_whom(self):
        a = member("a", age=28)
        b = member("b", gender="man", age=40)
        forward = directional_features(a, b)
        reverse = directional_features(b, a)
        self.assertEqual(len(forward), FEATURE_COUNT)
        self.assertNotEqual(forward[1], reverse[1])

    def test_learning_uses_action_time_snapshot_and_deduplicates_feedback(self):
        a = member("a")
        b = member("b", gender="man")
        observation = parse_observation(state(a, b, day=0))
        memory = {}
        record_actions(observation, [("a", "b")], memory)
        released = state(a, b, day=1, introductions=[{
            "introduction_id": "intro-1",
            "user_a": "a",
            "user_b": "b",
            "assigned_day": 0,
        }])
        released["feedback"] = [{
            "introduction_id": "intro-1",
            "member_id": "a",
            "event": "introduction_response",
            "value": "yes",
            "occurred_day": 1,
            "observed_day": 1,
        }]
        observe_feedback(released, memory)
        learning = ensure_learning_state(memory)
        self.assertEqual(learning["labels"], 1)
        observe_feedback(copy.deepcopy(released), memory)
        self.assertEqual(learning["labels"], 1)

    def test_directional_scores_are_reported_separately(self):
        a = member("a")
        b = member("b", gender="man")
        observation = parse_observation(state(a, b, day=0))
        memory = {}
        record_actions(observation, [("a", "b")], memory)
        released = state(a, b, day=1, introductions=[{
            "introduction_id": "intro-1", "user_a": "a", "user_b": "b", "assigned_day": 0,
        }])
        released["feedback"] = [
            {
                "introduction_id": "intro-1", "member_id": "a", "event": "introduction_response",
                "value": "yes", "occurred_day": 1, "observed_day": 1,
            },
            {
                "introduction_id": "intro-1", "member_id": "b", "event": "introduction_response",
                "value": "no", "occurred_day": 1, "observed_day": 1,
            },
        ]
        observe_feedback(released, memory)
        directions = ensure_learning_state(memory)["direction_scores"]
        self.assertEqual(directions["left_to_right"]["scored_labels"], 1)
        self.assertEqual(directions["right_to_left"]["scored_labels"], 1)
        self.assertEqual(set(directions), {"left_to_right", "right_to_left"})

    def test_missing_feedback_is_not_a_negative_label(self):
        a = member("a")
        b = member("b", gender="man")
        observation = parse_observation(state(a, b, day=0))
        memory = {}
        record_actions(observation, [("a", "b")], memory)
        released = state(a, b, day=1, introductions=[{
            "introduction_id": "intro-1", "user_a": "a", "user_b": "b", "assigned_day": 0,
        }])
        released["feedback"] = [{
            "introduction_id": "intro-1", "member_id": "a",
            "event": "introduction_response", "value": None,
            "occurred_day": 1, "observed_day": 1, "missing_reason": "no_response",
        }]
        observe_feedback(released, memory)
        self.assertEqual(ensure_learning_state(memory)["labels"], 0)

    def test_current_match_score_is_kept_until_model_has_enough_labels(self):
        a = member("a")
        b = member("b", gender="man")
        learning = _empty_state()
        self.assertEqual(feedback_pair_score(a, b, learning), transparent_pair_score(a, b))

    def test_feedback_strategy_preserves_reciprocal_hard_gate(self):
        a = member("a", fields={"who_to_meet": ["woman"]})
        b = member("b", gender="man")
        observation = parse_observation(state(a, b))
        self.assertEqual(build_match_action(observation, get_strategy("feedback_voi")), [])

    def test_learned_directional_score_is_finite_and_positive(self):
        a = member("a", age=28)
        b = member("b", gender="man", age=40)
        learning = _empty_state()
        learning["labels"] = 40
        learning["positive_labels"] = 6
        learning["negative_labels"] = 34
        learning["scored_labels"] = 40
        learning["brier_sum"] = 8.0
        learning["baseline_brier_sum"] = 10.0
        learning["weights"][1] = 1.0
        forward = predict_direction(directional_features(a, b), learning)
        reverse = predict_direction(directional_features(b, a), learning)
        score = feedback_pair_score(a, b, learning)
        self.assertNotEqual(forward, reverse)
        self.assertGreater(score, transparent_pair_score(a, b))


if __name__ == "__main__":
    unittest.main()
