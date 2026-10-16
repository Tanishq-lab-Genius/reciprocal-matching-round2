"""Run a short, reproducible demonstration of the submitted policy."""

from itertools import combinations

from kit import Simulator, eligibility, generate
from matching_core import transparent_pair_score
from reciprocal_matching_policy import decide


SEED = 15
POPULATION = 12


def label_map(state):
    return {
        member["member_id"]: f"P{index:02d}"
        for index, member in enumerate(state["members"], start=1)
    }


def pair_counts(state):
    available = [member for member in state["members"] if member["available"]]
    statuses = [eligibility(left, right)["status"] for left, right in combinations(available, 2)]
    return {
        "feasible": statuses.count("feasible"),
        "needs_clarification": statuses.count("needs_clarification"),
        "infeasible": statuses.count("infeasible"),
    }


def main():
    simulator = Simulator(generate(seed=SEED, n=POPULATION))
    initial_state = simulator.observe()
    labels = label_map(initial_state)

    print("SEQUENTIAL RECIPROCAL MATCHING — POLICY DEMO")
    print("Public synthetic sample • seed 15 • day 0 • policy: selective_joint_voi")
    print("This is a reproducible demonstration, not an official benchmark result.\n")
    print(f"Participants arrived today: {len(initial_state['members'])}")
    print(f"ASK budget remaining: {initial_state['ask_budget_remaining']} units")

    before = pair_counts(initial_state)
    print("\n1. Check pairs against mutual hard requirements")
    print(f"   Feasible now: {before['feasible']}")
    print(f"   Need clarification: {before['needs_clarification']}")
    print(f"   Infeasible: {before['infeasible']}")

    ask_result = decide({"phase": "ask", "state": initial_state, "memory": None})
    asks = ask_result["asks"]
    print("\n2. ASK decision")
    if asks:
        for ask in asks:
            cost = 3 if ask["field"] == "constraints" else 1
            print(f"   Ask {labels.get(ask['member_id'], 'participant')} for {ask['field']} (cost: {cost})")
        print("   The simulator supplies the answers; only the refreshed visible state goes to MATCH.")
        simulator.resolve_asks(asks)
    else:
        print("   No question had positive estimated value for the current allocation.")

    refreshed_state = simulator.observe()
    after = pair_counts(refreshed_state)
    print("\n3. Updated eligibility after answers")
    print(f"   Feasible now: {after['feasible']}")
    print(f"   Need clarification: {after['needs_clarification']}")
    print(f"   Infeasible: {after['infeasible']}")

    match_result = decide({
        "phase": "match",
        "state": refreshed_state,
        "memory": ask_result["memory"],
    })
    pairs = match_result["pairs"]
    print("\n4. MATCH decision")
    if pairs:
        members = {member["member_id"]: member for member in refreshed_state["members"]}
        for left_id, right_id in pairs:
            left, right = members[left_id], members[right_id]
            score = transparent_pair_score(left, right)
            print(
                f"   {labels.get(left_id, left_id)} ↔ {labels.get(right_id, right_id)}"
                f"  | mutual hard checks pass | transparent soft score: {score:.2f}"
            )
        print("   Each participant appears at most once in this day's introductions.")
    else:
        print("   No pair was introduced today; returning an empty match is allowed.")

    print("\nWhat this demonstrates: the submitted policy asks from observed information,")
    print("then matches only pairs that pass the reciprocal hard-constraint gate.")


if __name__ == "__main__":
    main()
