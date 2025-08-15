from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from statistics import mean
from .config import ScoringConfig
from .normalize import fraction_for

def _levels_for(cfg: ScoringConfig, activity: str) -> List[str]:
    if cfg.levels_order and activity in cfg.levels_order:
        return cfg.levels_order[activity]
    # fallback: sort labels by difficulty (fraction)
    act = cfg.activities[activity]
    return sorted(act.labels.keys(), key=lambda k: act.labels[k])

def _level_index(levels: List[str], label: str) -> int:
    try:
        return levels.index(label)
    except ValueError:
        return 0

def _met_target(cfg: ScoringConfig, activity: str, chosen_label: str, target_label: str) -> bool:
    f_chosen = fraction_for(cfg, activity, chosen_label)
    f_target = fraction_for(cfg, activity, target_label)
    return f_chosen >= f_target

def _adherence_short(cfg: ScoringConfig, activity: str, chosen_hist: List[str], target_hist: List[str], n: int) -> Tuple[float,int,int]:
    n = min(n, len(chosen_hist), len(target_hist))
    if n == 0:
        return 0.0, 0, 0
    hits = [1 if _met_target(cfg, activity, ch, tg) else 0 for ch, tg in zip(chosen_hist[-n:], target_hist[-n:])]
    adh = sum(hits) / n
    streak = fail_streak = 0
    for ch, tg in zip(reversed(chosen_hist[-n:]), reversed(target_hist[-n:])):
        if _met_target(cfg, activity, ch, tg):
            if fail_streak == 0: streak += 1
            else: break
        else:
            if streak == 0: fail_streak += 1
            else: break
    return adh, streak, fail_streak

def recommend_next_targets(
    cfg: ScoringConfig,
    last_k_entries: List[Dict[str, str]],
    last_k_targets: Optional[List[Dict[str, str]]] = None,
    recent_daily_scores: Optional[List[float]] = None,
    days_since_up: Optional[Dict[str, int]] = None,
    days_since_down: Optional[Dict[str, int]] = None
) -> Dict[str, Dict[str, str]]:
    ad = cfg.adaptation or {}
    short_days = int(ad.get("windows", {}).get("short_days", 3))
    thr = ad.get("thresholds", {})
    up_min_short_adherence = float(thr.get("up_min_short_adherence", 0.80))
    up_min_streak = int(thr.get("up_min_streak", 2))
    up_max_step = int(thr.get("up_max_step", 1))
    down_max_short_adherence = float(thr.get("down_max_short_adherence", 0.40))
    down_min_fail_streak = int(thr.get("down_min_fail_streak", 2))
    down_max_step = int(thr.get("down_max_step", 1))
    cad = ad.get("cadence", {})
    min_days_between_up = int(cad.get("min_days_between_up", 2))
    min_days_between_down = int(cad.get("min_days_between_down", 1))
    state_cfg = ad.get("state", {})
    struggling_lt = float(state_cfg.get("struggling_lt", 50))
    thriving_gt = float(state_cfg.get("thriving_gt", 80))
    essentials = ad.get("essentials_when_struggling", [])

    user_state = "on_track"
    if recent_daily_scores:
        s = mean(recent_daily_scores[-short_days:])
        if s < struggling_lt: user_state = "struggling"
        elif s > thriving_gt: user_state = "thriving"

    if last_k_targets is None or len(last_k_targets) != len(last_k_entries):
        last_k_targets = [{a: d.get(a, "") for a in cfg.activities.keys()} for d in last_k_entries]

    results: Dict[str, Dict[str, str]] = {}

    for act in cfg.activities.keys():
        levels = _levels_for(cfg, act)
        current_target = last_k_targets[-1].get(act) or levels[0]
        current_idx = _level_index(levels, current_target)

        chosen_hist = [d.get(act, "") for d in last_k_entries]
        target_hist = [t.get(act, "") for t in last_k_targets]
        adh, streak, fail_streak = _adherence_short(cfg, act, chosen_hist, target_hist, short_days)

        can_up = (days_since_up or {}).get(act, min_days_between_up) >= min_days_between_up
        can_down = (days_since_down or {}).get(act, min_days_between_down) >= min_days_between_down

        action, step = "keep", 0
        reason = f"adh={adh:.2f}, streak={streak}, fail_streak={fail_streak}"

        if user_state == "struggling" and act not in essentials:
            if can_down and (adh < down_max_short_adherence or fail_streak >= down_min_fail_streak):
                action, step = "down", min(down_max_step, 1)
                reason += " | struggling: easing"
        else:
            if can_down and (adh < down_max_short_adherence or fail_streak >= down_min_fail_streak):
                action, step = "down", min(down_max_step, 1)
                reason += " | easing low adherence"

        if action == "keep":
            if user_state == "thriving":
                if can_up and adh >= max(0.90, up_min_short_adherence) and streak >= max(4, up_min_streak):
                    action, step = "up", min(up_max_step, 1)
                    reason += " | thriving: gentle push"
            else:
                if can_up and adh >= up_min_short_adherence and streak >= up_min_streak:
                    action, step = "up", min(up_max_step, 1)
                    reason += " | consistent: small progress"

        if action == "up":
            next_idx = min(current_idx + step, len(levels) - 1)
        elif action == "down":
            next_idx = max(current_idx - step, 0)
        else:
            next_idx = current_idx

        results[act] = {
            "current_target": current_target,
            "next_target": levels[next_idx],
            "action": action,
            "reason": reason
        }

    return results
