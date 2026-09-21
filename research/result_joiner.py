"""Join pre-match research data with isolated result labels.

HH520 match_id restarts every date, therefore the canonical join key is
(date, match_id). Result labels remain Research-only.
"""


def _key(row):
    day = str(row.get("date") or "").strip()
    match_id = str(row.get("match_id") or "").strip()
    return (day, match_id) if day and match_id else None


def join_results(prematch_records, result_labels):
    labels = {_key(x): x for x in result_labels if _key(x)}
    joined = []
    for record in prematch_records:
        item = dict(record)
        label = labels.get(_key(record))
        if label:
            item["result_label"] = {
                "actual_score": label.get("actual_score") or label.get("full_score"),
                "actual_half_score": label.get("actual_half_score") or label.get("half_score"),
                "actual_outcome": label.get("actual_outcome") or label.get("result"),
                "actual_total_goals": label.get("actual_total_goals") if label.get("actual_total_goals") is not None else label.get("goals"),
                # Compatibility aliases
                "full_score": label.get("actual_score") or label.get("full_score"),
                "half_score": label.get("actual_half_score") or label.get("half_score"),
                "result": label.get("actual_outcome") or label.get("result"),
                "goals": label.get("actual_total_goals") if label.get("actual_total_goals") is not None else label.get("goals"),
            }
            item["label_status"] = "MATCHED"
        else:
            item["label_status"] = "UNKNOWN"
        joined.append(item)
    return joined
