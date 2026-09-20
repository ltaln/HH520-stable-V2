"""Historical pre-match sanitizer for Research Lab V1."""
from copy import deepcopy

_FORBIDDEN = {
    "actual", "outcome", "result", "score", "scores", "final_score", "half_score",
    "full_time", "half_time", "settlement", "events", "post_match",
    "match_result", "final_result", "winner",
}

def sanitize_record(record):
    if not isinstance(record, dict):
        raise ValueError("record must be an object")
    removed = []

    def clean_value(value):
        if isinstance(value, dict):
            clean = {}
            for key, nested in value.items():
                normalized = str(key).strip().lower()
                if normalized in _FORBIDDEN or normalized.startswith("post_"):
                    removed.append(key)
                    continue
                clean[key] = clean_value(nested)
            return clean
        if isinstance(value, list):
            return [clean_value(item) for item in value]
        return deepcopy(value)

    clean = clean_value(record)
    return clean, sorted(removed, key=str)

def sanitize_records(records):
    clean, audit = [], []
    for index, record in enumerate(records):
        item, removed = sanitize_record(record)
        clean.append(item)
        if removed:
            audit.append({"index": index, "removed_fields": removed})
    return clean, audit
