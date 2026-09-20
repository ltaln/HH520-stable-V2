import math
import re
from typing import List, Dict

_BASE = ["场次", "联赛", "时间", "比分", "胜", "平", "负", "主队", "主控球率", "客控球率", "客队", "差值", "区间", "平滑p", "EV", "凯利比例", "建议下注", "是否下注", "进攻", "防守", "交锋", "状态", "打出", "图形", "首发", "复制"]
_FUSION = ["排名", "场次", "对阵", "比赛结果", "官方赔率", "平赔率", "融合平值", "优势差", "平局综合分", "优势方", "单选", "融合真实概率", "结构", "一致", "规律", "评分", "评级", "风险", "半全场", "最可能比分", "总进球", "盘口", "忽略"]


def _cells(line):
    if not line.lstrip().startswith("|"):
        return []
    return [x.strip().replace("<br>", " ") for x in line.strip().strip("|").split("|")]


def _num(text, field, allow_missing=False):
    if allow_missing and str(text).strip() in ("", "-", "--", "—"):
        return None
    try:
        v = float(str(text).replace("%", "").strip())
    except Exception:
        raise ValueError(f"{field} 不是数字: {text!r}")
    if not math.isfinite(v):
        raise ValueError(f"{field} 无效")
    return v


def _normalize_match_id(value):
    """Normalize HH520 display IDs such as 001, 001*, 001C and 001A."""
    token = str(value or "").strip()
    token = token.replace("*", "")
    m = re.search(r"(\d+)", token)
    if not m:
        return None
    return int(m.group(1))


def _normalize_team(value):
    return re.sub(r"\s+", "", str(value or "").strip()).lower()


def _pair_key(text):
    raw = str(text or "").strip()
    parts = re.split(r"\s+vs\s+|\s+VS\s+|\s+v\s+|\s+-\s+", raw, maxsplit=1)
    if len(parts) != 2:
        return None
    home, away = _normalize_team(parts[0]), _normalize_team(parts[1])
    return (home, away) if home and away else None


def _rows(lines, start, end):
    out = []
    for line in lines[start + 1:end]:
        c = _cells(line)
        if not c:
            continue
        mid = _normalize_match_id(c[0])
        if mid is None:
            continue
        if len(c) < 26:
            continue
        out.append((mid, c))
    return out


def _parse_probability(raw):
    text = str(raw or "").replace("%", "").strip()
    if not text:
        return None
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", text)]
    if len(nums) < 3:
        return None
    nums = nums[:3]
    if any(x < 0 for x in nums) or sum(nums) <= 0:
        return None
    total = sum(nums)
    return {
        "home": nums[0] / total,
        "draw": nums[1] / total,
        "away": nums[2] / total,
    }


def _score_options(raw):
    out = []
    for home, away in re.findall(r"(\d+)\s*[-:：]\s*(\d+)", str(raw or "")):
        item = {"home": int(home), "away": int(away)}
        if item not in out:
            out.append(item)
    return out


def parse_10023s_markdown(markdown: str) -> List[Dict]:
    lines = [x.strip() for x in markdown.splitlines() if x.strip()]
    b = [i for i, x in enumerate(lines) if _cells(x)[:len(_BASE)] == _BASE]
    if not b:
        raise ValueError("缺少基础表表头")

    f = [i for i, x in enumerate(lines) if _cells(x)[:len(_FUSION)] == _FUSION]
    base = _rows(lines, b[0], f[0] if f else len(lines))
    if not base:
        return []

    fusion_by_id = {}
    fusion_by_pair = {}
    if f:
        for line in lines[f[0] + 1:]:
            c = _cells(line)
            if len(c) <= 2:
                continue

            mid = _normalize_match_id(c[1])
            if mid is not None and len(c) >= len(_FUSION):
                fusion_by_id[mid] = c

            pair = _pair_key(c[2])
            if pair and len(c) >= len(_FUSION):
                fusion_by_pair[pair] = c

    result = []
    for mid, c in base:
        item = {
            "match_id": str(mid),
            "home_team": c[7],
            "away_team": c[10],
            "league": c[1],
            "kickoff": c[2],
            "result": c[3],
            "market": {
                "home_odds": _num(c[4], "home"),
                "draw_odds": _num(c[5], "draw"),
                "away_odds": _num(c[6], "away"),
            },
            "page_probability": None,
            "value": {
                "ev": _num(c[14], "ev", True),
                "kelly": _num(c[15], "kelly", True),
                "signal": c[17],
            },
            "team_dna": {
                "attack": {
                    "home": _num(c[18], "attack", True),
                    "away": _num(c[19], "attack", True),
                },
                "defense": {
                    "home": _num(c[20], "defense", True),
                    "away": _num(c[21], "defense", True),
                },
            },
            "page_prediction": {
                "scores": "",
                "score_options": [],
                "htft": None,
                "total_goals": None,
                "single": None,
            },
        }

        fusion = fusion_by_id.get(mid)
        if fusion is None:
            pair = (_normalize_team(c[7]), _normalize_team(c[10]))
            fusion = fusion_by_pair.get(pair)

        if fusion is not None and len(fusion) > 20:
            item["page_probability"] = _parse_probability(fusion[11])
            item["page_prediction"] = {
                "scores": fusion[19],
                "score_options": _score_options(fusion[19]),
                "htft": fusion[18],
                "total_goals": fusion[20],
                "single": fusion[10],
            }

        result.append(item)

    return result
