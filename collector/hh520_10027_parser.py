"""Header-driven parser for HH520 10027s comprehensive pages."""
import math
import re
from typing import Dict, List


def _cells(line):
    if not str(line).lstrip().startswith("|"):
        return []
    return [x.strip().replace("<br>", " ") for x in str(line).strip().strip("|").split("|")]


def _norm_header(value):
    return re.sub(r"\s+", "", str(value or "")).strip()


def _num(value):
    raw = str(value or "").replace("%", "").strip()
    if raw in {"", "-", "--", "—"}:
        return None
    try:
        parsed = float(raw)
    except Exception:
        return None
    return parsed if math.isfinite(parsed) else None


def _match_id(value):
    m = re.search(r"(\d+)", str(value or ""))
    return str(int(m.group(1))) if m else None


def _score(value):
    m = re.search(r"(\d+)\s*[-:：]\s*(\d+)", str(value or ""))
    return f"{int(m.group(1))}-{int(m.group(2))}" if m else None


def _score_options(value):
    out = []
    for home, away in re.findall(r"(\d+)\s*[-:：]\s*(\d+)", str(value or "")):
        item = {"home": int(home), "away": int(away)}
        if item not in out:
            out.append(item)
    return out


def _probability(value):
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(value or "").replace("%", ""))]
    if len(nums) < 3:
        return None
    nums = nums[:3]
    total = sum(nums)
    if total <= 0:
        return None
    return {"home": nums[0] / total, "draw": nums[1] / total, "away": nums[2] / total}


def _split_pair(value):
    raw = str(value or "").strip()
    parts = re.split(r"\s*(?:vs|VS|v|V|—|–|-)\s*", raw, maxsplit=1)
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0].strip(), parts[1].strip()
    return "", ""


def _alias_index(headers):
    aliases = {
        "match_id": ["场次", "编号", "赛事编号"],
        "date": ["日期", "比赛日期"],
        "league": ["联赛", "赛事"],
        "kickoff": ["时间", "开赛时间", "比赛时间"],
        "home_team": ["主队", "主队名称"],
        "away_team": ["客队", "客队名称"],
        "matchup": ["对阵", "比赛"],
        "full_score": ["比分", "比赛结果", "全场比分", "赛果"],
        "half_score": ["半场比分", "半场", "半场赛果"],
        "home_odds": ["胜", "主胜", "主胜赔率"],
        "draw_odds": ["平", "平局", "平赔率"],
        "away_odds": ["负", "客胜", "客胜赔率"],
        "ev": ["EV", "价值", "期望值"],
        "kelly": ["凯利比例", "凯利"],
        "signal": ["是否下注", "建议下注", "下注"],
        "probability": ["融合真实概率", "真实概率", "概率"],
        "single": ["单选", "胜平负预测", "预测"],
        "htft": ["半全场", "半全场预测"],
        "scores": ["最可能比分", "比分预测", "预测比分"],
        "total_goals": ["总进球", "总进球预测", "进球数"],
        "attack": ["进攻"],
        "defense": ["防守"],
        "head_to_head": ["交锋"],
        "form": ["状态"],
    }
    normalized = [_norm_header(x) for x in headers]
    result = {}
    for key, names in aliases.items():
        for name in names:
            target = _norm_header(name)
            if target in normalized:
                result[key] = normalized.index(target)
                break
    return result


def _get(row, indexes, key):
    pos = indexes.get(key)
    if pos is None or pos >= len(row):
        return ""
    return row[pos].strip()


def parse_10027s_markdown(markdown: str) -> List[Dict]:
    lines = [x.strip() for x in str(markdown or "").splitlines() if x.strip()]
    result = []
    seen = set()

    i = 0
    while i < len(lines):
        header = _cells(lines[i])
        if not header:
            i += 1
            continue

        indexes = _alias_index(header)
        has_identity = "match_id" in indexes or "matchup" in indexes or (
            "home_team" in indexes and "away_team" in indexes
        )
        if not has_identity:
            i += 1
            continue

        j = i + 1
        while j < len(lines):
            row = _cells(lines[j])
            if not row:
                break
            if row and all(re.fullmatch(r"[:\- ]*", cell or "") for cell in row):
                j += 1
                continue

            mid = _match_id(_get(row, indexes, "match_id"))
            home = _get(row, indexes, "home_team")
            away = _get(row, indexes, "away_team")
            if (not home or not away) and "matchup" in indexes:
                pair_home, pair_away = _split_pair(_get(row, indexes, "matchup"))
                home = home or pair_home
                away = away or pair_away

            if not mid and not (home and away):
                j += 1
                continue

            full_score = _score(_get(row, indexes, "full_score"))
            half_score = _score(_get(row, indexes, "half_score"))
            scores_raw = _get(row, indexes, "scores")
            key = (mid or "", home, away, _get(row, indexes, "date"))
            if key in seen:
                j += 1
                continue
            seen.add(key)

            item = {
                "match_id": mid or str(len(result) + 1),
                "date": _get(row, indexes, "date"),
                "home_team": home,
                "away_team": away,
                "league": _get(row, indexes, "league"),
                "kickoff": _get(row, indexes, "kickoff"),
                "result": full_score or _get(row, indexes, "full_score"),
                "half_score": half_score,
                "market": {
                    "home_odds": _num(_get(row, indexes, "home_odds")),
                    "draw_odds": _num(_get(row, indexes, "draw_odds")),
                    "away_odds": _num(_get(row, indexes, "away_odds")),
                },
                "page_probability": _probability(_get(row, indexes, "probability")),
                "value": {
                    "ev": _num(_get(row, indexes, "ev")),
                    "kelly": _num(_get(row, indexes, "kelly")),
                    "signal": _get(row, indexes, "signal"),
                },
                "team_dna": {
                    "attack": _get(row, indexes, "attack"),
                    "defense": _get(row, indexes, "defense"),
                    "head_to_head": _get(row, indexes, "head_to_head"),
                    "form": _get(row, indexes, "form"),
                },
                "page_prediction": {
                    "single": _get(row, indexes, "single") or None,
                    "htft": _get(row, indexes, "htft") or None,
                    "scores": scores_raw,
                    "score_options": _score_options(scores_raw),
                    "total_goals": _get(row, indexes, "total_goals") or None,
                },
            }
            result.append(item)
            j += 1

        i = max(i + 1, j)

    if not result:
        raise ValueError("10027s 页面未解析到比赛数据")
    return result
