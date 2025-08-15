from __future__ import annotations
from typing import Dict, List
from statistics import mean
from .config import ScoringConfig
from .normalize import fraction_for, label_weight_for

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def weighted_mean(values: Dict[str, float], weights: Dict[str, float]) -> float:
    if not values:
        return 0.0
    if not weights:
        return mean(values.values())
    num = den = 0.0
    for k, v in values.items():
        w = float(weights.get(k, 1.0))
        num += v * w
        den += w
    return (num / den) if den > 0 else mean(values.values())

def compute_daily_score(cfg: ScoringConfig, entries: Dict[str, str], junk_eating: bool) -> Dict[str, float]:
    eff_fractions: Dict[str, float] = {}
    per_activity_scores: Dict[str, float] = {}

    for act in cfg.activities.keys():
        frac = fraction_for(cfg, act, entries.get(act))
        mult = label_weight_for(cfg, act, entries.get(act))
        eff = clamp(frac * mult, 0.0, 1.0)
        eff_fractions[act] = eff
        per_activity_scores[f"{act}_score"] = round(eff * 100.0, 2)

    core_mean = weighted_mean(eff_fractions, cfg.weights_activities)
    base_core_score = core_mean * 100.0

    delta = cfg.bonus.bad_delta if junk_eating else cfg.bonus.good_delta
    final_daily_score = clamp(base_core_score + delta, cfg.bonus.clamp_min, cfg.bonus.clamp_max)

    return {
        "base_core_score": round(base_core_score, 2),
        "bonus_delta": float(delta),
        "final_daily_score": round(final_daily_score, 2),
        **per_activity_scores,
    }

def compute_program_summary(cfg: ScoringConfig, daily_entries: List[Dict[str, str]], junk_flags: List[bool]) -> Dict[str, float]:
    from statistics import mean
    assert len(daily_entries) == len(junk_flags), "daily_entries and junk_flags length mismatch."

    daily_scores: List[float] = []
    accum: Dict[str, List[float]] = {a: [] for a in cfg.activities.keys()}

    for entry, junk in zip(daily_entries, junk_flags):
        res = compute_daily_score(cfg, entry, junk)
        daily_scores.append(res["final_daily_score"])
        for a in cfg.activities.keys():
            accum[a].append(res[f"{a}_score"] / 100.0)

    program_overall = round(mean(daily_scores), 2) if daily_scores else 0.0
    per_activity_overall = {
        f"{a}_overall": round((mean(vs) if vs else 0.0) * 100.0, 2)
        for a, vs in accum.items()
    }

    return {
        "program_overall_score": program_overall,
        "days_counted": len(daily_scores),
        "avg_daily_score": program_overall,
        **per_activity_overall
    }
