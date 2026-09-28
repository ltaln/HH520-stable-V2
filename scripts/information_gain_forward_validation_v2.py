"""Forward information-gain validation V2.

Uses cached target-date HH520 snapshots as the prediction feature snapshot and
fetches fresh historical HH520 pages only for isolated result labels. The
frozen FootyStats/Collection1 profile snapshot was committed before target
dates. Stable 3.5.1 production code is not modified.
"""
from __future__ import annotations

import json
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

import collection1_full_profile_ablation as c1
import information_gain_forward_validation as v1
from collector.service import collect_date, validate_raw
from collector.cache_manager import load_cache
from collector.url_builder import build_10027s_url
from collector.firecrawl_client import scrape_markdown
from collector.hh520_10027_parser import parse_10027s_markdown

TARGET_DATES = ("2026-09-26", "2026-09-27")
SNAPSHOT_UTC = "2026-09-25T10:29:38Z"


def fresh_label_map(day):
    raw = scrape_markdown(build_10027s_url(day, day))
    md = validate_raw(day, raw)
    matches = parse_10027s_markdown(md)
    by_id = {}
    by_teams = {}
    for m in matches:
        full = c1.parse_score(m.get("result") or m.get("full_score"))
        half = c1.parse_score(m.get("half_score"))
        if not full or not half:
            continue
        lab = {"full": full, "half": half}
        mid = str(m.get("match_id") or "")
        if mid:
            by_id[mid] = lab
        by_teams[(str(m.get("home_team") or ""), str(m.get("away_team") or ""))] = lab
    return by_id, by_teams, len(matches), len(by_id)


def collect_targets():
    rows = []
    feature_firecrawl_calls = 0
    label_firecrawl_calls = 0
    per_date = {}

    for day in TARGET_DATES:
        existed = load_cache(day) is not None
        payload = collect_date(day)
        if not existed:
            feature_firecrawl_calls += 1

        by_id, by_teams, label_page_matches, label_count = fresh_label_map(day)
        label_firecrawl_calls += 1

        feature_matches = payload.get("matches", [])
        joined = 0
        evaluable = 0
        for m in feature_matches:
            mid = str(m.get("match_id") or "")
            lab = by_id.get(mid)
            if lab is None:
                lab = by_teams.get((str(m.get("home_team") or ""), str(m.get("away_team") or "")))
            if lab is None:
                continue

            augmented = deepcopy(m)
            augmented["result"] = f"{lab['full'][0]}-{lab['full'][1]}"
            augmented["half_score"] = f"{lab['half'][0]}-{lab['half'][1]}"
            row = v1._stable_record(day, augmented)
            if row is not None:
                rows.append(row)
                evaluable += 1
                joined += 1

        per_date[day] = {
            "feature_matches": len(feature_matches),
            "evaluable": evaluable,
            "labels_joined": joined,
            "fresh_label_page_matches": label_page_matches,
            "fresh_labels": label_count,
            "feature_cache_reused": existed,
            "feature_captured_at": payload.get("captured_at"),
        }

    rows.sort(key=lambda r: (r["date"], r["home_team"] or "", r["away_team"] or ""))
    return rows, feature_firecrawl_calls, label_firecrawl_calls, per_date


def main():
    if os.getenv("HH520_INFOGAIN_FORWARD_ONLY") != "1":
        raise SystemExit("forward-only guard missing")

    collection = json.loads(Path("_collection1_profiles.json").read_text(encoding="utf-8"))
    prior_ablation = json.loads(Path("_collection1_ablation.json").read_text(encoding="utf-8"))

    historical = c1.load_matches()
    hist_rows, hist_gate = c1.quality_rows(historical, collection)
    selection = [r for r in hist_rows if r["date"] <= "2026-09-14"]

    target_all, feature_calls, label_calls, per_date = collect_targets()
    target, target_gate = c1.quality_rows(target_all, collection)

    baseline_all = {
        "ft": c1.ft_baseline(target_all),
        "htft": c1.htft_baseline(target_all),
        "score": v1._score_baseline(target_all),
    }
    baseline_covered = {
        "ft": c1.ft_baseline(target),
        "htft": c1.htft_baseline(target),
        "score": v1._score_baseline(target),
    }

    frozen_selected = {}
    for kind in ("ft", "htft", "score"):
        best = ((prior_ablation.get(kind) or {}).get("selected_on_sep1_14_cv"))
        frozen_selected[kind] = {
            "candidate": best,
            "forward_sep26_27": v1._eval_candidate(selection, target, kind, best),
        }

    single_groups = v1._individual_group_tests(selection, target)

    out = {
        "status": "READY",
        "kind": "HH520_INFORMATION_GAIN_FORWARD_VALIDATION_V2",
        "stable_version": "HH520 Stable V3.5.1",
        "research_only": True,
        "stable_modified": False,
        "target_dates": list(TARGET_DATES),
        "external_snapshot_utc": SNAPSHOT_UTC,
        "external_snapshot_precedes_targets": True,
        "selection_window": "2026-09-01..2026-09-14",
        "target_labels_used_for_selection": False,
        "target_labels_used_for_tuning": False,
        "feature_snapshot_policy": "reuse cached target-date HH520 snapshot",
        "label_policy": "fresh historical HH520 page used only for result labels",
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
        "firecrawl_calls_for_target_features": feature_calls,
        "firecrawl_calls_for_result_labels": label_calls,
        "firecrawl_calls_total_this_run": feature_calls + label_calls,
        "baseline_all_target": baseline_all,
        "baseline_profile_covered_target": baseline_covered,
        "frozen_selected_combinations": frozen_selected,
        "single_external_group_forward_tests": single_groups,
        "methodology": {
            "external_features_frozen_before_target_dates": True,
            "formal_frozen_combinations_loaded_from_prior_sep1_14_selection": True,
            "single_group_hyperparameters_selected_only_on_sep1_14_blocked_cv": True,
            "forward_dates_never_used_to_choose_group_or_weight": True,
            "result_labels_isolated_from_prediction_features": True,
            "comparison_population": "same profile-covered target matches for baseline and challenger",
            "stable_production_code_changed": False,
        },
    }

    Path("_information_gain_forward_v2.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps({
        "status": out["status"],
        "target_all_n": out["target_all_n"],
        "target_profile_covered_n": out["target_profile_covered_n"],
        "target_profile_coverage": out["target_profile_coverage"],
        "firecrawl_calls_total_this_run": out["firecrawl_calls_total_this_run"],
        "baseline_profile_covered_target": out["baseline_profile_covered_target"],
        "frozen_selected": {
            k: v["forward_sep26_27"] for k, v in out["frozen_selected_combinations"].items()
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
