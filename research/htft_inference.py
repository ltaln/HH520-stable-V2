"""Research-only HT/FT inference from pre-match Poisson score model.

Preserves actionable raw HH520 HT/FT predictions. When the raw field is absent
or non-actionable (for example "不建议"), derives the most likely half-time /
full-time outcome from the Research Poisson lambdas.

Never writes Stable inputs.
"""
import math
from copy import deepcopy


OUTCOMES = ("HOME", "DRAW", "AWAY")
HALF_SHARE = 0.45
MAX_GOALS_HALF = 6
MAX_GOALS_SECOND = 7


def _outcome(home, away):
    if home > away:
        return "HOME"
    if home < away:
        return "AWAY"
    return "DRAW"


def _poisson_probs(lmbda, max_goals):
    probs = [math.exp(-lmbda)]
    for k in range(1, max_goals + 1):
        probs.append(probs[-1] * lmbda / k)
    return probs


def _normalize_raw_htft(value):
    raw = str(value or "").strip()
    if not raw:
        return None

    upper = raw.upper().replace("-", "_").replace("/", "_").replace(" ", "")
    if "_" in upper:
        parts = [x for x in upper.split("_") if x]
        if len(parts) >= 2 and parts[0] in OUTCOMES and parts[1] in OUTCOMES:
            return f"{parts[0]}_{parts[1]}"

    token_map = {
        "主": "HOME", "胜": "HOME",
        "平": "DRAW",
        "客": "AWAY", "负": "AWAY",
    }
    chars = [c for c in raw if c in token_map]
    if len(chars) >= 2:
        return f"{token_map[chars[0]]}_{token_map[chars[1]]}"
    return None


def _display(htft):
    mapping = {"HOME": "胜", "DRAW": "平", "AWAY": "负"}
    first, second = htft.split("_", 1)
    return mapping[first] + mapping[second]


def infer_htft_from_lambdas(home_lambda, away_lambda):
    try:
        lh = float(home_lambda)
        la = float(away_lambda)
    except (TypeError, ValueError):
        return None
    if lh <= 0 or la <= 0:
        return None

    h1 = _poisson_probs(lh * HALF_SHARE, MAX_GOALS_HALF)
    a1 = _poisson_probs(la * HALF_SHARE, MAX_GOALS_HALF)
    h2 = _poisson_probs(lh * (1.0 - HALF_SHARE), MAX_GOALS_SECOND)
    a2 = _poisson_probs(la * (1.0 - HALF_SHARE), MAX_GOALS_SECOND)

    joint = {f"{x}_{y}": 0.0 for x in OUTCOMES for y in OUTCOMES}

    for hh, phh in enumerate(h1):
        for ah, pah in enumerate(a1):
            half_outcome = _outcome(hh, ah)
            for hs, phs in enumerate(h2):
                for a_s, pas in enumerate(a2):
                    full_outcome = _outcome(hh + hs, ah + a_s)
                    joint[f"{half_outcome}_{full_outcome}"] += phh * pah * phs * pas

    total = sum(joint.values())
    if total <= 0:
        return None

    ranked = sorted(
        ((prob / total, key) for key, prob in joint.items()),
        reverse=True,
    )
    return {
        "primary": ranked[0][1],
        "primary_probability": ranked[0][0],
        "top2": [ranked[0][1], ranked[1][1]],
        "distribution": {key: prob for prob, key in ranked},
    }


def attach_research_htft_predictions(records):
    output = []
    for record in records:
        item = deepcopy(record)
        source = deepcopy(item.get("research_source_prediction") or {})
        page_prediction = deepcopy(source.get("page_prediction") or item.get("page_prediction") or {})

        raw_htft = page_prediction.get("htft")
        normalized = _normalize_raw_htft(raw_htft)

        # Preserve actionable source prediction.
        if normalized is not None:
            page_prediction["htft_normalized"] = normalized
            page_prediction.setdefault("htft_source", "HH520_RAW")
            source["page_prediction"] = page_prediction
            item["research_source_prediction"] = source
            output.append(item)
            continue

        model = source.get("research_score_model") or {}
        inferred = infer_htft_from_lambdas(
            model.get("home_lambda"),
            model.get("away_lambda"),
        )
        if inferred is not None:
            page_prediction["htft_raw"] = raw_htft
            page_prediction["htft"] = _display(inferred["primary"])
            page_prediction["htft_normalized"] = inferred["primary"]
            page_prediction["htft_top2"] = inferred["top2"]
            page_prediction["htft_source"] = "RESEARCH_DERIVED_POISSON"
            source["page_prediction"] = page_prediction
            source["research_htft_model"] = {
                "source": "RESEARCH_POISSON_HTFT",
                "half_share": HALF_SHARE,
                "primary": inferred["primary"],
                "primary_probability": round(inferred["primary_probability"], 8),
                "top2": inferred["top2"],
                "stable_access": "FORBIDDEN",
            }
            source["stable_access"] = "FORBIDDEN"
            item["research_source_prediction"] = source

        output.append(item)

    return output
