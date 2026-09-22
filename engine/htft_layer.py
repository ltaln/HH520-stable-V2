"""Frozen conditional HTFT model for HH520 Stable V3.2."""
from __future__ import annotations
from .model_artifact import load_model_artifact

FT_MAP = {"home": "HOME", "draw": "DRAW", "away": "AWAY"}
ZH = {"HOME": "主", "DRAW": "平", "AWAY": "客"}


def htft_layer(probability: dict) -> dict:
    probs = probability.get("probabilities") or {}
    if not probability.get("valid") or len(probs) != 3:
        return {"valid": False, "model": "CONDITIONAL_HT_GIVEN_FT", "top": [], "distribution": []}

    artifact = load_model_artifact()
    matrix = artifact["htft"]["matrix"]
    rows = []
    for ft_key, p_ft in probs.items():
        ft = FT_MAP[ft_key]
        for ht in ("HOME", "DRAW", "AWAY"):
            p = float(p_ft) * float(matrix[ft][ht])
            rows.append({
                "selection": f"{ZH[ht]}/{ZH[ft]}",
                "ht": ht,
                "ft": ft,
                "probability": p,
            })

    rows.sort(key=lambda x: x["probability"], reverse=True)
    return {
        "valid": True,
        "model": artifact["htft"]["model"],
        "top": rows[:3],
        "distribution": rows,
    }
