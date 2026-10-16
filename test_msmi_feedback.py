import copy
import unittest

from directional_learning import ensure_learning_state
from matching_core import parse_observation
from msmi_feedback import (
    ensure_msmi_state,
    expected_msmi_utility,
    observe_msmi_feedback,
)
from test_matching_core import member, state


class MSMIFeedbackTests(unittest.TestCase):
    def test_utility_is_finite_bounded_and_uses_directional_features_only_when_ready(self):
        left = member("left")
        right = member("right", gender="man")
        low_match = member("low", gender="man", fields={
            "relationship_goal": "exploring",
            "relationship_pace": "quick",
            "lifestyle": "social",
            "conversations": "playful",
        })
        memory = {}
        acceptance = ensure_learning_state(memory)
        outcomes = ensure_msmi_state(memory)

        score = expected_msmi_utility(left, right, acceptance, outcomes)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
        self.assertEqual(
            score,
            expected_msmi_utility(right, left, acceptance, outcomes),
        )
        self.assertGreater(
            score,
            expected_msmi_utility(left, low_match, acceptance, outcomes),
        )

    def test_only_released_mature_outcomes_update_funnel_rates(self):
        a = member("a")
        b = member("b", gender="man")
        intro = {"introduction_id": "intro-1", "user_a": "a", "user_b": "b", "assigned_day": 0}
        feedback = [
            {"introduction_id": "intro-1", "member_id": "a", "event": "introduction_response", "value": "yes", "occurred_day": 1, "observed_day": 1},
            {"introduction_id": "intro-1", "member_id": "b", "event": "introduction_response", "value": "yes", "occurred_day": 2, "observed_day": 2},
            {"introduction_id": "intro-1", "member_id": None, "event": "date_happened", "value": True, "occurred_day": 4, "observed_day": 9},
            {"introduction_id": "intro-1", "member_id": "a", "event": "second_meeting_intention", "value": "yes", "occurred_day": 5, "observed_day": 5},
            {"introduction_id": "intro-1", "member_id": "b", "event": "second_meeting_intention", "value": "yes", "occurred_day": 6, "observed_day": 6},
        ]
        memory = {}
        early = state(a, b, day=6, introductions=[intro])
        early["feedback"] = copy.deepcopy(feedback)
        observe_msmi_feedback(early, memory)
        rates = ensure_msmi_state(memory)
        self.assertEqual(rates["acceptance_response_events"], 2)
        self.assertEqual(rates["date_labels"], 0)
        self.assertEqual(rates["second_labels"], 0)

        released = state(a, b, day=9, introductions=[intro])
        released["feedback"] = copy.deepcopy(feedback)
        observe_msmi_feedback(released, memory)
        self.assertEqual(rates["acceptance_response_events"], 2)
        self.assertEqual(rates["acceptance_responses"], 2)
        self.assertEqual(rates["date_labels"], 1)
        self.assertEqual(rates["date_positive"], 1)
        self.assertEqual(rates["second_labels"], 2)
        self.assertEqual(rates["second_positive"], 2)

        observe_msmi_feedback(copy.deepcopy(released), memory)
        self.assertEqual(rates["acceptance_response_events"], 2)
        self.assertEqual(rates["date_labels"], 1)
        self.assertEqual(rates["second_labels"], 2)

    def test_late_date_cannot_contribute_second_meeting_success(self):
        a = member("a")
        b = member("b", gender="man")
        intro = {"introduction_id": "intro-late", "user_a": "a", "user_b": "b", "assigned_day": 0}
        feedback = [
            {"introduction_id": "intro-late", "member_id": None, "event": "date_happened", "value": True, "occurred_day": 31, "observed_day": 31},
            {"introduction_id": "intro-late", "member_id": "a", "event": "second_meeting_intention", "value": "yes", "occurred_day": 32, "observed_day": 32},
        ]
        memory = {}
        snapshot = state(a, b, day=32, introductions=[intro])
        snapshot["feedback"] = feedback
        observe_msmi_feedback(snapshot, memory)
        rates = ensure_msmi_state(memory)
        self.assertEqual(rates["date_labels"], 1)
        self.assertEqual(rates["date_positive"], 0)
        self.assertEqual(rates["second_labels"], 0)

    def test_null_no_response_is_not_a_directional_preference_label(self):
        a = member("a")
        b = member("b", gender="man")
        snapshot = state(a, b, day=7, introductions=[{
            "introduction_id": "intro-null", "user_a": "a", "user_b": "b", "assigned_day": 0,
        }])
        snapshot["feedback"] = [{
            "introduction_id": "intro-null", "member_id": "a", "event": "introduction_response",
            "value": None, "missing_reason": "no_response", "occurred_day": None, "observed_day": 7,
        }]
        memory = {}
        observe_msmi_feedback(snapshot, memory)
        observe_msmi_feedback(snapshot, memory)
        self.assertEqual(ensure_learning_state(memory)["labels"], 0)
        self.assertEqual(ensure_msmi_state(memory)["acceptance_response_events"], 1)


if __name__ == "__main__":
    unittest.main()
