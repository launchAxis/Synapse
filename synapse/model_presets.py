from __future__ import annotations

import os
from dataclasses import dataclass

from synapse.config import FINAL_SYNTHESIS_MODEL_KEY, MODELS


MODEL_PRESETS = {"local", "hybrid", "strong"}
INTERNAL_JUDGE_KEY = "__judge__"
INTERNAL_SYNTHESIS_KEY = "__synthesis__"


@dataclass(frozen=True)
class CouncilModelPlan:
    preset: str
    configured_models: dict[str, str]
    council_keys: tuple[str, ...]
    judge_key: str | None = None
    synthesis_key: str | None = None


def resolve_model_plan(
    preset: str = "local",
    base_models: dict[str, str] | None = None,
) -> CouncilModelPlan:
    selected = normalize_model_preset(preset)
    configured = dict(base_models or MODELS)
    council_keys = tuple(configured.keys())
    judge_key: str | None = None
    synthesis_key: str | None = None

    if selected == "hybrid":
        judge_model = os.environ.get("SYNAPSE_HYBRID_JUDGE_MODEL", "").strip()
        synthesis_model = os.environ.get("SYNAPSE_HYBRID_SYNTHESIS_MODEL", "").strip()
        if judge_model:
            configured[INTERNAL_JUDGE_KEY] = judge_model
            judge_key = INTERNAL_JUDGE_KEY
        if synthesis_model:
            configured[INTERNAL_SYNTHESIS_KEY] = synthesis_model
            synthesis_key = INTERNAL_SYNTHESIS_KEY

    if selected == "strong":
        shared_model = os.environ.get("SYNAPSE_STRONG_MODEL", "").strip()
        judge_model = os.environ.get("SYNAPSE_STRONG_JUDGE_MODEL", "").strip() or shared_model
        synthesis_model = os.environ.get("SYNAPSE_STRONG_SYNTHESIS_MODEL", "").strip() or shared_model
        if judge_model:
            configured[INTERNAL_JUDGE_KEY] = judge_model
            judge_key = INTERNAL_JUDGE_KEY
        if synthesis_model:
            configured[INTERNAL_SYNTHESIS_KEY] = synthesis_model
            synthesis_key = INTERNAL_SYNTHESIS_KEY

    return CouncilModelPlan(
        preset=selected,
        configured_models=configured,
        council_keys=council_keys,
        judge_key=judge_key,
        synthesis_key=synthesis_key,
    )


def normalize_model_preset(value: str | None) -> str:
    preset = (value or "local").strip().lower()
    return preset if preset in MODEL_PRESETS else "local"


def phase_models(
    usable_models: dict[str, str],
    plan: CouncilModelPlan,
) -> tuple[dict[str, str], dict[str, str], str | None]:
    council_models = {key: usable_models[key] for key in plan.council_keys if key in usable_models}
    judge_models = dict(council_models)
    if plan.judge_key and plan.judge_key in usable_models:
        judge_models["J"] = usable_models[plan.judge_key]
    synthesis_model = usable_models.get(plan.synthesis_key or "") if plan.synthesis_key else None
    if not synthesis_model and FINAL_SYNTHESIS_MODEL_KEY in council_models:
        synthesis_model = council_models[FINAL_SYNTHESIS_MODEL_KEY]
    if not synthesis_model and council_models:
        synthesis_model = next(iter(council_models.values()))
    return council_models, judge_models, synthesis_model
