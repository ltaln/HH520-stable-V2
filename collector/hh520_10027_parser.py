"""Robust parser for HH520 10027s comprehensive pages.

Research-facing parser only. It uses tolerant header matching and merges
multiple table sections for the same match so prediction/result fields can
live in different blocks.
"""
import math
import re
from typing import Dict, List


def _cells(line):
    if not str(line).lstrip().startswith("|"):
        return []
    return [x.strip().replace("<br>", " ") for x in str(line).strip().strip("|").split("|")]


def _norm_header(value):
    text = re.sub(r"\s+", "", str(value or "")).strip().lower()
    text = text.replace("（", "(").replace("）", ")")
    return text


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
    parts = re.split(r"\s*(?:vs|VS|v|V|—|–)\s*", raw, maxsplit=1)
    if len(parts) != 2:
        parts = re.split(r"\s+-\s+", raw, maxsplit=1)
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0].strip(), parts[1].strip()
    return "", ""


ALIASES = {
    "match_id": ["场次", "编号", "赛事编号", "序号"],
    "date": ["日期", "比赛日期", "riqi"],
    "league": ["联赛", "赛事", "联赛名称"],
    "kickoff": ["时间", "开赛时间", "比赛时间", "开球时间"],
    "home_team": ["主队", "主队名称"],
    "away_team": ["客队", "客队名称"],
    "matchup": ["对阵", "比赛对阵", "主客队"],
    "full_score": ["全场比分", "最终比分", "比赛结果", "赛果", "实际比分", "完场比分", "比分"],
    "half_score": ["半场比分", "上半场比分", "半场赛果", "半场结果", "半场"],
    "home_odds": ["主胜赔率", "主胜", "胜"],
    "draw_odds": ["平局赔率", "平赔率", "平局", "平"],
    "away_odds": ["客胜赔率", "客胜", "负"],
    "ev": ["ev", "期望值", "价值"],
    "kelly": ["凯利比例", "凯利"],
    "signal": ["是否下注", "建议下注", "下注建议", "建议"],
    "probability": ["融合真实概率", "真实概率", "胜平负概率", "概率"],
    "single": ["单选", "胜平负预测", "胜平负推荐", "预测方向", "推荐方向"],
    "htft": ["半全场预测", "半全场推荐", "半全场"],
    "scores": ["最可能比分", "预测比分", "比分预测", "推荐比分", "比分推荐", "参考比分"],
    "total_goals": ["总进球预测", "总进球推荐", "预测总进球", "总进球", "进球数", "进球数预测"],
    "attack": ["进攻", "进攻值"],
    "defense": ["防守", "防守值"],
    "head_to_head": ["交锋", "交锋值"],
    "form": ["状态", "状态值"],
}


def _header_matches(header, alias):
    h = _norm_header(header)
    a = _norm_header(alias)
    if not h or not a:
        return False
    if h == a:
        return True
    # Prediction/result fields often carry prefixes/suffixes on 10027s.
    return a in h or h in a


def _alias_index(headers):
    result = {}
    for key, names in ALIASES.items():
        for pos, header in enumerate(headers):
            if any(_header_matches(header, name) for name in names):
                result[key] = pos
                break
    return result


def _get(row, indexes, key):
    pos = indexes.get(key)
    if pos is None or pos >= len(row):
        return ""
    return row[pos].strip()


def _looks_like_separator(row):
    if not row:
        return True
    return all(re.fullmatch(r"[:\- ]*", cell or "") for cell in row)


def _prediction_score_value(row, headers, indexes):
    direct = _get(row, indexes, "scores")
    if _score_options(direct):
        return direct

    # Do not steal actual/full-time score columns.
    for pos, value in enumerate(row):
        if not _score_options(value):
            continue
        header = _norm_header(headers[pos]) if pos < len(headers) else ""
        if any(token in header for token in ("预测", "推荐", "最可能", "参考")) and "半场" not in header:
            return value
    return ""


def _total_goals_value(row, headers, indexes):
    direct = _get(row, indexes, "total_goals")
    if direct and direct not in {"-", "--", "—"}:
        return direct

    for pos, value in enumerate(row):
        raw = str(value or "").strip()
        if not raw or raw in {"-", "--", "—"}:
            continue
        header = _norm_header(headers[pos]) if pos < len(headers) else ""
        if ("总进球" in header or "进球数" in header) and any(
            token in header for token in ("预测", "推荐", "参考", "总进球", "进球数")
        ):
            return raw
    return ""


def _htft_value(row, headers, indexes):
    direct = _get(row, indexes, "htft")
    if direct and direct not in {"-", "--", "—"}:
        return direct
    for pos, value in enumerate(row):
        raw = str(value or "").strip()
        header = _norm_header(headers[pos]) if pos < len(headers) else ""
        if raw and "半全场" in header and any(token in header for token in ("预测", "推荐", "半全场")):
            return raw
    return ""


def _merge(current, item):
    for field in ("date", "home_team", "away_team", "league", "kickoff", "result", "half_score"):
        if not current.get(field) and item.get(field):
            current[field] = item[field]

    for section in ("market", "value", "team_dna", "page_prediction"):
        current.setdefault(section, {})
        for field, value in (item.get(section) or {}).items():
            if current[section].get(field) in (None, "", [], {}) and value not in (None, "", [], {}):
                current[section][field] = value

    if current.get("page_probability") is None and item.get("page_probability") is not None:
        current["page_probability"] = item["page_probability"]


def parse_10027s_markdown(markdown: str) -> List[Dict]:
    lines = [x.strip() for x in str(markdown or "").splitlines() if x.strip()]
    records = {}
    order = []
    fallback_id = 0

    i = 0
    while i < len(lines):
        headers = _cells(lines[i])
        if not headers:
            i += 1
            continue

        indexes = _alias_index(headers)
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

            # A new recognizable table header starts another section.
            next_indexes = _alias_index(row)
            if next_indexes and (
                "match_id" in next_indexes
                or "matchup" in next_indexes
                or ("home_team" in next_indexes and "away_team" in next_indexes)
            ):
                break

            if _looks_like_separator(row):
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

            full_raw = _get(row, indexes, "full_score")
            half_raw = _get(row, indexes, "half_score")
            full_score = _score(full_raw)
            half_score = _score(half_raw)

            scores_raw = _prediction_score_value(row, headers, indexes)
            total_goals_raw = _total_goals_value(row, headers, indexes)
            htft_raw = _htft_value(row, headers, indexes)

            if mid:
                key = ("id", mid)
            else:
                key = ("teams", home.strip().lower(), away.strip().lower())

            fallback_id += 1
            item = {
                "match_id": mid or str(fallback_id),
                "date": _get(row, indexes, "date"),
                "home_team": home,
                "away_team": away,
                "league": _get(row, indexes, "league"),
                "kickoff": _get(row, indexes, "kickoff"),
                "result": full_score or full_raw,
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
                    "htft": htft_raw or None,
                    "scores": scores_raw,
                    "score_options": _score_options(scores_raw),
                    "total_goals": total_goals_raw or None,
                },
            }

            if key not in records:
                records[key] = item
                order.append(key)
            else:
                _merge(records[key], item)

            j += 1

        i = j if j > i else i + 1

    result = [records[key] for key in order]
    if not result:
        raise ValueError("10027s 页面未解析到比赛数据")
    return result
