"""Research-only score inference from pre-match 1X2 probabilities.

This module never writes Stable inputs. It derives a simple independent-Poisson
score distribution by fitting home/away expected goals to pre-match W/D/L
probabilities. Source priority:
1) page_probability (fusion probability from 10027s)
2) de-vigged official 1X2 odds

Outputs are explicitly marked RESEARCH_DERIVED and must not be presented as
raw HH520 score predictions.
"""
import math
from copy import deepcopy


MAX_GOALS = 8
LAMBDA_MIN = 0.20
LAMBDA_MAX = 4.50
LAMBDA_STEP = 0.10


def _finite_positive(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or x <= 0:
        return None
    return x


def _normalize_probs(home, draw, away):
    vals = [_finite_positive(home), _finite_positive(draw), _finite_positive(away)]
    if any(v is None for v in vals):
        return None
    total = sum(vals)
    if total <= 0:
        return None
    return {"home": vals[0] / total, "draw": vals[1] / total, "away": vals[2] / total}


def _market_probability(record):
    market = record.get("market") or {}
    odds = [
        _finite_positive(market.get("home_odds")),
        _finite_positive(market.get("draw_odds")),
        _finite_positive(market.get("away_odds")),
    ]
    if any(v is None for v in odds):
        return None
    implied = [1.0 / v for v in odds]
    total = sum(implied)
    if total <= 0:
        return None
    return {"home": implied[0] / total, "draw": implied[1] / total, "away": implied[2] / total}


def _target_probability(record):
    page = record.get("page_probability") or {}
    p = _normalize_probs(page.get("home"), page.get("draw"), page.get("away"))
    if p is not None:
        return p, "PAGE_PROBABILITY"
    p = _market_probability(record)
    if p is not None:
        return p, "DEVIG_1X2_ODDS"
    return None, None


def _poisson_probs(lmbda):
    probs = []
    p0 = math.exp(-lmbda)
    probs.append(p0)
    for k in range(1, MAX_GOALS + 1):
        probs.append(probs[-1] * lmbda / k)
    return probs


def _wdl_and_scores(home_lambda, away_lambda):
    hp = _poisson_probs(home_lambda)
    ap = _poisson_probs(away_lambda)

    p_home = p_draw = p_away = 0.0
    scores = []
    for h, ph in enumerate(hp):
        for a, pa in enumerate(ap):
            prob = ph * pa
            scores.append((prob, h, a))
            if h > a:
                p_home += prob
            elif h == a:
                p_draw += prob
            else:
                p_away += prob

    total = p_home + p_draw + p_away
    if total <= 0:
        return None
    scores.sort(reverse=True)
    return {
        "home": p_home / total,
        "draw": p_draw / total,
        "away": p_away / total,
        "scores": scores,
    }


def _fit_lambdas(target):
    best = None
    steps = int(round((LAMBDA_MAX - LAMBDA_MIN) / LAMBDA_STEP))
    for i in range(steps + 1):
        lh = LAMBDA_MIN + i * LAMBDA_STEP
        for j in range(steps + 1):
            la = LAMBDA_MIN + j * LAMBDA_STEP
            model = _wdl_and_scores(lh, la)
            if model is None:
                continue
            error = (
                (model["home"] - target["home"]) ** 2
                + (model["draw"] - target["draw"]) ** 2
                + (model["away"] - target["away"]) ** 2
            )
            candidate = (error, lh, la, model)
            if best is None or candidate[0] < best[0]:
                best = candidate
    return best


def infer_score_prediction(record):
    target, probability_source = _target_probability(record)
    if target is None:
        return None

    fitted = _fit_lambdas(target)
    if fitted is None:
        return None

    error, home_lambda, away_lambda, model = fitted
    top_scores = []
    seen = set()
    for prob, home, away in model["scores"]:
        pair = (home, away)
        if pair in seen:
            continue
        seen.add(pair)
        top_scores.append({
            "home": home,
            "away": away,
            "probability": prob,
        })
        if len(top_scores) >= 2:
            break

    if not top_scores:
        return None

    predicted_total_goals = top_scores[0]["home"] + top_scores[0]["away"]
    return {
        "score_options": [{"home": x["home"], "away": x["away"]} for x in top_scores],
        "scores": " / ".join(f'{x["home"]}-{x["away"]}' for x in top_scores),
        "total_goals": str(predicted_total_goals),
        "research_score_model": {
            "source": "RESEARCH_POISSON_1X2",
            "probability_source": probability_source,
            "home_lambda": round(home_lambda, 3),
            "away_lambda": round(away_lambda, 3),
            "fit_error": round(error, 8),
            "top_scores": top_scores,
            "stable_access": "FORBIDDEN",
        },
    }


def attach_research_score_predictions(records):
    output = []
    for record in records:
        item = deepcopy(record)
        inferred = infer_score_prediction(item)
        if inferred is not None:
            source = deepcopy(item.get("research_source_prediction") or {})
            page_prediction = deepcopy(source.get("page_prediction") or item.get("page_prediction") or {})

            # Never overwrite explicit raw source predictions if they exist.
            if not page_prediction.get("score_options") and not page_prediction.get("scores"):
                page_prediction["score_options"] = inferred["score_options"]
                page_prediction["scores"] = inferred["scores"]
                page_prediction["score_source"] = "RESEARCH_DERIVED"

            if not page_prediction.get("total_goals"):
                page_prediction["total_goals"] = inferred["total_goals"]
                page_prediction["total_goals_source"] = "RESEARCH_DERIVED_FROM_SCORE"

            source["page_prediction"] = page_prediction
            source["page_probability"] = deepcopy(item.get("page_probability"))
            source["research_score_model"] = inferred["research_score_model"]
            source["stable_access"] = "FORBIDDEN"
            item["research_source_prediction"] = source
        output.append(item)
    return output
