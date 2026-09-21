"""Parser for HH520 10027s comprehensive page.

Uses the actual 10027s page structure:
1) settlement/base table with match identity + HT/FT actual scores;
2) fusion summary tables with single/probability/HTFT prediction fields.
The two sections are merged by match_id.
"""
import math
import re
from typing import Dict, List


BASE_HEADER = [
    "日期", "场次", "联赛", "时间", "比分", "胜", "平", "负",
    "主队", "主控球率", "客控球率", "客队", "半场比分", "全场比分",
    "差值", "区间", "平滑p", "EV", "凯利比例", "建议下注", "是否下注",
]

FUSION_PREFIX = ["日期", "排名", "场次", "对阵", "比赛结果"]


def _cells(line):
    if not str(line).lstrip().startswith("|"):
        return []
    return [x.strip().replace("<br>", " ") for x in str(line).strip().strip("|").split("|")]


def _strip_md(value):
    return re.sub(r"\*\*", "", str(value or "")).strip()


def _num(value):
    raw = _strip_md(value).replace("%", "")
    if raw in {"", "-", "--", "—"}:
        return None
    try:
        v = float(raw)
    except Exception:
        return None
    return v if math.isfinite(v) else None


def _percent(value):
    """Parse percentage-like values to percentage points, e.g. 55% -> 55.0."""
    return _num(value)


def _clean_header(value):
    return re.sub(r"\s+", "", _strip_md(value).replace("\n", ""))


def _match_id(value):
    m = re.search(r"(\d+)", _strip_md(value))
    return str(int(m.group(1))) if m else None


def _score(value):
    m = re.search(r"(\d+)\s*[-:：]\s*(\d+)", _strip_md(value))
    return f"{int(m.group(1))}-{int(m.group(2))}" if m else None


def _score_options(value):
    out = []
    for home, away in re.findall(r"(\d+)\s*[-:：]\s*(\d+)", _strip_md(value)):
        item = {"home": int(home), "away": int(away)}
        if item not in out:
            out.append(item)
    return out


def _probability(value):
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", _strip_md(value).replace("%", ""))]
    if len(nums) < 3:
        return None
    nums = nums[:3]
    total = sum(nums)
    if total <= 0:
        return None
    return {"home": nums[0] / total, "draw": nums[1] / total, "away": nums[2] / total}


def _split_pair(value):
    raw = _strip_md(value).replace("<br>", " ")
    parts = re.split(r"\s*(?:vs|VS|v|V)\s*", raw, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", ""


def _header_starts(cells, expected):
    normalized = [_strip_md(x) for x in cells]
    return normalized[:len(expected)] == expected


def _empty_prediction():
    return {
        "single": None,
        "htft": None,
        "scores": "",
        "score_options": [],
        "total_goals": None,
    }


def parse_10027s_markdown(markdown: str) -> List[Dict]:
    lines = [x.strip() for x in str(markdown or "").splitlines() if x.strip()]

    base_header_index = None
    for i, line in enumerate(lines):
        cells = _cells(line)
        if _header_starts(cells, BASE_HEADER):
            base_header_index = i
            break
    if base_header_index is None:
        raise ValueError("10027s 缺少结算基础表")

    records = {}
    order = []

    # The first 21 fields are stable even though later grouped headers expand
    # into separate home/away cells in markdown.
    i = base_header_index + 1
    while i < len(lines):
        cells = _cells(lines[i])
        if not cells:
            break
        # The comprehensive 10027s page contains subsequent fusion tables.
        # Stop the base-table scan at the next fusion header so fusion rows
        # cannot be misread as settlement/base rows.
        if _header_starts(cells, FUSION_PREFIX):
            break
        if all(re.fullmatch(r"[:\- ]*", x or "") for x in cells):
            i += 1
            continue

        day = _strip_md(cells[0]) if len(cells) > 0 else ""
        mid = _match_id(cells[1]) if len(cells) > 1 else None
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or mid is None:
            i += 1
            continue

        league = _strip_md(cells[2]) if len(cells) > 2 else ""
        kickoff = _strip_md(cells[3]) if len(cells) > 3 else ""
        combined_score = _strip_md(cells[4]) if len(cells) > 4 else ""
        home = _strip_md(cells[8]) if len(cells) > 8 else ""
        away = _strip_md(cells[11]) if len(cells) > 11 else ""
        half_score = _score(cells[12]) if len(cells) > 12 else None
        full_score = _score(cells[13]) if len(cells) > 13 else None

        # Defensive fallback: combined "HT / FT" column.
        if (half_score is None or full_score is None) and "/" in combined_score:
            parts = combined_score.split("/", 1)
            half_score = half_score or _score(parts[0])
            full_score = full_score or _score(parts[1])

        item = {
            "match_id": mid,
            "date": day,
            "home_team": home,
            "away_team": away,
            "league": league,
            "kickoff": kickoff,
            "result": full_score,
            "half_score": half_score,
            "market": {
                "home_odds": _num(cells[5]) if len(cells) > 5 else None,
                "draw_odds": _num(cells[6]) if len(cells) > 6 else None,
                "away_odds": _num(cells[7]) if len(cells) > 7 else None,
            },
            "possession": {
                "home": _percent(cells[9]) if len(cells) > 9 else None,
                "away": _percent(cells[10]) if len(cells) > 10 else None,
                "diff": _num(cells[14]) if len(cells) > 14 else None,
                "interval": _strip_md(cells[15]) if len(cells) > 15 else "",
                "smooth_p": _num(cells[16]) if len(cells) > 16 else None,
            },
            "page_probability": None,
            "value": {
                "ev": _num(cells[17]) if len(cells) > 17 else None,
                "kelly": _num(cells[18]) if len(cells) > 18 else None,
            },
            "team_dna": {},
            "research_factors": {},
            "page_prediction": _empty_prediction(),
        }
        key = (day, mid)
        records[key] = item
        order.append(key)
        i += 1

    # Merge every fusion summary table into the settlement/base records.
    for i, line in enumerate(lines):
        header = _cells(line)
        if not _header_starts(header, FUSION_PREFIX):
            continue

        h = [_clean_header(x) for x in header]
        index = {name: pos for pos, name in enumerate(h)}
        j = i + 1
        while j < len(lines):
            row = _cells(lines[j])
            if not row:
                break
            if all(re.fullmatch(r"[:\- ]*", x or "") for x in row):
                j += 1
                continue
            if _header_starts(row, FUSION_PREFIX):
                break

            day = _strip_md(row[index["日期"]]) if index.get("日期") is not None and index["日期"] < len(row) else ""
            mid = _match_id(row[index["场次"]]) if index.get("场次") is not None and index["场次"] < len(row) else None
            if not day or mid is None:
                j += 1
                continue

            key = (day[:10], mid)
            item = records.get(key)
            if item is None:
                # Team fallback only if base row could not be keyed.
                matchup = row[index["对阵"]] if index.get("对阵") is not None and index["对阵"] < len(row) else ""
                home, away = _split_pair(matchup)
                for candidate in records.values():
                    if candidate["date"] == day[:10] and candidate["home_team"] == home and candidate["away_team"] == away:
                        item = candidate
                        break
            if item is None:
                j += 1
                continue

            def value(name):
                pos = index.get(name)
                return _strip_md(row[pos]) if pos is not None and pos < len(row) else ""

            item["page_prediction"]["single"] = value("单选") or item["page_prediction"].get("single")
            item["page_prediction"]["htft"] = value("半全场") or item["page_prediction"].get("htft")
            probability = _probability(value("融合真实概率"))
            if probability is not None:
                item["page_probability"] = probability

            factors = item.setdefault("research_factors", {})

            # Preserve every fusion column for reverse engineering. This keeps
            # future source fields from being silently discarded.
            raw_fusion = item.setdefault("raw_fusion_fields", {})
            for pos, name in enumerate(h):
                if pos < len(row) and name:
                    raw_fusion[name] = _strip_md(row[pos])

            factors.update({
                "odds_judgement": value("赔率判断"),
                "draw_odds": _num(value("平赔率")),
                "fusion_draw": _num(value("融合平值")),
                "advantage_diff": _num(value("优势差")),
                "draw_composite_score": _num(value("平局综合分")),
                "advantage_side": value("优势方"),
                "structure": value("结构"),
                "consistency": value("一致"),
                "pattern": value("规律"),
                "rating_score": _num(value("评分")),
                "rating": value("评级"),
                "risk": value("风险"),
                "handicap": value("盘口"),
                "ignore": value("忽略"),
                # Common 10027s model-factor columns. Empty when a particular
                # fusion table/version does not expose them.
                "home_attack": _num(value("主队进攻") or value("主进攻")),
                "away_attack": _num(value("客队进攻") or value("客进攻")),
                "home_defense": _num(value("主队防守") or value("主防守")),
                "away_defense": _num(value("客队防守") or value("客防守")),
                "home_h2h": _num(value("主队交锋") or value("主交锋")),
                "away_h2h": _num(value("客队交锋") or value("客交锋")),
                "home_form": _num(value("主队状态") or value("主状态")),
                "away_form": _num(value("客队状态") or value("客状态")),
                "attack": _num(value("进攻")),
                "defense": _num(value("防守")),
                "h2h": _num(value("交锋")),
                "form": _num(value("状态")),
                "water_level": value("水位") or value("水盘"),
                "home_water": _num(value("主水") or value("主队水位")),
                "away_water": _num(value("客水") or value("客队水位")),
            })

            j += 1

    result = [records[key] for key in order]
    if not result:
        raise ValueError("10027s 页面未解析到比赛数据")
    return result
