"""Match sanitized Research records with isolated result labels.

Primary key: date + match_id.
Fallbacks: normalized date + teams, then unique normalized team pair.
"""

def _norm(value):
    return "".join(str(value or "").strip().lower().split())


def _norm_date(value):
    return str(value or "").strip()[:10]


def _norm_match_id(value):
    raw = str(value or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    return str(int(digits)) if digits else ""


def _id_key(item):
    day = _norm_date(item.get("date"))
    match_id = _norm_match_id(item.get("match_id"))
    return (day, match_id) if day and match_id else None


def _team_date_key(item):
    day = _norm_date(item.get("date"))
    home = _norm(item.get("home_team") or item.get("home"))
    away = _norm(item.get("away_team") or item.get("away"))
    return (day, home, away) if day and home and away else None


def _team_key(item):
    home = _norm(item.get("home_team") or item.get("home"))
    away = _norm(item.get("away_team") or item.get("away"))
    return (home, away) if home and away else None


def match_results(records, labels):
    by_id = {}
    by_team_date = {}
    team_candidates = {}

    for label in labels:
        key = _id_key(label)
        if key:
            by_id[key] = label

        key = _team_date_key(label)
        if key:
            by_team_date[key] = label

        key = _team_key(label)
        if key:
            team_candidates.setdefault(key, []).append(label)

    output = []
    for record in records:
        label = None
        method = None

        key = _id_key(record)
        if key:
            label = by_id.get(key)
            if label is not None:
                method = "DATE_MATCH_ID"

        if label is None:
            key = _team_date_key(record)
            if key:
                label = by_team_date.get(key)
                if label is not None:
                    method = "DATE_TEAMS"

        if label is None:
            key = _team_key(record)
            candidates = team_candidates.get(key, []) if key else []
            if len(candidates) == 1:
                label = candidates[0]
                method = "UNIQUE_TEAMS"

        item = dict(record)
        item["label_status"] = "MATCHED" if label else "UNKNOWN"
        item["label_match_method"] = method
        if label:
            item["result_label"] = dict(label)
        output.append(item)

    return output
