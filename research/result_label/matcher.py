"""Match sanitized research records with isolated result labels.

Multi-day HH520 match IDs repeat (1, 2, 3...), so date + match_id is the
primary key. Team/date fallback is used only when the ID key is unavailable.
"""


def _norm(value):
    return " ".join(str(value or "").strip().lower().split())


def _id_key(item):
    day = _norm(item.get("date"))
    match_id = _norm(item.get("match_id"))
    return (day, match_id) if day and match_id else None


def _team_key(item):
    day = _norm(item.get("date"))
    home = _norm(item.get("home_team") or item.get("home"))
    away = _norm(item.get("away_team") or item.get("away"))
    return (day, home, away) if day and home and away else None


def match_results(records, labels):
    by_id = {}
    by_team = {}
    for label in labels:
        key = _id_key(label)
        if key:
            by_id[key] = label
        key = _team_key(label)
        if key:
            by_team[key] = label

    output = []
    for record in records:
        label = None
        key = _id_key(record)
        if key:
            label = by_id.get(key)
        if label is None:
            key = _team_key(record)
            if key:
                label = by_team.get(key)

        item = dict(record)
        item["label_status"] = "MATCHED" if label else "UNKNOWN"
        if label:
            item["result_label"] = dict(label)
        output.append(item)
    return output
