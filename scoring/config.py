from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import os, yaml

@dataclass
class BonusRule:
    name: str
    good_delta: float = 5.0
    bad_delta: float = -5.0
    clamp_min: float = 0.0
    clamp_max: float = 100.0

@dataclass
class ActivityConfig:
    labels: Dict[str, float]               # canonical label -> fraction [0..1]
    label_weights: Dict[str, float]        # canonical label -> multiplier (default 1.0)
    aliases: Dict[str, str]                # raw -> canonical

@dataclass
class ScoringConfig:
    activities: Dict[str, ActivityConfig]
    bonus: BonusRule
    weights_activities: Dict[str, float]
    # adaptive extras (from adaptation.yaml)
    levels_order: Dict[str, List[str]] | None = None
    adaptation: Dict[str, Any] | None = None

def _load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def load_config(
    scoring_path: Optional[str] = None,
    adaptation_path: Optional[str] = None
) -> ScoringConfig:
    scoring_path = scoring_path or os.environ.get("SCORING_CONFIG_PATH", "config/scoring.yaml")
    adaptation_path = adaptation_path or os.environ.get("ADAPTATION_CONFIG_PATH", "config/adaptation.yaml")

    raw_scoring = _load_yaml(scoring_path)
    raw_adapt = _load_yaml(adaptation_path)

    b = raw_scoring.get("bonus", {}) or {}
    bonus = BonusRule(
        name=b.get("name", "no_junk_eating"),
        good_delta=float(b.get("good_delta", 5)),
        bad_delta=float(b.get("bad_delta", -5)),
        clamp_min=float(b.get("clamp_min", 0)),
        clamp_max=float(b.get("clamp_max", 100)),
    )

    acts: Dict[str, ActivityConfig] = {}
    for act, conf in (raw_scoring.get("activities") or {}).items():
        labels = conf.get("labels") or {}
        if not labels:
            raise ValueError(f"Activity '{act}' must define 'labels'")
        label_weights = conf.get("label_weights") or {}
        aliases = conf.get("aliases") or {}
        acts[act] = ActivityConfig(
            labels={str(k): float(v) for k, v in labels.items()},
            label_weights={str(k): float(v) for k, v in label_weights.items()},
            aliases={str(k): str(v) for k, v in aliases.items()},
        )

    weights_activities = {str(k): float(v)
                          for k, v in (raw_scoring.get("weights_activities") or {}).items()}

    return ScoringConfig(
        activities=acts,
        bonus=bonus,
        weights_activities=weights_activities,
        levels_order=raw_adapt.get("levels_order") or {},
        adaptation=raw_adapt.get("adaptation") or {},
    )
