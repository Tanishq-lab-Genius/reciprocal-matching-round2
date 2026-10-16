"""Bounded allocation-aware clarification for Sequential Reciprocal Matching Part 2.

Counterfactuals are constructed only from the public observation and documented
schema values. They are never written back into the real MATCH observation.
"""

from __future__ import annotations

from dataclasses import dataclass
import copy
import itertools
import json
import time

from matching_core import (
    FEASIBLE,
    INFEASIBLE,
    UNRESOLVED,
    HARD_FIELDS,
    QUESTION_COSTS,
    SOFT_WEIGHTS,
    OUTCOME_SIGNAL_WEIGHTS,
    ParsedObservation,
    build_weighted_edges,
    enumerate_legal_questions,
    enumerate_pair_states,
    evaluate_pair,
    safe_ask_batch,
    select_count_based_asks,
    select_global_matching,
    transparent_pair_score,
)


SOFT_OPTIONS = {
    "relationship_goal": ("long_term", "exploring"),
    "relationship_pace": ("slow", "steady", "quick"),
    "lifestyle": ("quiet", "mixed", "social"),
    "conversations": ("ideas", "stories", "practical", "playful"),
    "emotional_availability": ("ready", "taking_time"),
    "space_for_relationship": ("limited", "moderate", "ample"),
    "relocate": ("yes", "no", "unsure"),
}

SCHEDULE_OPTIONS = ("weekday_evening", "weekend_day", "weekend_evening")
GENDER_OPTIONS = ("woman", "man", "non_binary")


@dataclass(frozen=True)
class QuestionMetadata:
    member_id: str
    field: str
    cost: int
    affected_pairs: tuple
    resolving_pairs: int
    final_missing_pairs: int
    high_score: float
    scarcity: float
    competition: float
    count_priority: float

    def key(self):
        return (self.member_id, self.field)

    def action(self):
        return {"member_id": self.member_id, "field": self.field}


@dataclass(frozen=True)
class HypotheticalAnswer:
    name: str
    values: dict
    statuses: dict
    weight: float


@dataclass(frozen=True)
class VOIEvaluation:
    candidate: QuestionMetadata
    expected_delta: float
    priority: float
    scenario_values: tuple
    solver_calls: int


@dataclass(frozen=True)
class JointVOIEvaluation:
    first: QuestionMetadata
    second: QuestionMetadata
    expected_delta: float
    priority: float
    scenario_value: float
    solver_calls: int


def _pair_key(left, right):
    return tuple(sorted((left["member_id"], right["member_id"])))


def _has_declined_hard_requirement(result, observation):
    for member_id, field in result.missing_requirements:
        member = observation.members_by_id[member_id]
        if (member.get("field_status") or {}).get(field) == "declined":
            return True
    return False


def build_question_metadata(observation, pair_scorer=None):
    legal = set(enumerate_legal_questions(observation))
    if not legal:
        return ()
    feasible_degree = {member_id: 0 for member_id, _ in legal}
    pair_rows = []
    for left, right, result in enumerate_pair_states(observation):
        score = (pair_scorer or transparent_pair_score)(left, right)
        pair = _pair_key(left, right)
        pair_rows.append((left, right, result, score, pair))
        if result.status == FEASIBLE:
            feasible_degree[left["member_id"]] = feasible_degree.get(left["member_id"], 0) + 1
            feasible_degree[right["member_id"]] = feasible_degree.get(right["member_id"], 0) + 1

    output = []
    for member_id, field in sorted(legal):
        if field != "constraints" and field not in OUTCOME_SIGNAL_WEIGHTS:
            continue
        affected = []
        resolving = 0
        final_missing = 0
        high_score = 0.0
        competition = 0.0
        for left, right, result, score, pair in pair_rows:
            if (
                member_id not in pair
                or result.status == INFEASIBLE
                or _has_declined_hard_requirement(result, observation)
            ):
                continue
            if field == "constraints":
                missing_members = {item[0] for item in result.missing_requirements}
                if member_id not in missing_members:
                    continue
                resolving += 1
                final_missing += int(missing_members == {member_id})
            else:
                other_id = pair[1] if pair[0] == member_id else pair[0]
                other_fields = observation.members_by_id[other_id].get("fields") or {}
                if other_fields.get(field) is None:
                    continue
            affected.append(pair)
            high_score = max(high_score, score)
            other = pair[1] if pair[0] == member_id else pair[0]
            competition = max(competition, float(feasible_degree.get(other, 0)))
        if not affected:
            continue
        cost = QUESTION_COSTS[field]
        count_value = resolving if field == "constraints" else len(affected) * 0.25
        output.append(
            QuestionMetadata(
                member_id=member_id,
                field=field,
                cost=cost,
                affected_pairs=tuple(sorted(set(affected))),
                resolving_pairs=resolving,
                final_missing_pairs=final_missing,
                high_score=round(high_score, 10),
                scarcity=1.0 / (1.0 + feasible_degree.get(member_id, 0)),
                competition=competition,
                count_priority=count_value / cost,
            )
        )
    return tuple(output)


def count_shortlist(candidates, cap):
    return tuple(sorted(candidates, key=lambda item: (
        -item.count_priority,
        -item.high_score,
        -item.final_missing_pairs,
        item.member_id,
        item.field,
    ))[:cap])


def voi_only_shortlist(candidates, cap):
    return tuple(sorted(candidates, key=lambda item: (
        -item.final_missing_pairs,
        -item.high_score,
        -item.scarcity,
        item.cost,
        item.member_id,
        item.field,
    ))[:cap])


def diversified_shortlist(candidates, cap):
    """Round-robin multiple impact views so low-count scarce questions survive."""
    if cap <= 0:
        return ()
    orderings = (
        sorted(candidates, key=lambda item: (-item.count_priority, -item.high_score, item.member_id, item.field)),
        sorted(candidates, key=lambda item: (-item.high_score, item.cost, item.member_id, item.field)),
        sorted(candidates, key=lambda item: (-item.scarcity, -item.high_score, item.member_id, item.field)),
        sorted(candidates, key=lambda item: (-item.final_missing_pairs, -item.high_score, item.member_id, item.field)),
        sorted(candidates, key=lambda item: (-item.competition, -item.high_score, item.member_id, item.field)),
    )
    selected = []
    seen = set()
    depth = 0
    while len(selected) < cap and any(depth < len(items) for items in orderings):
        for items in orderings:
            if depth >= len(items):
                continue
            candidate = items[depth]
            if candidate.key() not in seen:
                selected.append(candidate)
                seen.add(candidate.key())
                if len(selected) == cap:
                    break
        depth += 1
    return tuple(selected)


def _anchor_for(candidate, observation, pair_scorer=None):
    member = observation.members_by_id[candidate.member_id]
    partners = []
    for pair in candidate.affected_pairs:
        other_id = pair[1] if pair[0] == candidate.member_id else pair[0]
        other = observation.members_by_id[other_id]
        partners.append((-(pair_scorer or transparent_pair_score)(member, other), other_id, other))
    return min(partners)[2] if partners else None


def _compatible_constraint_values(member, anchor):
    statuses = member.get("field_status") or {}
    missing = [
        field for field in HARD_FIELDS
        if (member.get("fields") or {}).get(field) is None
        and statuses.get(field) == "not_asked"
    ]
    anchor_fields = anchor.get("fields") or {}
    values = {}
    for field in missing:
        if field == "age_min" or field == "age_max":
            values[field] = int(anchor["age"])
        elif field == "who_to_meet":
            values[field] = [anchor["gender"]]
        elif field == "relationship_structure":
            values[field] = anchor_fields.get(field) or "monogamous"
        elif field == "smoking":
            values[field] = "no"
        elif field == "partner_smoking":
            values[field] = "any"
        elif field == "has_children":
            values[field] = False
        elif field == "partner_children":
            values[field] = "any"
        elif field == "wants_children":
            values[field] = anchor_fields.get(field) if anchor_fields.get(field) in ("yes", "no") else "unsure"
        elif field == "acceptable_zones":
            values[field] = [anchor["zone"]]
        elif field == "schedule":
            values[field] = list(anchor_fields.get(field) or ("weekend_day",))
    return values


def _incompatible_constraint_values(member, anchor, compatible, observation):
    values = copy.deepcopy(compatible)
    missing = set(values)
    anchor_fields = anchor.get("fields") or {}
    if "who_to_meet" in missing:
        values["who_to_meet"] = [next(value for value in GENDER_OPTIONS if value != anchor["gender"])]
        return values
    if "acceptable_zones" in missing:
        alternatives = sorted({item.get("zone") for item in observation.members if item.get("zone") != anchor.get("zone")})
        values["acceptable_zones"] = [alternatives[0] if alternatives else "zone_other"]
        return values
    if "schedule" in missing:
        anchor_schedule = set(anchor_fields.get("schedule") or ())
        alternative = next((value for value in SCHEDULE_OPTIONS if value not in anchor_schedule), None)
        if alternative:
            values["schedule"] = [alternative]
            return values
    if "relationship_structure" in missing and anchor_fields.get("relationship_structure"):
        values["relationship_structure"] = "non_monogamous" if anchor_fields["relationship_structure"] == "monogamous" else "monogamous"
        return values
    if "wants_children" in missing and anchor_fields.get("wants_children") in ("yes", "no"):
        values["wants_children"] = "no" if anchor_fields["wants_children"] == "yes" else "yes"
        return values
    if "partner_smoking" in missing and anchor_fields.get("smoking") in ("yes", "occasionally"):
        values["partner_smoking"] = "no_smoking"
        return values
    if "smoking" in missing and anchor_fields.get("partner_smoking") == "no_smoking":
        values["smoking"] = "yes"
        return values
    if "partner_children" in missing and anchor_fields.get("has_children") is True:
        values["partner_children"] = "no_children"
        return values
    if "has_children" in missing and anchor_fields.get("partner_children") == "no_children":
        values["has_children"] = True
        return values
    if "age_min" in missing:
        proposed = min(65, int(anchor["age"]) + 1)
        known_max = (member.get("fields") or {}).get("age_max")
        if known_max is None or proposed <= known_max:
            values["age_min"] = proposed
            if "age_max" in missing:
                values["age_max"] = max(proposed, values["age_max"])
            return values
    if "age_max" in missing:
        proposed = max(18, int(anchor["age"]) - 1)
        known_min = (member.get("fields") or {}).get("age_min")
        if known_min is None or known_min <= proposed:
            values["age_max"] = proposed
            return values
    return {field: None for field in compatible}


def plausible_scenarios(candidate, observation, max_scenarios=3, pair_scorer=None):
    member = observation.members_by_id[candidate.member_id]
    if candidate.field == "constraints":
        anchor = _anchor_for(candidate, observation, pair_scorer)
        if anchor is None:
            return ()
        compatible = _compatible_constraint_values(member, anchor)
        if not compatible:
            return ()
        incompatible = _incompatible_constraint_values(member, anchor, compatible, observation)
        declined = {field: None for field in compatible}
        raw = (
            ("compatible_anchor", compatible, {field: "observed" for field in compatible}),
            ("incompatible_or_unresolved", incompatible, {field: ("observed" if value is not None else "declined") for field, value in incompatible.items()}),
            ("declined", declined, {field: "declined" for field in declined}),
        )
    else:
        observed = []
        for pair in candidate.affected_pairs:
            other_id = pair[1] if pair[0] == candidate.member_id else pair[0]
            value = (observation.members_by_id[other_id].get("fields") or {}).get(candidate.field)
            if value is not None:
                observed.append(value)
        counts = {value: observed.count(value) for value in set(observed)}
        ordered = sorted(SOFT_OPTIONS[candidate.field], key=lambda value: (-counts.get(value, 0), value))[:2]
        raw = tuple((f"observed_value_{index + 1}", {candidate.field: value}, {candidate.field: "observed"}) for index, value in enumerate(ordered))
        raw += (("declined", {candidate.field: None}, {candidate.field: "declined"}),)
    raw = raw[:max_scenarios]
    weight = 1.0 / len(raw) if raw else 0.0
    return tuple(HypotheticalAnswer(name, values, statuses, weight) for name, values, statuses in raw)


def hypothetical_observation(observation, candidate, scenario):
    members = []
    for original in observation.members:
        if original["member_id"] != candidate.member_id:
            members.append(original)
            continue
        member = copy.deepcopy(original)
        fields = member.setdefault("fields", {})
        statuses = member.setdefault("field_status", {})
        observed_days = member.setdefault("field_observed_day", {})
        for field, value in scenario.values.items():
            fields[field] = copy.deepcopy(value)
            statuses[field] = scenario.statuses[field]
            observed_days[field] = observation.day if value is not None else None
        members.append(member)
    ordered = tuple(sorted(members, key=lambda item: item["member_id"]))
    by_id = {member["member_id"]: member for member in ordered}
    available = tuple(member for member in ordered if member.get("available") is True)
    return ParsedObservation(
        observation.day,
        observation.ask_budget,
        ordered,
        by_id,
        available,
        observation.past_pairs,
        observation.ask_history,
    )


def allocation_value(observation, config, pair_scorer=None):
    # VOI performs many counterfactual re-solves inside one official request.
    # Keep exact dynamic programming to small components; larger components use
    # the existing deterministic bounded fallback.  The final MATCH phase keeps
    # its Part 1 solver configuration unchanged.
    edges = build_weighted_edges(observation, scorer=pair_scorer or transparent_pair_score)
    result = select_global_matching(
        edges,
        min(config.exact_component_limit, 12),
        force_fallback=config.matching_mode == "fallback",
    )
    return result.total_weight


def evaluate_question(candidate, observation, config, current_value, pair_scorer=None):
    scenarios = plausible_scenarios(
        candidate, observation, config.max_scenarios_per_question, pair_scorer
    )
    values = []
    solver_calls = 0
    for scenario in scenarios:
        if scenario.name == "declined":
            value = current_value
        else:
            hypothetical = hypothetical_observation(observation, candidate, scenario)
            value = allocation_value(hypothetical, config, pair_scorer)
            solver_calls += 1
        values.append((scenario.name, value, scenario.weight))
    expected_after = sum(value * weight for _, value, weight in values)
    expected_delta = max(0.0, expected_after - current_value)
    return VOIEvaluation(
        candidate,
        round(expected_delta, 10),
        round(expected_delta / candidate.cost, 10),
        tuple((name, round(value, 10), weight) for name, value, weight in values),
        solver_calls,
    )


def complementary_candidate_pairs(candidates, observation):
    """Return bounded two-question bundles that can jointly resolve one edge."""
    pairs = []
    for first, second in itertools.combinations(candidates, 2):
        if first.field != "constraints" or second.field != "constraints":
            continue
        if first.member_id == second.member_id:
            continue
        shared_edges = set(first.affected_pairs).intersection(second.affected_pairs)
        complementary = False
        for left_id, right_id in shared_edges:
            if {left_id, right_id} != {first.member_id, second.member_id}:
                continue
            result = evaluate_pair(
                observation,
                observation.members_by_id[left_id],
                observation.members_by_id[right_id],
            )
            missing_members = {member_id for member_id, _ in result.missing_requirements}
            if result.status == UNRESOLVED and {first.member_id, second.member_id}.issubset(missing_members):
                complementary = True
                break
        if complementary:
            pairs.append((first, second))
    return tuple(sorted(pairs, key=lambda item: (
        -max(item[0].high_score, item[1].high_score),
        -(item[0].count_priority + item[1].count_priority),
        item[0].member_id,
        item[1].member_id,
    )))


def evaluate_joint_question_pair(
    first, second, observation, config, current_value, single_evaluations, pair_scorer=None,
):
    """Estimate complementary value with one favorable-favorable re-solve."""
    first_scenarios = plausible_scenarios(
        first, observation, config.max_scenarios_per_question, pair_scorer
    )
    first_favorable = next((item for item in first_scenarios if item.name == "compatible_anchor"), None)
    if first_favorable is None:
        return JointVOIEvaluation(first, second, 0.0, 0.0, current_value, 0)
    after_first = hypothetical_observation(observation, first, first_favorable)
    second_scenarios = plausible_scenarios(
        second, after_first, config.max_scenarios_per_question, pair_scorer
    )
    second_favorable = next((item for item in second_scenarios if item.name == "compatible_anchor"), None)
    if second_favorable is None:
        return JointVOIEvaluation(first, second, 0.0, 0.0, current_value, 0)
    after_both = hypothetical_observation(after_first, second, second_favorable)
    joint_value = allocation_value(after_both, config, pair_scorer)
    weighted_gain = max(
        0.0,
        (joint_value - current_value) * first_favorable.weight * second_favorable.weight,
    )
    single_credit = (
        single_evaluations[first.key()].expected_delta
        + single_evaluations[second.key()].expected_delta
    )
    complementary_gain = max(0.0, weighted_gain - single_credit)
    combined_cost = first.cost + second.cost
    return JointVOIEvaluation(
        first,
        second,
        round(complementary_gain, 10),
        round(complementary_gain / combined_cost, 10),
        round(joint_value, 10),
        1,
    )


def select_cost_aware(evaluations, budget, mode, joint_evaluations=()):
    ordered = sorted(evaluations, key=lambda item: (
        -item.priority,
        -item.expected_delta,
        -item.candidate.count_priority,
        -item.candidate.final_missing_pairs,
        item.candidate.member_id,
        item.candidate.field,
    ))
    selected = []
    selected_keys = set()
    covered = set()
    remaining = budget

    def add_single(item, allow_zero):
        nonlocal remaining
        candidate = item.candidate
        if candidate.key() in selected_keys:
            return
        if candidate.cost > remaining:
            return
        affected = set(candidate.affected_pairs)
        overlap = len(affected.intersection(covered)) / max(1, len(affected))
        marginal = item.priority * (1.0 - overlap)
        if item.expected_delta <= 0.0:
            if not allow_zero or candidate.field != "constraints":
                return
            marginal = 0.001 * candidate.count_priority * (1.0 - overlap)
        if marginal <= 0.0:
            return
        selected.append(candidate.action())
        selected_keys.add(candidate.key())
        covered.update(affected)
        remaining -= candidate.cost

    for item in ordered:
        if item.expected_delta > 0.0:
            add_single(item, allow_zero=False)

    for joint in sorted(joint_evaluations, key=lambda item: (
        -item.priority,
        -item.expected_delta,
        item.first.member_id,
        item.second.member_id,
    )):
        if joint.expected_delta <= 0.0:
            continue
        missing = tuple(
            candidate for candidate in (joint.first, joint.second)
            if candidate.key() not in selected_keys
        )
        required = sum(candidate.cost for candidate in missing)
        if not missing or required > remaining:
            continue
        for candidate in missing:
            selected.append(candidate.action())
            selected_keys.add(candidate.key())
            covered.update(candidate.affected_pairs)
            remaining -= candidate.cost

    if mode != "voi_only":
        for item in ordered:
            if item.expected_delta <= 0.0:
                add_single(item, allow_zero=True)
    return selected


def select_joint_budget_aware(
    evaluations,
    budget,
    joint_evaluations=(),
    apply_redundancy_penalty=True,
    include_zero_voi_hard_fallback=True,
):
    """Select one legal question set after singles and joint gains compete together.

    The shortlist is deliberately small, so every affordable subset can be
    compared without additional allocation solves. Single-question gains are
    shared across overlapping affected edges. A joint gain is added only when
    both questions are present; the comparator has already removed their
    individual credit. Overlapping joint gains share their edge credit as well.
    """
    ordered = sorted(evaluations, key=lambda item: (
        -item.priority,
        -item.expected_delta,
        -item.candidate.count_priority,
        -item.candidate.final_missing_pairs,
        item.candidate.member_id,
        item.candidate.field,
    ))
    unique = []
    seen = set()
    for item in ordered:
        if item.candidate.key() not in seen:
            unique.append(item)
            seen.add(item.candidate.key())
    ordered = tuple(unique)

    positive_joints = tuple(
        item for item in joint_evaluations
        if item.expected_delta > 0.0 and item.first.key() != item.second.key()
    )

    def adjusted_value(selected_items):
        edge_counts = {}
        for item in selected_items:
            for edge in set(item.candidate.affected_pairs):
                edge_counts[edge] = edge_counts.get(edge, 0) + 1

        value = 0.0
        for item in selected_items:
            base = item.expected_delta
            if base <= 0.0 and item.candidate.field == "constraints":
                if not include_zero_voi_hard_fallback:
                    continue
                base = 0.001 * item.candidate.count_priority
            if base <= 0.0:
                continue
            affected = set(item.candidate.affected_pairs)
            novelty = (
                sum(1.0 / edge_counts[edge] for edge in affected) / len(affected)
                if affected and apply_redundancy_penalty else 1.0
            )
            value += base * novelty

        keys = {item.candidate.key() for item in selected_items}
        active_joints = tuple(
            item for item in positive_joints
            if item.first.key() in keys and item.second.key() in keys
        )
        joint_edge_counts = {}
        joint_edges = []
        for item in active_joints:
            affected = set(item.first.affected_pairs).union(item.second.affected_pairs)
            joint_edges.append(affected)
            for edge in affected:
                joint_edge_counts[edge] = joint_edge_counts.get(edge, 0) + 1
        for item, affected in zip(active_joints, joint_edges):
            novelty = (
                sum(1.0 / joint_edge_counts[edge] for edge in affected) / len(affected)
                if affected and apply_redundancy_penalty else 1.0
            )
            value += item.expected_delta * novelty
        return round(value, 12)

    best_items = ()
    best_value = 0.0
    best_cost = 0
    best_signature = ()
    for size in range(1, len(ordered) + 1):
        for selected_items in itertools.combinations(ordered, size):
            cost = sum(item.candidate.cost for item in selected_items)
            if cost > budget:
                continue
            value = adjusted_value(selected_items)
            signature = tuple(item.candidate.key() for item in selected_items)
            better = value > best_value
            tied = abs(value - best_value) <= 1e-12
            if tied and value > 0.0:
                better = (cost, len(signature), signature) < (
                    best_cost, len(best_signature), best_signature,
                )
            if better:
                best_items = selected_items
                best_value = value
                best_cost = cost
                best_signature = signature
    return [item.candidate.action() for item in best_items]


def classify_hard_unlock_members(observation):
    """Classify available people using observable feasible/actionable edges.

    An unresolved edge is actionable only when every missing hard field is
    currently askable through the official constraints bundle at the relevant
    endpoint. Pending or declined information is not treated as an ASK
    opportunity.
    """
    legal = set(enumerate_legal_questions(observation))
    ids = {member["member_id"] for member in observation.available_members}
    feasible_degree = {member_id: 0 for member_id in ids}
    potential_by_member = {member_id: set() for member_id in ids}
    actionable_by_member = {member_id: set() for member_id in ids}
    actionable_edges = set()

    for left, right, result in enumerate_pair_states(observation):
        pair = _pair_key(left, right)
        if result.status == FEASIBLE:
            feasible_degree[left["member_id"]] += 1
            feasible_degree[right["member_id"]] += 1
            continue
        if result.status != UNRESOLVED or not result.missing_requirements:
            continue
        if _has_declined_hard_requirement(result, observation):
            continue
        missing_members = {member_id for member_id, _ in result.missing_requirements}
        if any(
            (observation.members_by_id[member_id].get("field_status") or {}).get(field) != "not_asked"
            for member_id, field in result.missing_requirements
        ):
            continue
        if any((member_id, "constraints") not in legal for member_id in missing_members):
            continue
        actionable_edges.add(pair)
        for member_id in pair:
            potential_by_member[member_id].add(pair)
        for member_id in missing_members:
            actionable_by_member[member_id].add(pair)

    alternatives = {
        member_id: feasible_degree[member_id] + len(potential_by_member[member_id])
        for member_id in ids
    }
    classes = {}
    for member_id in ids:
        if feasible_degree[member_id] > 0:
            classes[member_id] = "A"
        elif potential_by_member[member_id]:
            classes[member_id] = "B"
        else:
            classes[member_id] = "C"
    return {
        "classes": classes,
        "feasible_degree": feasible_degree,
        "potential_by_member": potential_by_member,
        "actionable_by_member": actionable_by_member,
        "actionable_edges": actionable_edges,
        "alternatives": alternatives,
    }


def _hard_unlock_question_candidates(observation, profile, ask_scorer):
    legal = set(enumerate_legal_questions(observation))
    candidates = []
    hard_edges = profile["actionable_by_member"]
    for member_id, field in sorted(legal):
        if field != "constraints":
            continue
        affected = tuple(sorted(hard_edges.get(member_id, ())))
        if not affected:
            continue
        scores = []
        competition = 0.0
        final_missing = 0
        for pair in affected:
            other_id = pair[1] if pair[0] == member_id else pair[0]
            member = observation.members_by_id[member_id]
            other = observation.members_by_id[other_id]
            scores.append(float(ask_scorer(member, other)))
            competition = max(competition, float(profile["alternatives"].get(other_id, 0)))
            result = evaluate_pair(observation, member, other)
            missing_members = {item[0] for item in result.missing_requirements}
            final_missing += int(missing_members == {member_id})
        cost = QUESTION_COSTS[field]
        candidates.append(QuestionMetadata(
            member_id=member_id,
            field=field,
            cost=cost,
            affected_pairs=affected,
            resolving_pairs=len(affected),
            final_missing_pairs=final_missing,
            high_score=max(scores, default=0.0),
            scarcity=1.0 / (1.0 + profile["feasible_degree"].get(member_id, 0)),
            competition=competition,
            count_priority=len(affected) / cost,
        ))

    # A soft question is considered only when its answer can reorder at least
    # two presently feasible partner options with different disclosed values.
    soft_options = {}
    for left, right, result in enumerate_pair_states(observation):
        if result.status != FEASIBLE:
            continue
        for member, partner in ((left, right), (right, left)):
            member_id = member["member_id"]
            partner_fields = partner.get("fields") or {}
            for field in OUTCOME_SIGNAL_WEIGHTS:
                if (member_id, field) not in legal:
                    continue
                value = partner_fields.get(field)
                if value is None:
                    continue
                key = (member_id, field)
                soft_options.setdefault(key, []).append((
                    _pair_key(left, right), value, ask_scorer(member, partner), partner["member_id"],
                ))

    for (member_id, field), rows in sorted(soft_options.items()):
        if len({row[3] for row in rows}) < 2 or len({row[1] for row in rows}) < 2:
            continue
        pairs = tuple(sorted({row[0] for row in rows}))
        cost = QUESTION_COSTS[field]
        candidates.append(QuestionMetadata(
            member_id=member_id,
            field=field,
            cost=cost,
            affected_pairs=pairs,
            resolving_pairs=0,
            final_missing_pairs=0,
            high_score=max(float(row[2]) for row in rows),
            scarcity=1.0 / (1.0 + profile["feasible_degree"].get(member_id, 0)),
            competition=max(float(profile["alternatives"].get(row[3], 0)) for row in rows),
            count_priority=len(pairs) * 0.25 / cost,
        ))
    hard = tuple(item for item in candidates if item.field == "constraints")
    soft = tuple(item for item in candidates if item.field != "constraints")
    return hard, soft


def _hard_unlock_fallback(observation, candidates):
    """Legal, actionable hard-only fallback; never fall back to blind counts."""
    remaining = observation.ask_budget
    selected = []
    for candidate in sorted(candidates, key=lambda item: (
        -item.scarcity,
        -item.high_score,
        -item.count_priority,
        item.member_id,
    )):
        if candidate.cost > remaining:
            continue
        selected.append(candidate.action())
        remaining -= candidate.cost
    return safe_ask_batch(observation, selected)


def select_hard_unlock_asks(observation, config, pair_scorer=None):
    """Run scarcity-aware hard-unlock VOI, then selective feasible-edge soft VOI."""
    started = time.perf_counter()
    profile = classify_hard_unlock_members(observation)
    alternative_counts = profile["alternatives"]
    base_scorer = pair_scorer or transparent_pair_score
    score_cache = {}
    signature_cache = {}

    def ask_scorer(left, right):
        def signature(member):
            identity = id(member)
            cached = signature_cache.get(identity)
            if cached is not None and cached[0] is member:
                return cached[1]
            value = json.dumps((
                member.get("member_id"), member.get("age"), member.get("gender"),
                member.get("zone"), member.get("fields") or {},
                member.get("field_status") or {},
            ), sort_keys=True, separators=(",", ":"))
            signature_cache[identity] = (member, value)
            return value

        cache_key = tuple(sorted((signature(left), signature(right))))
        if cache_key in score_cache:
            return score_cache[cache_key]
        score = float(base_scorer(left, right))
        scarce_alternatives = min(
            alternative_counts.get(left["member_id"], 0),
            alternative_counts.get(right["member_id"], 0),
        )
        bonus = min(0.25, 0.25 / max(1, scarce_alternatives))
        result = score * (1.0 + bonus)
        if len(score_cache) < 30000:
            score_cache[cache_key] = result
        return result

    hard_candidates, soft_candidates = _hard_unlock_question_candidates(
        observation, profile, ask_scorer,
    )
    hard_shortlist = diversified_shortlist(
        hard_candidates, min(config.max_candidates, config.shortlist_size),
    )
    soft_shortlist = diversified_shortlist(
        soft_candidates, min(config.max_candidates, 6),
    )
    diagnostics = {
        "strategy": config.name,
        "layer": "hard_unlock_voi",
        "class_counts": {
            label: sum(value == label for value in profile["classes"].values())
            for label in ("A", "B", "C")
        },
        "actionable_hard_edges": len(profile["actionable_edges"]),
        "hard_candidates_generated": len(hard_candidates),
        "soft_candidates_generated": len(soft_candidates),
        "shortlisted": len(hard_shortlist) + len(soft_shortlist),
        "evaluated": 0,
        "scenarios": 0,
        "solver_calls": 0,
        "joint_candidates": 0,
        "joint_evaluated": 0,
        "joint_selected": 0,
        "fallback_used": False,
        "scarcity_bonus_cap": 0.25,
        "scoring_note": "ASK-only scarcity-adjusted factorised MSMI estimate; uncalibrated",
    }

    def finish(asks, **updates):
        diagnostics.update(updates)
        diagnostics["selected"] = len(asks)
        return safe_ask_batch(observation, asks), diagnostics

    if not hard_shortlist and not soft_shortlist:
        return finish([])

    solver_calls = 0
    hard_evaluations = []
    hard_joints = []
    scenario_count = 0
    try:
        current_value = allocation_value(observation, config, ask_scorer)
        solver_calls += 1
        if time.perf_counter() - started > config.ask_time_budget_seconds:
            fallback = _hard_unlock_fallback(observation, hard_shortlist)
            return finish(
                fallback, solver_calls=solver_calls, fallback_used=True,
                fallback_reason="time_cap_before_voi",
            )

        for candidate in hard_shortlist:
            if time.perf_counter() - started > config.ask_time_budget_seconds:
                diagnostics["fallback_reason"] = "time_cap_during_hard_single_search"
                break
            scenarios = plausible_scenarios(
                candidate, observation, config.max_scenarios_per_question, ask_scorer,
            )
            required_calls = sum(item.name != "declined" for item in scenarios)
            if solver_calls + required_calls > config.max_solver_calls:
                diagnostics["fallback_reason"] = "solver_cap_during_hard_single_search"
                break
            evaluation = evaluate_question(
                candidate, observation, config, current_value, ask_scorer,
            )
            hard_evaluations.append(evaluation)
            solver_calls += evaluation.solver_calls
            scenario_count += len(scenarios)

        if hard_evaluations:
            joint_candidates = complementary_candidate_pairs(
                tuple(item.candidate for item in hard_evaluations), observation,
            )
            diagnostics["joint_candidates"] = len(joint_candidates)
            singles_by_key = {item.candidate.key(): item for item in hard_evaluations}
            for first, second in joint_candidates:
                if time.perf_counter() - started > config.ask_time_budget_seconds:
                    diagnostics["fallback_reason"] = "time_cap_during_joint_search"
                    break
                if solver_calls + 1 > config.max_solver_calls:
                    diagnostics["fallback_reason"] = "solver_cap_during_joint_search"
                    break
                joint = evaluate_joint_question_pair(
                    first, second, observation, config, current_value,
                    singles_by_key, ask_scorer,
                )
                hard_joints.append(joint)
                solver_calls += joint.solver_calls

        hard_asks = select_joint_budget_aware(
            hard_evaluations,
            observation.ask_budget,
            hard_joints,
            include_zero_voi_hard_fallback=False,
        )
        spent = sum(QUESTION_COSTS[item["field"]] for item in hard_asks)
        remaining = max(0, observation.ask_budget - spent)
        soft_evaluations = []
        if remaining and not diagnostics.get("fallback_reason"):
            for candidate in soft_shortlist:
                if time.perf_counter() - started > config.ask_time_budget_seconds:
                    diagnostics["fallback_reason"] = "time_cap_during_soft_search"
                    break
                scenarios = plausible_scenarios(
                    candidate, observation, config.max_scenarios_per_question, ask_scorer,
                )
                required_calls = sum(item.name != "declined" for item in scenarios)
                if solver_calls + required_calls > config.max_solver_calls:
                    diagnostics["fallback_reason"] = "solver_cap_during_soft_search"
                    break
                evaluation = evaluate_question(
                    candidate, observation, config, current_value, ask_scorer,
                )
                soft_evaluations.append(evaluation)
                solver_calls += evaluation.solver_calls
                scenario_count += len(scenarios)
        soft_asks = select_joint_budget_aware(
            soft_evaluations,
            remaining,
            (),
            include_zero_voi_hard_fallback=False,
        )
        asks = hard_asks + soft_asks
        selected_keys = {(item["member_id"], item["field"]) for item in hard_asks}
        diagnostics["joint_selected"] = sum(
            item.first.key() in selected_keys and item.second.key() in selected_keys
            for item in hard_joints if item.expected_delta > 0.0
        )
        diagnostics["evaluated"] = len(hard_evaluations) + len(soft_evaluations)
        diagnostics["scenarios"] = scenario_count
        diagnostics["solver_calls"] = solver_calls
        diagnostics["joint_evaluated"] = len(hard_joints)
        if diagnostics.get("fallback_reason"):
            diagnostics["fallback_used"] = not bool(hard_evaluations or soft_evaluations)
            if diagnostics["fallback_used"]:
                asks = _hard_unlock_fallback(observation, hard_shortlist)
        return finish(asks)
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        fallback = _hard_unlock_fallback(observation, hard_shortlist)
        return finish(
            fallback, solver_calls=solver_calls, fallback_used=True,
            fallback_reason="safe_exception",
        )


def _fallback(observation, config, reason, generated=0, shortlisted=0, solver_calls=0):
    if config.ask_mode == "selective_joint_voi":
        return [], {
            "strategy": config.name,
            "candidates_generated": generated,
            "shortlisted": shortlisted,
            "evaluated": 0,
            "scenarios": 0,
            "solver_calls": solver_calls,
            "joint_candidates": 0,
            "joint_evaluated": 0,
            "joint_selected": 0,
            "fallback_used": True,
            "fallback_reason": reason,
            "selection_rule": "positive_counterfactual_value_only",
            "selected": 0,
        }
    asks = safe_ask_batch(observation, select_count_based_asks(observation))
    return asks, {
        "strategy": config.name,
        "candidates_generated": generated,
        "shortlisted": shortlisted,
        "evaluated": 0,
        "scenarios": 0,
        "solver_calls": solver_calls,
        "joint_candidates": 0,
        "joint_evaluated": 0,
        "joint_selected": 0,
        "fallback_used": True,
        "fallback_reason": reason,
        "selected": len(asks),
    }


def select_voi_asks(observation, config, pair_scorer=None):
    if config.ask_mode == "hard_unlock_voi":
        return select_hard_unlock_asks(observation, config, pair_scorer)
    started = time.perf_counter()
    candidates = build_question_metadata(observation)
    generated = len(candidates)
    if config.ask_mode == "voi_only":
        shortlist = voi_only_shortlist(candidates, min(config.max_candidates, config.shortlist_size))
    elif config.ask_mode == "count_voi":
        shortlist = count_shortlist(candidates, min(config.max_candidates, config.shortlist_size))
    else:
        shortlist = diversified_shortlist(candidates, min(config.max_candidates, config.shortlist_size))
    if not shortlist:
        return [], {
            "strategy": config.name, "candidates_generated": generated, "shortlisted": 0,
            "evaluated": 0, "scenarios": 0, "solver_calls": 0,
            "joint_candidates": 0, "joint_evaluated": 0, "joint_selected": 0,
            "fallback_used": False, "selected": 0,
        }
    solver_calls = 1
    try:
        current_value = allocation_value(observation, config)
        if time.perf_counter() - started > config.ask_time_budget_seconds:
            return _fallback(observation, config, "time_cap", generated, len(shortlist), solver_calls)
        evaluations = []
        scenario_count = 0
        for candidate in shortlist:
            if time.perf_counter() - started > config.ask_time_budget_seconds:
                return _fallback(observation, config, "time_cap", generated, len(shortlist), solver_calls)
            scenarios = plausible_scenarios(candidate, observation, config.max_scenarios_per_question)
            required_calls = sum(scenario.name != "declined" for scenario in scenarios)
            if solver_calls + required_calls > config.max_solver_calls:
                return _fallback(observation, config, "solver_call_cap", generated, len(shortlist), solver_calls)
            evaluation = evaluate_question(candidate, observation, config, current_value)
            evaluations.append(evaluation)
            solver_calls += evaluation.solver_calls
            scenario_count += len(scenarios)

        joint_candidates = ()
        joint_evaluations = []
        if config.ask_mode in (
            "diversified_voi", "joint_budget_voi", "joint_budget_no_redundancy", "selective_joint_voi",
        ):
            joint_candidates = complementary_candidate_pairs(shortlist, observation)
            singles_by_key = {item.candidate.key(): item for item in evaluations}
            for first, second in joint_candidates:
                if time.perf_counter() - started > config.ask_time_budget_seconds:
                    return _fallback(observation, config, "time_cap", generated, len(shortlist), solver_calls)
                if solver_calls + 1 > config.max_solver_calls:
                    break
                evaluation = evaluate_joint_question_pair(
                    first,
                    second,
                    observation,
                    config,
                    current_value,
                    singles_by_key,
                )
                joint_evaluations.append(evaluation)
                solver_calls += evaluation.solver_calls

        if config.ask_mode == "single_only_voi":
            asks = select_joint_budget_aware(
                evaluations,
                observation.ask_budget,
                (),
                include_zero_voi_hard_fallback=False,
            )
        elif config.ask_mode in ("joint_budget_voi", "joint_budget_no_redundancy", "selective_joint_voi"):
            asks = select_joint_budget_aware(
                evaluations,
                observation.ask_budget,
                joint_evaluations,
                apply_redundancy_penalty=(config.ask_mode != "joint_budget_no_redundancy"),
                include_zero_voi_hard_fallback=(config.ask_mode != "selective_joint_voi"),
            )
        else:
            asks = select_cost_aware(
                evaluations,
                observation.ask_budget,
                config.ask_mode,
                joint_evaluations,
            )
        asks = safe_ask_batch(observation, asks)
        selected_keys = {(item["member_id"], item["field"]) for item in asks}
        joint_selected = sum(
            item.first.key() in selected_keys and item.second.key() in selected_keys
            for item in joint_evaluations
            if item.expected_delta > 0.0
        )
        return asks, {
            "strategy": config.name,
            "candidates_generated": generated,
            "shortlisted": len(shortlist),
            "evaluated": len(evaluations),
            "scenarios": scenario_count,
            "solver_calls": solver_calls,
            "joint_candidates": len(joint_candidates),
            "joint_evaluated": len(joint_evaluations),
            "joint_selected": joint_selected,
            "fallback_used": False,
            "zero_immediate_voi": sum(item.expected_delta <= 0.0 for item in evaluations),
            "selection_rule": (
                "positive_counterfactual_value_only"
                if config.ask_mode == "selective_joint_voi" else "standard"
            ),
            "selected": len(asks),
        }
    except (KeyError, TypeError, ValueError, OverflowError):
        return _fallback(observation, config, "safe_exception", generated, len(shortlist), solver_calls)
