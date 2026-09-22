"""Load the frozen HH520 Stable V3.3 runtime artifact."""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

ARTIFACT_PATH = Path(__file__).resolve().parents[1] / "model_artifacts" / "HH520_Stable_V3_3.json"


@lru_cache(maxsize=1)
def load_model_artifact() -> dict:
    data = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    if data.get("version") != "HH520 Stable V3.3":
        raise RuntimeError("unexpected HH520 model artifact version")
    return data
