"""Research-only half time result adapter.

Converts external verified half-time/full-time records into labels.
Never writes Stable data.
"""

from .half_time_collector import build_half_time_label, build_htft


def normalize_half_time_record(record, source="external_half_time_source"):
    """Create a normalized research half-time label."""
    label = build_half_time_label(record, source=source)
    label["htft"] = build_htft(
        record.get("half_score"),
        record.get("full_score"),
    )
    label["label_type"] = "HALF_TIME_RESULT"
    return label


def validate_half_time_record(record):
    """Require both half and full scores before accepting a label."""
    return bool(record.get("half_score") and record.get("full_score"))
