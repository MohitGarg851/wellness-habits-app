from __future__ import annotations
from typing import Optional
from .config import ScoringConfig

def resolve_category(cfg: ScoringConfig, activity: str, raw_label: Optional[str]) -> str:
    if activity not in cfg.activities:
        raise KeyError(f"Unknown activity: {activity}")
    labels = cfg.activities[activity].labels
    aliases = cfg.activities[activity].aliases

    if not raw_label:
        return next(iter(labels.keys()))

    if raw_label in labels:
        return raw_label
    if raw_label in aliases:
        return aliases[raw_label]

    low = raw_label.strip().casefold()
    for k in labels:
        if k.casefold() == low:
            return k
    for k, v in aliases.items():
        if k.casefold() == low:
            return v

    return raw_label

def fraction_for(cfg: ScoringConfig, activity: str, label: Optional[str]) -> float:
    canon = resolve_category(cfg, activity, label)
    return float(cfg.activities[activity].labels.get(canon, 0.0))

def label_weight_for(cfg: ScoringConfig, activity: str, label: Optional[str]) -> float:
    canon = resolve_category(cfg, activity, label)
    lw = cfg.activities[activity].label_weights
    return float(lw.get(canon, 1.0))
