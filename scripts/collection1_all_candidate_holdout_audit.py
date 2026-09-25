import json, os, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

import scripts.collection1_full_profile_ablation as base

def compact_holdout(m,kind):
    if kind=="ft":
        return {"n":m["n"],"top1_hits":m["top1_hits"],"top1_accuracy":m["top1_accuracy"],"baseline_hits":m["baseline"]["top1_hits"],"baseline_accuracy":m["baseline"]["top1_accuracy"],"net_top1":m["net_top1"]}
    if kind=="htft":
        return {"n":m["n"],**{f"top{i}_hits":m[f"top{i}_hits"] for i in (1,2,3)},**{f"baseline_top{i}_hits":m["baseline"][f"top{i}_hits"] for i in (1,2,3)},**{f"net_top{i}":m[f"net_top{i}"] for i in (1,2,3)}}
    return {"n":m["n"],**{f"top{i}_hits":m[f"top{i}_hits"] for i in (1,2,3,5)},**{f"baseline_top{i}_hits":m["baseline"][f"top{i}_hits"] for i in (1,2,3,5)},**{f"net_top{i}":m[f"net_top{i}"] for i in (1,2,3,5)}}

def main():
    if os.getenv("HH520_COLLECTION1_AUDIT_OFFLINE_ONLY")!="1":
        raise SystemExit("offline-only guard missing")
    collection=json.loads(Path("_collection1_profiles.json").read_text(encoding="utf-8"))
    first=json.loads(Path("_collection1_ablation.json").read_text(encoding="utf-8"))
    matches=base.load_matches()
    rows,gate=base.quality_rows(matches,collection)
    selection=[r for r in rows if r["date"]<="2026-09-14"]
    holdout=[r for r in rows if r["date"]>="2026-09-15"]

    audit={}
    for kind in ("ft","htft","score"):
        enriched=[]
        for i,c in enumerate(first[kind]["all_candidates"]):
            candidate={"groups":tuple(c["groups"]),"params":tuple(c["params"])}
            h=base.final_eval(selection,holdout,kind,candidate)
            rec={k:v for k,v in c.items() if k!="fold_nets"}
            rec["holdout"]=compact_holdout(h,kind)
            if kind=="ft":
                rec["cv_safe"]=c["min_primary"]>=0 and c["total_primary"]>0
                rec["cross_window_strict"]=rec["cv_safe"] and h["net_top1"]>=0
            elif kind=="htft":
                rec["cv_safe"]=c["min_primary"]>=0 and c.get("min_top1",0)>=0 and c.get("min_top3",0)>=0 and c["total_primary"]>0
                rec["cross_window_strict"]=rec["cv_safe"] and h["net_top1"]>=0 and h["net_top2"]>=0 and h["net_top3"]>=0
                rec["cross_window_top2"]=c["min_primary"]>=0 and c["total_primary"]>0 and h["net_top2"]>0
            else:
                rec["cv_safe"]=c["min_primary"]>=0 and c.get("min_top1",0)>=0 and c["total_primary"]>0
                rec["cross_window_strict"]=rec["cv_safe"] and h["net_top1"]>=0 and h["net_top2"]>0 and h["net_top3"]>=0 and h["net_top5"]>=0
                rec["cross_window_top2"]=rec["cv_safe"] and h["net_top2"]>0
            enriched.append(rec)

        strict=[x for x in enriched if x.get("cross_window_strict")]
        if kind=="ft":
            ranked=sorted(strict,key=lambda x:(x["holdout"]["net_top1"],x["total_primary"],x["min_primary"]),reverse=True)
            secondary=[]
        elif kind=="htft":
            ranked=sorted(strict,key=lambda x:(x["holdout"]["net_top2"],x["holdout"]["net_top1"],x["holdout"]["net_top3"],x["total_primary"]),reverse=True)
            secondary=sorted([x for x in enriched if x.get("cross_window_top2")],key=lambda x:(x["holdout"]["net_top2"],x["total_primary"],x["holdout"]["net_top1"]),reverse=True)
        else:
            ranked=sorted(strict,key=lambda x:(x["holdout"]["net_top2"],x["holdout"]["net_top1"],x["holdout"]["net_top3"],x["total_primary"]),reverse=True)
            secondary=sorted([x for x in enriched if x.get("cross_window_top2")],key=lambda x:(x["holdout"]["net_top2"],x["holdout"]["net_top1"],x["total_primary"]),reverse=True)

        per_group={}
        for g in base.GROUP_NAMES:
            exact=[x for x in enriched if tuple(x["groups"])==(g,)]
            if not exact:continue
            if kind=="ft":
                exact=sorted(exact,key=lambda x:(x["holdout"]["net_top1"],x["total_primary"]),reverse=True)
            elif kind=="htft":
                exact=sorted(exact,key=lambda x:(x["holdout"]["net_top2"],x["holdout"]["net_top1"],x["total_primary"]),reverse=True)
            else:
                exact=sorted(exact,key=lambda x:(x["holdout"]["net_top2"],x["holdout"]["net_top1"],x["total_primary"]),reverse=True)
            per_group[g]=exact[0]

        audit[kind]={
          "candidate_count":len(enriched),
          "cv_safe_count":sum(1 for x in enriched if x["cv_safe"]),
          "cross_window_strict_count":len(strict),
          "cross_window_top2_count":sum(1 for x in enriched if x.get("cross_window_top2")),
          "best_cross_window_strict":ranked[0] if ranked else None,
          "top10_cross_window_strict":ranked[:10],
          "best_cross_window_top2":secondary[0] if secondary else None,
          "best_single_group_by_holdout":per_group,
        }

    # Core field coverage among the 145 mapped profiles, separate from match gate.
    core_keys=sorted({k for p in (collection.get("profiles") or {}).values() for k in ((p or {}).get("core_stats") or {})})
    pav={}
    profiles=list((collection.get("profiles") or {}).values())
    for k in core_keys:
        present=0
        for p in profiles:
            v=((p or {}).get("core_stats") or {}).get(k) or {}
            if any(v.get(side) is not None for side in ("overall","home","away")):present+=1
        pav[k]={"present":present,"coverage":present/len(profiles) if profiles else 0}

    out={
      "mode":"RETROSPECTIVE_COLLECTION1_ALL_CANDIDATE_HOLDOUT_AUDIT",
      "source_summary":collection.get("summary"),
      "quality_gate":gate,"selection_n":len(selection),"holdout_n":len(holdout),
      "profile_field_availability":pav,
      "warning":"Holdout audit evaluates all already-tested candidates on Sep15-20 only for robustness diagnostics. It must not be treated as a fresh selection set; snapshot is Sep25 and is not point-in-time.",
      **audit,
      "promotion_status":"RESEARCH_ONLY_NOT_PROMOTED_AUTOMATICALLY",
    }
    Path("_collection1_holdout_audit.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
      "source_summary":out["source_summary"],"quality_gate":gate,"selection_n":len(selection),"holdout_n":len(holdout),
      "profile_field_availability":pav,
      "ft":{k:out["ft"][k] for k in ("candidate_count","cv_safe_count","cross_window_strict_count","best_cross_window_strict","best_single_group_by_holdout")},
      "htft":{k:out["htft"][k] for k in ("candidate_count","cv_safe_count","cross_window_strict_count","cross_window_top2_count","best_cross_window_strict","best_cross_window_top2","best_single_group_by_holdout")},
      "score":{k:out["score"][k] for k in ("candidate_count","cv_safe_count","cross_window_strict_count","cross_window_top2_count","best_cross_window_strict","best_cross_window_top2","best_single_group_by_holdout")},
    },ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
