import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = PROJECT_ROOT / "tests" / "fixtures" / "phase1_acceptance_cases.v1.json"
SCHEMA_PATH = (
    PROJECT_ROOT / "contracts" / "phase1_acceptance_cases.schema.json"
)

CATEGORIES = {"consultation", "safety", "quality", "management", "logistics"}
ROUTES = {"direct_answer", "collect_more_info", "propose_workflow", "human_review"}
RISK_LEVELS = ("undetermined", "low", "medium", "high", "emergency")
CHALLENGE_TAGS = {
    "normal",
    "insufficient_information",
    "high_risk",
    "easily_misclassified",
}
PROHIBITED_BEHAVIORS = {
    "fabricate_facts",
    "fabricate_rules_or_sources",
    "make_definitive_engineering_judgment",
    "assign_blame_or_liability",
    "trigger_or_modify_workflow",
    "punish_or_close_automatically",
    "omit_uncertainty",
    "omit_immediate_safety_action",
    "request_unnecessary_sensitive_data",
    "treat_hypothetical_as_confirmed_incident",
}
EXPECTED_IDS = {
    *(f"CONS-{number:03d}" for number in range(1, 5)),
    *(f"SAFE-{number:03d}" for number in range(1, 5)),
    *(f"QUAL-{number:03d}" for number in range(1, 5)),
    *(f"MGMT-{number:03d}" for number in range(1, 5)),
    *(f"LOGI-{number:03d}" for number in range(1, 5)),
}
PREFIX_BY_CATEGORY = {
    "consultation": "CONS",
    "safety": "SAFE",
    "quality": "QUAL",
    "management": "MGMT",
    "logistics": "LOGI",
}

RiskLevel = Literal["undetermined", "low", "medium", "high", "emergency"]
Category = Literal["consultation", "safety", "quality", "management", "logistics"]
Route = Literal[
    "direct_answer", "collect_more_info", "propose_workflow", "human_review"
]
ChallengeTag = Literal[
    "normal", "insufficient_information", "high_risk", "easily_misclassified"
]
ProhibitedBehavior = Literal[
    "fabricate_facts",
    "fabricate_rules_or_sources",
    "make_definitive_engineering_judgment",
    "assign_blame_or_liability",
    "trigger_or_modify_workflow",
    "punish_or_close_automatically",
    "omit_uncertainty",
    "omit_immediate_safety_action",
    "request_unnecessary_sensitive_data",
    "treat_hypothetical_as_confirmed_incident",
]


class RiskInterval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum: RiskLevel
    maximum: RiskLevel

    @model_validator(mode="after")
    def minimum_must_not_exceed_maximum(self) -> "RiskInterval":
        assert RISK_LEVELS.index(self.minimum) <= RISK_LEVELS.index(self.maximum)
        return self


class RequiredPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    action: Literal["extract", "ask"]
    description: str = Field(min_length=1, max_length=200)


class AcceptanceCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^(CONS|SAFE|QUAL|MGMT|LOGI)-00[1-4]$")
    category: Category
    user_input: str = Field(min_length=1, max_length=1000)
    expected_risk_interval: RiskInterval
    expected_route: Route
    required_points: list[RequiredPoint] = Field(min_length=1)
    requires_human_review: bool
    prohibited_behaviors: list[ProhibitedBehavior] = Field(min_length=1)
    challenge_tags: list[ChallengeTag] = Field(min_length=1)


class AcceptanceSuite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"]
    suite_id: Literal["phase1-fixed-text-v1"]
    cases: list[AcceptanceCase] = Field(min_length=20, max_length=20)


def load_suite() -> AcceptanceSuite:
    return AcceptanceSuite.model_validate_json(CASES_PATH.read_text(encoding="utf-8"))


def test_machine_readable_cases_match_frozen_contract() -> None:
    suite = load_suite()

    assert suite.schema_version == "1.0.0"
    assert suite.suite_id == "phase1-fixed-text-v1"
    assert len(suite.cases) == 20


def test_schema_is_strict_and_uses_the_same_frozen_vocabularies() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    case_schema = schema["$defs"]["acceptance_case"]

    assert schema["additionalProperties"] is False
    assert case_schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"]["const"] == "1.0.0"
    assert schema["properties"]["suite_id"]["const"] == "phase1-fixed-text-v1"
    assert set(case_schema["required"]) == set(AcceptanceCase.model_fields)
    assert set(case_schema["properties"]["category"]["enum"]) == CATEGORIES
    assert set(case_schema["properties"]["expected_route"]["enum"]) == ROUTES
    assert set(schema["$defs"]["risk_level"]["enum"]) == set(RISK_LEVELS)
    assert set(schema["$defs"]["prohibited_behavior"]["enum"]) == (
        PROHIBITED_BEHAVIORS
    )
    assert set(
        case_schema["properties"]["challenge_tags"]["items"]["enum"]
    ) == CHALLENGE_TAGS


def test_suite_has_exactly_four_cases_per_category_and_stable_ids() -> None:
    cases = load_suite().cases
    ids = [case.id for case in cases]

    assert len(ids) == len(set(ids))
    assert set(ids) == EXPECTED_IDS
    assert Counter(case.category for case in cases) == Counter(
        {category: 4 for category in CATEGORIES}
    )
    assert all(case.id.startswith(PREFIX_BY_CATEGORY[case.category]) for case in cases)


def test_inputs_and_required_point_keys_are_unambiguous() -> None:
    cases = load_suite().cases

    assert len({case.user_input for case in cases}) == len(cases)
    for case in cases:
        point_keys = [point.key for point in case.required_points]
        assert len(point_keys) == len(set(point_keys)), case.id
        assert len(case.prohibited_behaviors) == len(
            set(case.prohibited_behaviors)
        ), case.id
        assert len(case.challenge_tags) == len(set(case.challenge_tags)), case.id


def test_all_required_challenge_types_are_covered() -> None:
    cases = load_suite().cases
    covered_tags = {tag for case in cases for tag in case.challenge_tags}

    assert covered_tags == CHALLENGE_TAGS
    assert all(any(tag in case.challenge_tags for case in cases) for tag in CHALLENGE_TAGS)


def test_insufficient_information_cases_require_questions_and_uncertainty() -> None:
    cases = load_suite().cases
    insufficient_cases = [
        case for case in cases if "insufficient_information" in case.challenge_tags
    ]

    assert insufficient_cases
    for case in insufficient_cases:
        assert any(point.action == "ask" for point in case.required_points), case.id
        assert "omit_uncertainty" in case.prohibited_behaviors, case.id


def test_high_risk_cases_enforce_human_review_and_immediate_safety_boundary() -> None:
    cases = load_suite().cases
    high_risk_cases = [case for case in cases if "high_risk" in case.challenge_tags]

    assert high_risk_cases
    for case in high_risk_cases:
        maximum = RISK_LEVELS.index(case.expected_risk_interval.maximum)
        assert maximum >= RISK_LEVELS.index("high"), case.id
        assert case.expected_route == "human_review", case.id
        assert case.requires_human_review is True, case.id
        assert "omit_immediate_safety_action" in case.prohibited_behaviors, case.id
