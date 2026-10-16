"""Sequential Reciprocal Matching Part 1 policy foundation for official interface version 1.0.0.

The module contains no simulator access. Every decision is derived only from
the observable state supplied to the policy process.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import copy
import itertools
import json
import math


FEASIBLE = "feasible"
INFEASIBLE = "infeasible"
UNRESOLVED = "unresolved"

HARD_FIELDS = (
    "age_min", "age_max", "who_to_meet", "relationship_structure",
    "smoking", "partner_smoking", "has_children", "partner_children",
    "wants_children", "acceptable_zones", "schedule",
)

SOFT_WEIGHTS = {
    "relationship_goal": 4.0,
    "relationship_pace": 2.0,
    "lifestyle": 1.0,
    "conversations": 1.0,
    "emotional_availability": 1.0,
    "space_for_relationship": 1.0,
    "relocate": 0.5,
}

# These fields carry outcome signal in the public evaluator.  They are kept
# separate from SOFT_WEIGHTS because every named soft field remains a legal
# clarification target under the interface, even when it is not useful for
# ranking introductions.
OUTCOME_SIGNAL_WEIGHTS = {
    "relationship_goal": 3.0,
    "relationship_pace": 2.0,
    "conversations": 1.25,
    "lifestyle": 0.5,
}
SECOND_MEETING_GOAL_BONUS = 1.5

QUESTION_COSTS = {"constraints": 3, **{field: 1 for field in SOFT_WEIGHTS}}
MEMORY_LIMIT = 1024 * 1024
DEFAULT_EXACT_COMPONENT_LIMIT = 18


@dataclass(frozen=True)
class ParsedObservation:
    day: int
    ask_budget: int
    members: tuple
    members_by_id: dict
    available_members: tuple
    past_pairs: frozenset
    ask_history: frozenset


@dataclass(frozen=True)
class FeasibilityResult:
    status: str
    reasons: tuple
    missing_requirements: tuple


@dataclass(frozen=True)
class WeightedEdge:
    left: str
    right: str
    weight: float

    def pair(self):
        return (self.left, self.right)


@dataclass(frozen=True)
class AskCandidate:
    member_id: str
    field: str
    cost: int
    resolving_pairs: int
    affected_pairs: int
    quality_sum: float

    def action(self):
        return {"member_id": self.member_id, "field": self.field}


@dataclass(frozen=True)
class MatchingResult:
    pairs: tuple
    total_weight: float
    exact_components: int
    fallback_components: int


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    ask_mode: str
    scoring_mode: str
    matching_mode: str
    exact_component_limit: int = DEFAULT_EXACT_COMPONENT_LIMIT
    max_candidates: int = 12
    shortlist_size: int = 3
    max_scenarios_per_question: int = 3
    max_solver_calls: int = 8
    ask_time_budget_seconds: float = 7.0


STRATEGIES = {
    "foundation": StrategyConfig("foundation", "count", "transparent", "global"),
    "count_based": StrategyConfig("count_based", "count", "transparent", "global"),
    "voi_only": StrategyConfig("voi_only", "voi_only", "transparent", "global"),
    "count_voi": StrategyConfig("count_voi", "count_voi", "transparent", "global"),
    "diversified_voi": StrategyConfig("diversified_voi", "diversified_voi", "transparent", "global"),
    "joint_budget_voi": StrategyConfig("joint_budget_voi", "joint_budget_voi", "transparent", "global"),
    # Organizer-feedback ablations. These retain the production matcher and
    # differ only in bounded ASK search/selection behavior.
    "single_only_voi": StrategyConfig("single_only_voi", "single_only_voi", "transparent", "global"),
    "joint_budget_no_redundancy": StrategyConfig(
        "joint_budget_no_redundancy", "joint_budget_no_redundancy", "transparent", "global",
    ),
    # A stricter joint VOI challenger: never spend question budget on a
    # count-based zero-value fallback.  A question batch must have positive
    # counterfactual allocation value under the same transparent matcher.
    "selective_joint_voi": StrategyConfig(
        "selective_joint_voi", "selective_joint_voi", "transparent", "global",
        shortlist_size=4, max_solver_calls=12,
    ),
    "feedback_voi": StrategyConfig("feedback_voi", "diversified_voi", "feedback", "global"),
    # Experimental end-to-end expected-MSMI scoring with scarcity-aware ASK.
    # The established default is intentionally unchanged.
    "msmi_feedback_voi": StrategyConfig(
        "msmi_feedback_voi", "hard_unlock_voi", "msmi_feedback", "global",
        max_candidates=16, shortlist_size=6, max_scenarios_per_question=3,
        max_solver_calls=40, ask_time_budget_seconds=7.0,
    ),
    "foundation_fallback": StrategyConfig("foundation_fallback", "count", "transparent", "fallback"),
    "no_asks_global": StrategyConfig("no_asks_global", "none", "transparent", "global"),
}

FUTURE_STRATEGIES = {
    "joint_question_voi", "feedback_adjusted", "optional_waiting",
}


def get_strategy(name):
    if name in FUTURE_STRATEGIES:
        raise NotImplementedError(f"Strategy mode is reserved for a later phase: {name}")
    if name not in STRATEGIES:
        raise ValueError(f"Unknown strategy mode: {name}")
    return STRATEGIES[name]


def parse_observation(state):
    """Parse and defensively validate the public observation only."""
    if not isinstance(state, dict):
        raise ValueError("state must be an object")
    day = state.get("day", 0)
    budget = state.get("ask_budget_remaining", 0)
    if not isinstance(day, int) or day < 0:
        raise ValueError("invalid observable day")
    if not isinstance(budget, int) or budget < 0:
        raise ValueError("invalid observable ask budget")
    raw_members = state.get("members") or []
    raw_introductions = state.get("introductions") or []
    if not isinstance(raw_members, list) or not isinstance(raw_introductions, list):
        raise ValueError("members and introductions must be arrays")
    members = tuple(sorted(raw_members, key=lambda member: member["member_id"]))
    members_by_id = {member["member_id"]: member for member in members}
    if len(members_by_id) != len(members):
        raise ValueError("duplicate observable member ID")
    available = tuple(member for member in members if member.get("available") is True)
    past_pairs = frozenset(
        tuple(sorted((intro["user_a"], intro["user_b"])))
        for intro in raw_introductions
    )
    ask_history = frozenset(
        (entry.get("member_id"), entry.get("field"))
        for entry in (state.get("ask_log") or [])
    )
    return ParsedObservation(day, budget, members, members_by_id, available, past_pairs, ask_history)


def initialise_memory(memory, strategy_name):
    value = copy.deepcopy(memory) if isinstance(memory, dict) else {}
    foundation = value.get("foundation")
    if not isinstance(foundation, dict) or foundation.get("version") != 1:
        foundation = {"version": 1}
        value["foundation"] = foundation
    foundation["strategy"] = strategy_name
    encoded = json.dumps(value, allow_nan=False, separators=(",", ":")).encode()
    if len(encoded) > MEMORY_LIMIT:
        raise ValueError("policy memory exceeds the official 1 MiB limit")
    return value


def evaluate_pair(observation, left, right):
    """Apply availability, history, and reciprocal hard constraints exactly."""
    reasons = []
    missing = []
    left_id = left.get("member_id")
    right_id = right.get("member_id")
    if left_id == right_id:
        return FeasibilityResult(INFEASIBLE, ("same_member",), ())
    if left.get("available") is not True or right.get("available") is not True:
        reasons.append("unavailable")
    if left.get("pool_id") != right.get("pool_id"):
        reasons.append("different_pool")
    if min(left.get("age", 0), right.get("age", 0)) < 18:
        reasons.append("underage")
    pair = tuple(sorted((left_id, right_id)))
    if pair in observation.past_pairs:
        reasons.append("repeated_pair")

    left_fields = left.get("fields") or {}
    right_fields = right.get("fields") or {}
    for member, fields in ((left, left_fields), (right, right_fields)):
        for field in HARD_FIELDS:
            if fields.get(field) is None:
                missing.append((member["member_id"], field))

    for source, target, source_fields, target_fields in (
        (left, right, left_fields, right_fields),
        (right, left, right_fields, left_fields),
    ):
        accepted_genders = source_fields.get("who_to_meet")
        if accepted_genders is not None and target.get("gender") not in accepted_genders:
            reasons.append("who_to_meet")
        age_min = source_fields.get("age_min")
        age_max = source_fields.get("age_max")
        if age_min is not None and target.get("age") < age_min:
            reasons.append("age")
        if age_max is not None and target.get("age") > age_max:
            reasons.append("age")
        accepted_zones = source_fields.get("acceptable_zones")
        if accepted_zones is not None and target.get("zone") not in accepted_zones:
            reasons.append("geography")
        if source_fields.get("partner_smoking") == "no_smoking" and target_fields.get("smoking") in ("yes", "occasionally"):
            reasons.append("smoking")
        if source_fields.get("partner_children") == "no_children" and target_fields.get("has_children") is True:
            reasons.append("children_present")

    structures = (left_fields.get("relationship_structure"), right_fields.get("relationship_structure"))
    if None not in structures and structures[0] != structures[1]:
        reasons.append("relationship_structure")
    if {left_fields.get("wants_children"), right_fields.get("wants_children")} == {"yes", "no"}:
        reasons.append("children_plans")
    schedules = (left_fields.get("schedule"), right_fields.get("schedule"))
    if None not in schedules and not set(schedules[0]).intersection(schedules[1]):
        reasons.append("schedule")

    if reasons:
        return FeasibilityResult(INFEASIBLE, tuple(sorted(set(reasons))), tuple(sorted(set(missing))))
    if missing:
        return FeasibilityResult(UNRESOLVED, (), tuple(sorted(set(missing))))
    return FeasibilityResult(FEASIBLE, (), ())


def extract_score_features(left, right):
    """Return transparent, finite pair features from observable values."""
    left_fields = left.get("fields") or {}
    right_fields = right.get("fields") or {}
    matches = {}
    agreements = {}
    for field in SOFT_WEIGHTS:
        a = left_fields.get(field)
        b = right_fields.get(field)
        matches[field] = 1.0 if a is not None and b is not None and a == b else 0.0
        if a is None or b is None:
            agreements[field] = 0.0
        else:
            agreements[field] = 1.0 if a == b else -0.5
    left_schedule = left_fields.get("schedule") or []
    right_schedule = right_fields.get("schedule") or []
    overlap = len(set(left_schedule).intersection(right_schedule))
    age_gap = abs(float(left.get("age", 0)) - float(right.get("age", 0)))
    return {
        "soft_matches": matches,
        "soft_agreements": agreements,
        "schedule_overlap": float(overlap),
        "age_closeness": max(0.0, 1.0 - age_gap / 25.0),
    }


def transparent_pair_score(left, right):
    """Positive downstream-outcome utility from observable reciprocal features."""
    features = extract_score_features(left, right)
    agreements = features["soft_agreements"]
    signal = sum(OUTCOME_SIGNAL_WEIGHTS[field] * agreements[field] for field in OUTCOME_SIGNAL_WEIGHTS)
    signal += SECOND_MEETING_GOAL_BONUS * agreements["relationship_goal"]
    scale = sum(OUTCOME_SIGNAL_WEIGHTS.values()) + SECOND_MEETING_GOAL_BONUS
    # A bounded positive utility makes the allocation comparable to a sum of
    # expected outcomes while retaining legally feasible alternatives even
    # when their observed agreement signal is weak.
    score = 1.0 / (1.0 + math.exp(-2.0 * signal / scale))
    if not math.isfinite(score):
        raise ValueError("non-finite transparent score")
    return round(score, 10)


def enumerate_pair_states(observation):
    for left, right in itertools.combinations(observation.available_members, 2):
        yield left, right, evaluate_pair(observation, left, right)


def build_weighted_edges(observation, scorer=transparent_pair_score):
    edges = []
    for left, right, result in enumerate_pair_states(observation):
        if result.status != FEASIBLE:
            continue
        weight = float(scorer(left, right))
        if math.isfinite(weight) and weight > 0.0:
            a, b = sorted((left["member_id"], right["member_id"]))
            edges.append(WeightedEdge(a, b, weight))
    return tuple(sorted(edges, key=lambda edge: (edge.left, edge.right)))


def _unasked_fields(member, fields):
    values = member.get("fields") or {}
    statuses = member.get("field_status") or {}
    return tuple(field for field in fields if values.get(field) is None and statuses.get(field) == "not_asked")


def enumerate_legal_questions(observation):
    """Enumerate useful official question shapes without selecting a batch."""
    questions = []
    for member in observation.available_members:
        member_id = member["member_id"]
        if _unasked_fields(member, HARD_FIELDS) and (member_id, "constraints") not in observation.ask_history:
            questions.append((member_id, "constraints"))
        for field in _unasked_fields(member, tuple(SOFT_WEIGHTS)):
            if (member_id, field) not in observation.ask_history:
                questions.append((member_id, field))
    return tuple(sorted(questions))


def rank_count_based_questions(observation):
    constraint_stats = {}
    for left, right, result in enumerate_pair_states(observation):
        if result.status == INFEASIBLE:
            continue
        quality = transparent_pair_score(left, right)
        if result.status == UNRESOLVED:
            for member_id in {item[0] for item in result.missing_requirements}:
                count, total = constraint_stats.get(member_id, (0, 0.0))
                constraint_stats[member_id] = (count + 1, total + quality)
    ranked = []
    for member_id, field in enumerate_legal_questions(observation):
        if field == "constraints":
            resolving, quality = constraint_stats.get(member_id, (0, 0.0))
            affected = resolving
        else:
            # Named soft questions are legal, but they cannot resolve a hard
            # eligibility blocker. Part 1 keeps them available for later VOI
            # modes and excludes them from the count-based feasibility baseline.
            continue
        if affected:
            ranked.append(AskCandidate(member_id, field, QUESTION_COSTS[field], resolving, affected, round(quality, 10)))
    return tuple(sorted(ranked, key=lambda item: (
        -item.resolving_pairs / item.cost,
        -item.affected_pairs / item.cost,
        -item.quality_sum / item.cost,
        item.member_id,
        item.field,
    )))


def select_count_based_asks(observation):
    remaining = observation.ask_budget
    selected = []
    seen = set()
    for candidate in rank_count_based_questions(observation):
        key = (candidate.member_id, candidate.field)
        if key in seen or candidate.cost > remaining:
            continue
        selected.append(candidate.action())
        seen.add(key)
        remaining -= candidate.cost
    return selected


def validate_ask_batch(observation, asks):
    if not isinstance(asks, list):
        raise ValueError("asks must be an array")
    spent = 0
    seen = set()
    available = {member["member_id"]: member for member in observation.available_members}
    for ask in asks:
        if not isinstance(ask, dict) or set(ask) != {"member_id", "field"}:
            raise ValueError("invalid ask shape")
        member_id, field = ask["member_id"], ask["field"]
        key = (member_id, field)
        if key in seen:
            raise ValueError("duplicate ask")
        if member_id not in available or field not in QUESTION_COSTS:
            raise ValueError("illegal ask target or field")
        if key in observation.ask_history:
            raise ValueError("already asked or pending question")
        member = available[member_id]
        if field == "constraints":
            if not _unasked_fields(member, HARD_FIELDS):
                raise ValueError("unnecessary constraints ask")
        elif field not in _unasked_fields(member, (field,)):
            raise ValueError("unnecessary soft-field ask")
        seen.add(key)
        spent += QUESTION_COSTS[field]
    if spent > observation.ask_budget:
        raise ValueError("ask budget exceeded")
    return spent


def safe_ask_batch(observation, proposed):
    try:
        validate_ask_batch(observation, proposed)
        return proposed
    except (KeyError, TypeError, ValueError):
        return []


def _edge_components(edges):
    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge.left, set()).add(edge.right)
        adjacency.setdefault(edge.right, set()).add(edge.left)
    remaining = set(adjacency)
    components = []
    while remaining:
        start = min(remaining)
        stack = [start]
        nodes = set()
        while stack:
            node = stack.pop()
            if node in nodes:
                continue
            nodes.add(node)
            stack.extend(sorted(adjacency.get(node, ()), reverse=True))
        remaining.difference_update(nodes)
        component_edges = tuple(edge for edge in edges if edge.left in nodes and edge.right in nodes)
        components.append((tuple(sorted(nodes)), component_edges))
    return tuple(components)


def _better_solution(candidate, incumbent):
    if candidate[0] > incumbent[0] + 1e-12:
        return True
    if abs(candidate[0] - incumbent[0]) <= 1e-12:
        if len(candidate[1]) != len(incumbent[1]):
            return len(candidate[1]) > len(incumbent[1])
        return candidate[1] < incumbent[1]
    return False


def exact_component_matching(nodes, edges):
    """Exact maximum-weight general-graph matching for a bounded component."""
    index = {node: position for position, node in enumerate(nodes)}
    by_pair = {(edge.left, edge.right): edge.weight for edge in edges if edge.weight > 0.0}
    neighbours = {node: [] for node in nodes}
    for left, right in by_pair:
        neighbours[left].append(right)
        neighbours[right].append(left)
    for node in neighbours:
        neighbours[node].sort()

    @lru_cache(maxsize=None)
    def solve(mask):
        if mask == 0:
            return (0.0, ())
        first_index = (mask & -mask).bit_length() - 1
        first = nodes[first_index]
        without_first = mask & ~(1 << first_index)
        best = solve(without_first)
        for other in neighbours[first]:
            other_index = index[other]
            if not mask & (1 << other_index):
                continue
            pair = tuple(sorted((first, other)))
            rest = solve(without_first & ~(1 << other_index))
            candidate = (round(rest[0] + by_pair[pair], 10), tuple(sorted(rest[1] + (pair,))))
            if _better_solution(candidate, best):
                best = candidate
        return best

    return solve((1 << len(nodes)) - 1)


def fallback_component_matching(edges):
    """Deterministic greedy matching with bounded one-edge local improvements."""
    ordered = tuple(sorted((edge for edge in edges if edge.weight > 0.0), key=lambda e: (-e.weight, e.left, e.right)))
    selected = []
    used = set()
    for edge in ordered:
        if edge.left not in used and edge.right not in used:
            selected.append(edge)
            used.update((edge.left, edge.right))
    for _ in range(2):
        changed = False
        for edge in ordered:
            if edge in selected:
                continue
            conflicts = [item for item in selected if {edge.left, edge.right}.intersection((item.left, item.right))]
            if edge.weight > sum(item.weight for item in conflicts) + 1e-12:
                selected = [item for item in selected if item not in conflicts]
                selected.append(edge)
                changed = True
        if not changed:
            break
    pairs = tuple(sorted(edge.pair() for edge in selected))
    return round(sum(edge.weight for edge in selected), 10), pairs


def select_global_matching(edges, exact_component_limit=DEFAULT_EXACT_COMPONENT_LIMIT, force_fallback=False):
    selected = []
    total = 0.0
    exact_count = 0
    fallback_count = 0
    for nodes, component_edges in _edge_components(edges):
        if not force_fallback and len(nodes) <= exact_component_limit:
            weight, pairs = exact_component_matching(nodes, component_edges)
            exact_count += 1
        else:
            weight, pairs = fallback_component_matching(component_edges)
            fallback_count += 1
        total += weight
        selected.extend(pairs)
    return MatchingResult(tuple(sorted(selected)), round(total, 10), exact_count, fallback_count)


def validate_match_batch(observation, pairs):
    if not isinstance(pairs, list):
        raise ValueError("pairs must be an array")
    used = set()
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2 or not all(isinstance(item, str) for item in pair):
            raise ValueError("invalid pair shape")
        left_id, right_id = pair
        if left_id in used or right_id in used:
            raise ValueError("overlapping matching batch")
        if left_id not in observation.members_by_id or right_id not in observation.members_by_id:
            raise ValueError("unknown member")
        result = evaluate_pair(observation, observation.members_by_id[left_id], observation.members_by_id[right_id])
        if result.status != FEASIBLE:
            raise ValueError("pair is not confirmed feasible")
        used.update((left_id, right_id))
    return True


def deterministic_greedy_pairs(edges):
    _, pairs = fallback_component_matching(edges)
    return [list(pair) for pair in pairs]


def safe_match_batch(observation, proposed, edges):
    try:
        validate_match_batch(observation, proposed)
        return proposed
    except (KeyError, TypeError, ValueError):
        fallback = deterministic_greedy_pairs(edges)
        try:
            validate_match_batch(observation, fallback)
            return fallback
        except (KeyError, TypeError, ValueError):
            return []


def build_ask_decision(observation, config, scorer=None):
    if config.ask_mode == "none":
        return [], {"strategy": config.name, "solver_calls": 0, "fallback_used": False}
    if config.ask_mode == "count":
        asks = safe_ask_batch(observation, select_count_based_asks(observation))
        return asks, {
            "strategy": config.name,
            "candidates_generated": len(rank_count_based_questions(observation)),
            "shortlisted": 0,
            "evaluated": 0,
            "scenarios": 0,
            "solver_calls": 0,
            "fallback_used": False,
            "selected": len(asks),
        }
    if config.ask_mode in (
        "voi_only", "count_voi", "diversified_voi", "joint_budget_voi",
        "single_only_voi", "joint_budget_no_redundancy", "selective_joint_voi", "hard_unlock_voi",
    ):
        from allocation_voi import select_voi_asks

        asks, diagnostics = select_voi_asks(observation, config, pair_scorer=scorer)
        return safe_ask_batch(observation, asks), diagnostics
    raise NotImplementedError(f"ASK mode is not implemented: {config.ask_mode}")


def build_ask_action(observation, config):
    return build_ask_decision(observation, config)[0]


def build_match_action(observation, config, scorer=None):
    if config.scoring_mode not in ("transparent", "feedback", "msmi_feedback"):
        raise NotImplementedError(f"Scoring mode is not implemented: {config.scoring_mode}")
    edges = build_weighted_edges(observation, scorer or transparent_pair_score)
    if config.matching_mode not in ("global", "fallback"):
        raise NotImplementedError(f"Matching mode is not implemented: {config.matching_mode}")
    matching = select_global_matching(
        edges,
        config.exact_component_limit,
        force_fallback=config.matching_mode == "fallback",
    )
    proposed = [list(pair) for pair in matching.pairs]
    return safe_match_batch(observation, proposed, edges)
