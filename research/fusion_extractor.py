"""Research-only extractor for HH520 10023s fusion predictions.

Reads raw markdown directly so Research does not depend on Stable parser
matching/column assumptions. Never writes to Stable inputs.
"""
import re

_FUSION = ["排名", "场次", "对阵", "比赛结果", "官方赔率", "平赔率", "融合平值", "优势差", "平局综合分", "优势方", "单选", "融合真实概率", "结构", "一致", "规律", "评分", "评级", "风险", "半全场", "最可能比分", "总进球", "盘口", "忽略"]


def _cells(line):
    if not str(line).lstrip().startswith("|"):
        return []
    return [x.strip().replace("<br>", " ") for x in str(line).strip().strip("|").split("|")]


def _norm_team(value):
    return re.sub(r"\s+", "", str(value or "").strip()).lower()


def _norm_id(value):
    m = re.search(r"(\d+)", str(value or ""))
    return int(m.group(1)) if m else None


def _pair(text):
    raw = str(text or "").strip()
    parts = re.split(r"\s+vs\s+|\s+VS\s+|\s+v\s+|\s+-\s+", raw, maxsplit=1)
    if len(parts) != 2:
        return None
    home, away = _norm_team(parts[0]), _norm_team(parts[1])
    return (home, away) if home and away else None


def _probability(raw):
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(raw or ""))]
    if len(nums) < 3:
        return None
    nums = nums[:3]
    total = sum(nums)
    if total <= 0:
        return None
    return {"home": nums[0] / total, "draw": nums[1] / total, "away": nums[2] / total}


def extract_fusion_predictions(markdown):
    lines = [x.strip() for x in str(markdown or "").splitlines() if x.strip()]
    headers = []
    for i, line in enumerate(lines):
        cells = _cells(line)
        if cells[:len(_FUSION)] == _FUSION:
            headers.append((i, {name: pos for pos, name in enumerate(cells)}))

    by_id = {}
    by_pair = {}
    rows_seen = 0
    rows_with_score = 0
    rows_with_goal = 0
    raw_goal_values = []

    for header_index, index in headers:
        for line in lines[header_index + 1:]:
            cells = _cells(line)
            if not cells:
                continue
            # Stop at the next table header.
            if cells[:len(_FUSION)] == _FUSION:
                break
            if len(cells) <= max(index.get("场次", 1), index.get("对阵", 2)):
                continue

            match_id = _norm_id(cells[index["场次"]])
            pair = _pair(cells[index["对阵"]])
            if match_id is None and pair is None:
                continue

            def field(name):
                pos = index.get(name)
                return cells[pos].strip() if pos is not None and pos < len(cells) else ""

            score = field("最可能比分")
            goals = field("总进球")
            pred = {
                "single": field("单选") or None,
                "htft": field("半全场") or None,
                "scores": score,
                "total_goals": goals or None,
                "page_probability": _probability(field("融合真实概率")),
            }

            rows_seen += 1
            if score:
                rows_with_score += 1
            if goals:
                rows_with_goal += 1
                if goals not in raw_goal_values and len(raw_goal_values) < 20:
                    raw_goal_values.append(goals)

            if match_id is not None:
                by_id[match_id] = pred
            if pair is not None:
                by_pair[pair] = pred

    return {
        "by_id": by_id,
        "by_pair": by_pair,
        "debug": {
            "fusion_headers": len(headers),
            "fusion_rows_seen": rows_seen,
            "rows_with_score": rows_with_score,
            "rows_with_total_goals": rows_with_goal,
            "raw_total_goals_examples": raw_goal_values,
        },
    }


def attach_research_predictions(matches, markdown):
    extracted = extract_fusion_predictions(markdown)
    attached = 0
    score_available = 0
    goal_available = 0

    output = []
    for match in matches:
        item = dict(match)
        mid = _norm_id(item.get("match_id"))
        pair = (_norm_team(item.get("home_team")), _norm_team(item.get("away_team")))

        pred = None
        if mid is not None:
            pred = extracted["by_id"].get(mid)
        if pred is None and all(pair):
            pred = extracted["by_pair"].get(pair)

        if pred is not None:
            attached += 1
            page_prediction = {
                "single": pred.get("single"),
                "htft": pred.get("htft"),
                "scores": pred.get("scores") or "",
                "total_goals": pred.get("total_goals"),
            }
            item["research_source_prediction"] = {
                "page_probability": pred.get("page_probability"),
                "page_prediction": page_prediction,
            }
            if page_prediction["scores"]:
                score_available += 1
            if page_prediction["total_goals"]:
                goal_available += 1

        output.append(item)

    debug = dict(extracted["debug"])
    debug.update({
        "matches_total": len(matches),
        "prediction_attached": attached,
        "score_available": score_available,
        "total_goals_available": goal_available,
        "prediction_missing": max(0, len(matches) - attached),
    })
    return output, debug
