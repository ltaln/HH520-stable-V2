"""Forward information-gain validation for HH520.

Research-only. Stable 3.5.1 is never modified.
External profile snapshot is frozen before target dates:
- Collection1 / FootyStats profile snapshot committed 2026-09-25T10:29:38Z
Targets:
- 2026-09-26
- 2026-09-27
No target labels are used for model/group/weight selection.
"""
from __future__ import annotations

import json
import math
import os
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import numpy as np
import collection1_full_profile_ablation as c1
from collector.service import collect_date
from collector.cache_manager import load_cache

TARGET_DATES = ("2026-09-26", "2026-09-27")
SNAPSHOT_UTC = "2026-09-25T10:29:38Z"


def _stable_record(day, match):
    half = c1.parse_score(match.get("half_score"))
    full = c1.parse_score(match.get("result") or match.get("full_score"))
    if not half or not full:
        return None

    prematch = deepcopy(match)
    for k in c1.POSTMATCH:
        prematch.pop(k, None)

    prob = c1.probability_layer(prematch)
    if not prob.get("valid"):
        return None
    dec = c1.decision_filter(prematch, prob, prematch.get("value") or {})
    ht = c1.htft_layer(prob, prematch, dec)
    sc = c1.score_layer(prematch, prob, ht)
    if not ht.get("valid") or not sc.get("valid"):
        return None

    return {
        "date": day,
        "home_team": match.get("home_team"),
        "away_team": match.get("away_team"),
        "actual_score": full,
        "actual_ft": c1.outcome(full),
        "actual_htft": f"{c1.outcome(half)}_{c1.outcome(full)}",
        "ft_probs": prob.get("probabilities"),
        "ft_current": str(dec.get("resolved_direction") or prob.get("direction") or "").upper(),
        "htft_dist": {x["ht"] + "_" + x["ft"]: float(x["probability"]) for x in ht.get("distribution", [])},
        "score_dist": {x["score"]: float(x["probability"]) for x in sc.get("all_scores", [])},
        "lambda_home": float(sc["lambda_home"]),
        "lambda_away": float(sc["lambda_away"]),
    }


def _collect_targets():
    rows = []
    cache_misses = 0
    per_date = {}
    for day in TARGET_DATES:
        existed = load_cache(day) is not None
        payload = collect_date(day)
        if not existed:
            cache_misses += 1
        n = 0
        for m in payload.get("matches", []):
            r = _stable_record(day, m)
            if r is not None:
                rows.append(r)
                n += 1
        per_date[day] = {
            "evaluable": n,
            "cache_reused": existed,
            "captured_at": payload.get("captured_at"),
        }
    rows.sort(key=lambda r: (r["date"], r["home_team"] or "", r["away_team"] or ""))
    return rows, cache_misses, per_date


def _score_baseline(rows):
    P, keys = c1.score_matrix(rows)
    return c1.score_metric(P, keys, rows)


def _one_group_best(selection, kind, group):
    blocks = c1.blocks(selection)
    if kind == "ft":
        params = [(x,) for x in (.1, 1.0, 5.0)]
    elif kind == "htft":
        params = [(x,) for x in (.5, 2.0, 8.0)]
    else:
        params = [(l, s) for l in (3.0, 10.0, 30.0) for s in (.25, .5, .75)]

    candidates = []
    for param in params:
        folds = []
        for i, val in enumerate(blocks):
            train = [r for j, b in enumerate(blocks) if j != i for r in b]
            if not train or not val:
                continue
            if kind == "ft":
                m = c1.evaluate_ft(train, val, (group,), param[0])
            elif kind == "htft":
                m = c1.evaluate_htft(train, val, (group,), param[0])
            else:
                m = c1.evaluate_score(train, val, (group,), param[0], param[1])
            folds.append(m)
        if not folds:
            continue

        row = {"groups": [group], "params": list(param)}
        if kind == "ft":
            nets = [x["net_top1"] for x in folds]
            row.update(min_primary=min(nets), total_primary=sum(nets), total_secondary=0)
            safe = row["min_primary"] >= 0 and row["total_primary"] > 0
            rank = (row["min_primary"], row["total_primary"], row["total_secondary"])
        elif kind == "htft":
            n1 = [x["net_top1"] for x in folds]
            n2 = [x["net_top2"] for x in folds]
            n3 = [x["net_top3"] for x in folds]
            row.update(
                min_primary=min(n2), total_primary=sum(n2),
                min_top1=min(n1), min_top3=min(n3),
                total_secondary=sum(n1) + sum(n3),
            )
            safe = row["min_primary"] >= 0 and row["min_top1"] >= 0 and row["min_top3"] >= 0 and row["total_primary"] > 0
            rank = (row["min_primary"], row["total_primary"], row["min_top1"], row["min_top3"], row["total_secondary"])
        else:
            n1 = [x["net_top1"] for x in folds]
            n2 = [x["net_top2"] for x in folds]
            row.update(
                min_primary=min(n2), total_primary=sum(n2),
                min_top1=min(n1), total_secondary=sum(n1),
            )
            safe = row["min_primary"] >= 0 and row["min_top1"] >= 0 and row["total_primary"] > 0
            rank = (row["min_primary"], row["total_primary"], row["min_top1"], row["total_secondary"])

        row["safe"] = bool(safe)
        row["_rank"] = rank
        candidates.append(row)

    pool = [x for x in candidates if x["safe"]] or candidates
    if not pool:
        return None
    best = sorted(pool, key=lambda x: x["_rank"], reverse=True)[0]
    best = {k: v for k, v in best.items() if k != "_rank"}
    return best


def _eval_candidate(selection, target, kind, best):
    if not best:
        return None
    return c1.final_eval(selection, target, kind, best)


def _individual_group_tests(selection, target):
    out = {}
    for group in c1.GROUP_NAMES:
        out[group] = {}
        for kind in ("ft", "htft", "score"):
            best = _one_group_best(selection, kind, group)
            out[group][kind] = {
                "selected_on_sep1_14_only": best,
                "forward_sep26_27": _eval_candidate(selection, target, kind, best),
            }
    return out


def main():
    if os.getenv("HH520_INFOGAIN_FORWARD_ONLY") != "1":
        raise SystemExit("forward-only guard missing")

    profile_path = Path("_collection1_profiles.json")
    ablation_path = Path("_collection1_ablation.json")
    if not profile_path.exists() or not ablation_path.exists():
        raise SystemExit("frozen Collection1 artifacts missing")

    collection = json.loads(profile_path.read_text(encoding="utf-8"))
    prior_ablation = json.loads(ablation_path.read_text(encoding="utf-8"))

    historical = c1.load_matches()
    hist_rows, hist_gate = c1.quality_rows(historical, collection)
    selection = [r for r in hist_rows if r["date"] <= "2026-09-14"]

    target_all, firecrawl_calls, per_date = _collect_targets()
    target, target_gate = c1.quality_rows(target_all, collection)

    baseline_all = {
        "ft": c1.ft_baseline(target_all),
        "htft": c1.htft_baseline(target_all),
        "score": _score_baseline(target_all),
    }
    baseline_covered = {
        "ft": c1.ft_baseline(target),
        "htft": c1.htft_baseline(target),
        "score": _score_baseline(target),
    }

    frozen_selected = {}
    for kind in ("ft", "htft", "score"):
        best = ((prior_ablation.get(kind) or {}).get("selected_on_sep1_14_cv"))
        frozen_selected[kind] = {
            "candidate": best,
            "forward_sep26_27": _eval_candidate(selection, target, kind, best),
        }

    single_groups = _individual_group_tests(selection, target)

    primary_summary = {
        "ft_baseline_hits": baseline_covered["ft"].get("top1_hits"),
        "ft_baseline_accuracy": baseline_covered["ft"].get("top1_accuracy"),
        "htft_baseline_top2_hits": baseline_covered["htft"].get("top2_hits"),
        "htft_baseline_top2_accuracy": baseline_covered["htft"].get("top2_accuracy"),
        "score_baseline_top2_hits": baseline_covered["score"].get("top2_hits"),
        "score_baseline_top2_accuracy": baseline_covered["score"].get("top2_accuracy"),
    }
    for kind in ("ft", "htft", "score"):
        m = frozen_selected[kind]["forward_sep26_27"] or {}
        if kind == "ft":
            primary_summary["ft_frozen_net_top1_hits"] = m.get("net_top1")
            primary_summary["ft_frozen_accuracy"] = m.get("top1_accuracy")
        elif kind == "htft":
            primary_summary["htft_frozen_net_top2_hits"] = m.get("net_top2")
            primary_summary["htft_frozen_top2_accuracy"] = m.get("top2_accuracy")
        else:
            primary_summary["score_frozen_net_top2_hits"] = m.get("net_top2")
            primary_summary["score_frozen_top2_accuracy"] = m.get("top2_accuracy")

    out = {
        "status": "READY",
        "kind": "HH520_INFORMATION_GAIN_FORWARD_VALIDATION_V1",
        "stable_version": "HH520 Stable V3.5.1",
        "research_only": True,
        "stable_modified": False,
        "target_dates": list(TARGET_DATES),
        "external_snapshot_utc": SNAPSHOT_UTC,
        "external_snapshot_precedes_targets": True,
        "selection_window": "2026-09-01..2026-09-14",
        "target_labels_used_for_selection": False,
        "target_labels_used_for_tuning": False,
        "objective": "Measure incremental value of independent external information, not new model complexity.",
        "external_groups": c1.GROUPS,
        "collection_source_summary": collection.get("summary"),
        "historical_quality_gate": hist_gate,
        "selection_n": len(selection),
        "target_all_n": len(target_all),
        "target_profile_covered_n": len(target),
        "target_profile_coverage": len(target) / len(target_all) if target_all else 0.0,
        "target_quality_gate": target_gate,
        "target_collection": per_date,
        "firecrawl_calls_for_target_10027": firecrawl_calls,
        "baseline_all_target": baseline_all,
        "baseline_profile_covered_target": baseline_covered,
        "frozen_selected_combinations": frozen_selected,
        "single_external_group_forward_tests": single_groups,
        "primary_summary": primary_summary,
        "methodology": {
            "external_features_frozen_before_target_dates": True,
            "formal_frozen_combinations_loaded_from_prior_sep1_14_selection": True,
            "single_group_hyperparameters_selected_only_on_sep1_14_blocked_cv": True,
            "forward_dates_never_used_to_choose_group_or_weight": True,
            "comparison_population": "same profile-covered target matches for baseline and challenger",
            "stable_production_code_changed": False,
        },
    }

    Path("_information_gain_forward.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "status": out["status"],
        "target_all_n": out["target_all_n"],
        "target_profile_covered_n": out["target_profile_covered_n"],
        "target_profile_coverage": out["target_profile_coverage"],
        "firecrawl_calls_for_target_10027": out["firecrawl_calls_for_target_10027"],
        "primary_summary": out["primary_summary"],
        "frozen_selected": {
            k: v["forward_sep26_27"] for k, v in out["frozen_selected_combinations"].items()
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
