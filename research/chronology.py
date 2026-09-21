"""Canonical HH520 Research chronology.

Historical availability begins on 2026-08-01.
The chronology keeps discovery, historical shadow validation, and forward
validation separated to avoid leakage.
"""

HISTORY_START = "2026-08-01"

DISCOVERY_START = "2026-08-01"
DISCOVERY_END = "2026-08-31"

HISTORICAL_SHADOW_START = "2026-09-01"
HISTORICAL_SHADOW_END = "2026-09-20"

FORWARD_START = "2026-09-21"


def classify_window(start, end):
    if start >= DISCOVERY_START and end <= DISCOVERY_END:
        return "DISCOVERY"
    if start >= HISTORICAL_SHADOW_START and end <= HISTORICAL_SHADOW_END:
        return "HISTORICAL_SHADOW"
    if start >= FORWARD_START:
        return "FORWARD"
    return "MIXED"


def canonical_timeline():
    return {
        "history_start": HISTORY_START,
        "discovery_window": {"from": DISCOVERY_START, "to": DISCOVERY_END},
        "historical_shadow_window": {
            "from": HISTORICAL_SHADOW_START,
            "to": HISTORICAL_SHADOW_END,
        },
        "forward_window": {"from": FORWARD_START, "to": None},
        "policy": {
            "discovery_rules_frozen_before_shadow": True,
            "historical_shadow_must_not_regenerate_rules": True,
            "forward_validation_after_historical_shadow": True,
            "stable_access": "FORBIDDEN",
        },
    }
