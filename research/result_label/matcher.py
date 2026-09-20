"""Match research records with independent result labels."""


def match_results(records, labels):
    index = {x.get("match_id"): x for x in labels if x.get("match_id")}
    output = []
    for record in records:
        label = index.get(record.get("match_id"))
        item = dict(record)
        item["label_status"] = "MATCHED" if label else "UNKNOWN"
        if label:
            item["result_label"] = label
        output.append(item)
    return output
