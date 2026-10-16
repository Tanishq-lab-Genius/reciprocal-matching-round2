import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from kit import Simulator, generate
from reciprocal_matching_policy import decide
from test_matching_core import member, state


class ReciprocalMatchingPolicyIntegrationTests(unittest.TestCase):
    def test_empty_ask_and_match_requests(self):
        empty = state()
        ask = decide({"phase": "ask", "state": empty, "memory": None})
        match = decide({"phase": "match", "state": empty, "memory": ask["memory"]})
        self.assertEqual(ask["asks"], [])
        self.assertEqual(match["pairs"], [])

    def test_response_keys_match_official_contract(self):
        empty = state()
        self.assertEqual(set(decide({"phase": "ask", "state": empty, "memory": None})), {"asks", "memory"})
        self.assertEqual(set(decide({"phase": "match", "state": empty, "memory": None})), {"pairs", "memory"})

    def test_refreshed_match_state_is_used_after_ask(self):
        a = member("a", fields={"age_min": None})
        b = member("b", gender="man")
        ask = decide({"phase": "ask", "state": state(a, b), "memory": None})
        self.assertTrue(ask["asks"])
        refreshed = copy.deepcopy(a)
        refreshed["fields"]["age_min"] = 21
        refreshed["field_status"]["age_min"] = "observed"
        match = decide({"phase": "match", "state": state(refreshed, b), "memory": ask["memory"]})
        self.assertEqual(match["pairs"], [["a", "b"]])

    def test_no_hidden_or_future_top_level_dependency(self):
        a, b = member("a"), member("b", gender="man")
        request = {"phase": "match", "state": state(a, b), "memory": None}
        changed = copy.deepcopy(request)
        changed["hidden_world"] = {"future": True}
        changed["state"]["unsupported_hidden_key"] = "ignored"
        self.assertEqual(decide(request), decide(changed))

    def test_memory_round_trip(self):
        memory = {"external_safe_value": 3}
        result = decide({"phase": "ask", "state": state(), "memory": memory})
        encoded = json.dumps(result["memory"], allow_nan=False)
        self.assertEqual(json.loads(encoded)["external_safe_value"], 3)
        self.assertEqual(result["memory"]["foundation"]["strategy"], "selective_joint_voi")

    def test_default_strategy_matches_explicit_selective_joint_voi(self):
        a = member("a", fields={"age_min": None})
        b = member("b", gender="man")
        request = {"phase": "ask", "state": state(a, b), "memory": None}
        self.assertEqual(decide(request), decide(request, "selective_joint_voi"))

    def test_fallback_strategy_is_explicit(self):
        a, b = member("a"), member("b", gender="man")
        result = decide({"phase": "match", "state": state(a, b), "memory": None}, "foundation_fallback")
        self.assertEqual(result["pairs"], [["a", "b"]])

    def test_unknown_phase_rejected(self):
        with self.assertRaises(ValueError):
            decide({"phase": "wait", "state": state(), "memory": None})

    def test_real_process_emits_json_only(self):
        request = {"schema_version": "1.0.0", "phase": "match", "state": state(), "memory": None}
        completed = subprocess.run(
            [sys.executable, "reciprocal_matching_policy.py", "--baseline", "greedy"],
            input=json.dumps(request), text=True, capture_output=True, check=True,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(result["pairs"], [])
        self.assertEqual(completed.stderr, "")

    def test_sparse_official_observations_do_not_crash(self):
        sim = Simulator(generate(42, 20, "evaluation", "sparse"))
        memory = None
        for _ in range(3):
            ask = decide({"phase": "ask", "state": sim.observe(), "memory": memory})
            memory = ask["memory"]
            sim.resolve_asks(ask["asks"])
            match = decide({"phase": "match", "state": sim.observe(), "memory": memory})
            memory = match["memory"]
            sim.advance(match["pairs"])

    def test_feedback_model_is_opt_in_and_not_default(self):
        source = Path("reciprocal_matching_policy.py").read_text(encoding="utf-8")
        self.assertNotIn("phase3a_policy", source)
        self.assertIn('DEFAULT_STRATEGY = "selective_joint_voi"', source)
        self.assertIn('"feedback_voi"', Path("matching_core.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
