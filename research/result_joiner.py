"""Join pre-match research data with external result labels.

Result labels stay separate from prediction features.
"""


def join_results(prematch_records, result_labels):
    labels = {str(x.get("match_id")): x for x in result_labels if x.get("match_id")}
    joined = []
    for record in prematch_records:
        item = dict(record)
        label = labels.get(str(record.get("match_id")))
        if label:
            item["result_label"] = {
                "final_score": label.get("final_score"),
                "half_score": label.get("half_score"),
                "result": label.get("result"),
                "goals": label.get("goals"),
            }
            item["label_status"] = "MATCHED"
        else:
            item["label_status"] = "UNKNOWN"
        joined.append(item)
    return joined
