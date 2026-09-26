"""One-day Dongqiudi enrichment experiment for HH520 Stable V3.5.1.

Research-only: Stable production rules are not modified.
Collect historical HH520 10027 data, isolate result labels, replay the frozen
model with and without external enrichment, and run an FT group-ablation
tournament across SHOTS / RESULT_STABILITY / HALF_TIMING availability.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from collections import Counter
from pathlib import Path

from collector.service import collect_date
from collector.goal_timing_service import enrich_matches_with_goal_timing
from engine.probability_layer import probability_layer
from engine.full_data_layer import (
    _profile, _side_attack, _stability_distribution, _norm3, _clip, data_mode,
)
from prediction.builder import prepare_match
from research.result_label.collector import collect_result_labels

POSTMATCH_KEYS = {
    "result", "half_score", "full_score", "actual_score", "actual_half_score",
    "actual_outcome", "actual_total_goals", "result_label", "label_status",
    "label_match_method",
}
OUTCOME_ZH = {"主胜": "HOME", "平": "DRAW", "客胜": "AWAY"}
OUTCOMES = ("home", "draw", "away")


def _strip_postmatch(row):
    out = copy.deepcopy(row)
    for k in POSTMATCH_KEYS:
        out.pop(k, None)
    return out


def _score_pair(v):
    import re
    m = re.search(r"(\d+)\s*[-:：]\s*(\d+)", str(v or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _actual_htft(label):
    h = _score_pair(label.get("actual_half_score"))
    f = _score_pair(label.get("actual_score"))
    if not h or not f:
        return None
    def side(p):
        return "主" if p[0] > p[1] else "客" if p[0] < p[1] else "平"
    return f"{side(h)}/{side(f)}"


def _metrics(preds, label_map):
    out = {
        "predicted": 0,
        "wdl": {"evaluable": 0, "hits": 0},
        "score_top2": {"evaluable": 0, "hits": 0},
        "htft_top2": {"evaluable": 0, "hits": 0},
        "total_goals": {"evaluable": 0, "hits": 0},
    }
    for row in preds:
        key = str(row.get("match_id") or "")
        lab = label_map.get(key)
        if not lab or row.get("status") != "PREDICTED":
            continue
        out["predicted"] += 1
        actual = lab.get("actual_outcome")
        predicted = OUTCOME_ZH.get(row.get("direction"))
        if actual in {"HOME", "DRAW", "AWAY"} and predicted:
            out["wdl"]["evaluable"] += 1
            out["wdl"]["hits"] += int(actual == predicted)
        actual_score = _score_pair(lab.get("actual_score"))
        picks = [_score_pair(row.get("score1")), _score_pair(row.get("score2"))]
        picks = [x for x in picks if x]
        if actual_score and picks:
            out["score_top2"]["evaluable"] += 1
            out["score_top2"]["hits"] += int(actual_score in picks[:2])
        actual_htft = _actual_htft(lab)
        htft = [row.get("htft1"), row.get("htft2")]
        htft = [x for x in htft if x and x != "未提供"]
        if actual_htft and htft:
            out["htft_top2"]["evaluable"] += 1
            out["htft_top2"]["hits"] += int(actual_htft in htft[:2])
        ag = lab.get("actual_total_goals")
        pg = str(row.get("total_goals") or "").replace("球", "")
        try:
            pg = int(pg)
        except Exception:
            pg = None
        if isinstance(ag, int) and pg is not None:
            out["total_goals"]["evaluable"] += 1
            out["total_goals"]["hits"] += int(ag == pg)
    for k in ("wdl", "score_top2", "htft_top2", "total_goals"):
        n = out[k]["evaluable"]
        out[k]["accuracy"] = out[k]["hits"] / n if n else None
    return out


def _group_availability(match):
    hp, ap = _profile(match, "home"), _profile(match, "away")
    shots_keys = ("shots", "shots_on_target", "shot_conversion", "shots_off_target")
    stab_keys = ("wins_rate", "draws_rate", "losses_rate")
    def present(d, keys):
        return sum(1 for k in keys if isinstance(d.get(k), (int, float)) and math.isfinite(float(d[k])))
    timing = match.get("goal_timing") or {}
    h = timing.get("home") or {}; a = timing.get("away") or {}
    timing_ok = all(isinstance(x, (int, float)) and math.isfinite(float(x)) for x in (
        h.get("first_half_gf_signal"), h.get("first_half_ga_signal"),
        a.get("first_half_gf_signal"), a.get("first_half_ga_signal"),
    ))
    return {
        "SHOTS": present(hp, shots_keys) >= 1 and present(ap, shots_keys) >= 1,
        "RESULT_STABILITY": present(hp, stab_keys) >= 2 and present(ap, stab_keys) >= 2,
        "HALF_TIMING": timing_ok,
    }


def _ft_candidate(match, groups):
    base = probability_layer(match)
    if not base.get("valid"):
        return None
    probs = base.get("probabilities") or {}
    base_vec = [float(probs[k]) for k in OUTCOMES]
    avail = _group_availability(match)
    used = []
    parts = []
    weights = []
    hp, ap = _profile(match, "home"), _profile(match, "away")
    if "RESULT_STABILITY" in groups and avail["RESULT_STABILITY"]:
        stab = _stability_distribution(hp, ap)
        if stab:
            parts.append(stab); weights.append(0.17); used.append("RESULT_STABILITY")
    if "SHOTS" in groups and avail["SHOTS"]:
        ha, aa = _side_attack(hp), _side_attack(ap)
        diff = _clip(ha-aa, -1.5, 1.5)
        side_home = 1.0/(1.0+math.exp(-diff))
        shot = _norm3([0.72*side_home, 0.28, 0.72*(1.0-side_home)])
        parts.append(shot); weights.append(0.05); used.append("SHOTS")
    # HALF_TIMING intentionally does not alter FT in the frozen production model.
    ext = sum(weights)
    mix = [(1.0-ext)*base_vec[i] for i in range(3)]
    for vec, w in zip(parts, weights):
        for i in range(3):
            mix[i] += w*vec[i]
    mix = _norm3(mix)
    direction = OUTCOMES[max(range(3), key=lambda i: mix[i])]
    return {"direction": direction, "probabilities": dict(zip(OUTCOMES, mix)), "used": used, "availability": avail}


def _ft_tournament(matches, label_map):
    combos = [
        ("BASE", ()),
        ("SHOTS", ("SHOTS",)),
        ("RESULT_STABILITY", ("RESULT_STABILITY",)),
        ("SHOTS+RESULT_STABILITY", ("SHOTS","RESULT_STABILITY")),
        ("HALF_TIMING", ("HALF_TIMING",)),
        ("SHOTS+HALF_TIMING", ("SHOTS","HALF_TIMING")),
        ("RESULT_STABILITY+HALF_TIMING", ("RESULT_STABILITY","HALF_TIMING")),
        ("ALL3", ("SHOTS","RESULT_STABILITY","HALF_TIMING")),
    ]
    out = {}
    for name, groups in combos:
        n = hits = changed = usable = 0
        for m in matches:
            lab = label_map.get(str(m.get("match_id") or ""))
            if not lab:
                continue
            cand = _ft_candidate(m, groups)
            base = _ft_candidate(m, ())
            if not cand or not base:
                continue
            actual = lab.get("actual_outcome")
            if actual not in {"HOME","DRAW","AWAY"}:
                continue
            n += 1
            dmap = {"home":"HOME","draw":"DRAW","away":"AWAY"}
            hits += int(dmap[cand["direction"]] == actual)
            changed += int(cand["direction"] != base["direction"])
            if name == "BASE":
                usable += 1
            else:
                required = [g for g in groups if g != "HALF_TIMING"]  # timing does not move FT
                usable += int(all(cand["availability"].get(g, False) for g in required))
        out[name] = {
            "evaluable": n,
            "hits": hits,
            "accuracy": hits/n if n else None,
            "direction_changes_vs_base": changed,
            "fully_available_for_ft_groups": usable,
            "note": "HALF_TIMING affects HT/FT, not FT probability in frozen Stable V3.5.1" if "HALF_TIMING" in groups else None,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    raw = collect_date(args.date)
    records = []
    for m in raw.get("matches", []):
        x = copy.deepcopy(m); x["date"] = args.date; records.append(x)
    labels = collect_result_labels(records)
    label_map = {str(x["match_id"]): x for x in labels}

    baseline_matches = [_strip_postmatch(x) for x in records]
    baseline_predictions = [prepare_match(x) for x in baseline_matches]

    enriched_matches = [_strip_postmatch(x) for x in records]
    timing_summary = enrich_matches_with_goal_timing(args.date, enriched_matches)
    enriched_predictions = [prepare_match(x) for x in enriched_matches]

    domains = Counter()
    mode_counts = Counter()
    group_counts = Counter()
    field_counts = Counter()
    dongqiudi_matches = 0
    for m in enriched_matches:
        t = m.get("goal_timing") or {}
        src = t.get("source_domain") or ""
        if src:
            for d in str(src).split(","):
                domains[d] += 1
        if "dongqiudi.com" in str(src):
            dongqiudi_matches += 1
        mode_counts[data_mode(m)["mode"]] += 1
        av = _group_availability(m)
        for k,v in av.items():
            group_counts[k] += int(v)
        for side in ("home","away"):
            for k,v in _profile(m,side).items():
                if isinstance(v,(int,float)) and math.isfinite(float(v)):
                    field_counts[k] += 1

    result = {
        "experiment": "DONGQIUDI_SEP11_FULL_MODEL_TEST_V1",
        "date": args.date,
        "stable_mutated": False,
        "stable_version": "HH520 Stable V3.5.1",
        "match_count": len(records),
        "result_labels": len(labels),
        "timing_summary": timing_summary,
        "source_domains": dict(domains),
        "dongqiudi_matches": dongqiudi_matches,
        "data_modes": dict(mode_counts),
        "group_coverage_matches": dict(group_counts),
        "profile_field_side_coverage": dict(field_counts),
        "baseline_metrics": _metrics(baseline_predictions, label_map),
        "enriched_metrics": _metrics(enriched_predictions, label_map),
        "ft_group_tournament": _ft_tournament(enriched_matches, label_map),
        "per_match": [
            {
                "match_id": str(m.get("match_id") or ""),
                "league": m.get("league"),
                "home_team": m.get("home_team"),
                "away_team": m.get("away_team"),
                "source_domain": (m.get("goal_timing") or {}).get("source_domain"),
                "timing_mode": (m.get("goal_timing") or {}).get("timing_mode"),
                "groups": _group_availability(m),
                "data_mode": data_mode(m)["mode"],
                "actual": label_map.get(str(m.get("match_id") or "")),
                "baseline": next((p for p in baseline_predictions if p.get("match_id")==str(m.get("match_id") or "")), None),
                "enriched": next((p for p in enriched_predictions if p.get("match_id")==str(m.get("match_id") or "")), None),
            }
            for m in enriched_matches
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
