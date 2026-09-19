import math
import re
from typing import List, Dict

_BASE = ["场次", "联赛", "时间", "比分", "胜", "平", "负", "主队", "主控球率", "客控球率", "客队", "差值", "区间", "平滑p", "EV", "凯利比例", "建议下注", "是否下注", "进攻", "防守", "交锋", "状态", "打出", "图形", "首发", "复制"]
_FUSION = ["排名", "场次", "对阵", "比赛结果", "官方赔率", "平赔率", "融合平值", "优势差", "平局综合分", "优势方", "单选", "融合真实概率", "结构", "一致", "规律", "评分", "评级", "风险", "半全场", "最可能比分", "总进球", "盘口", "忽略"]

def _cells(line):
    return [x.strip().replace("<br>", " ") for x in line.strip().strip("|").split("|")] if line.lstrip().startswith("|") else []

def _num(text, field):
    try: v = float(text.strip().replace("%", ""))
    except (TypeError, ValueError): raise ValueError(f"{field} 不是数字: {text!r}") from None
    if not math.isfinite(v): raise ValueError(f"{field} 不是有限数字")
    return v

def _rows(lines, start, end, header, pos, name):
    out = []
    for line in lines[start + 1:end]:
        c = _cells(line); token = re.sub(r"[*]", "", c[pos]).strip() if len(c) > pos else ""
        if not c or set(c) <= {"-", "---", ""} or not re.fullmatch(r"\d+", token): continue
        expected = 30 if name == "基础表" else len(header)
        if len(c) != expected: raise ValueError(f"{name}场次 {token} 列数错误: {len(c)}")
        out.append((int(token), c))
    if not out: raise ValueError(f"{name}没有有效比赛行")
    return out

def parse_10023s_markdown(markdown: str) -> List[Dict]:
    if not isinstance(markdown, str): raise ValueError("10023s markdown 为空或异常")
    first_line = next((line.strip() for line in markdown.splitlines() if line.strip()), "")
    if "该日暂无赛事实力数据" in first_line and not any(_cells(line)[:len(_BASE)] == _BASE for line in markdown.splitlines()):
        return []
    if len(markdown.strip()) < 50: raise ValueError("10023s markdown 为空或异常")
    lines = [x.strip() for x in markdown.splitlines() if x.strip()]
    bs = [i for i,x in enumerate(lines) if _cells(x)[:len(_BASE)] == _BASE]
    fs = [i for i,x in enumerate(lines) if _cells(x)[:len(_FUSION)] == _FUSION]
    if len(bs) != 1 or not fs: raise ValueError("缺少基础表/融合表表头")
    base = _rows(lines, bs[0], fs[0], _BASE, 0, "基础表")
    count = re.search(r"共\s*(\d+)\s*场比赛", markdown)
    if count and int(count.group(1)) != len(base):
        raise ValueError("基础表行数与页面总场次数不符")
    fused = {}
    for line in lines[fs[0] + 1:]:
        c = _cells(line); token = re.sub(r"[*]", "", c[1]).strip() if len(c) > 1 else ""
        m = re.fullmatch(r"(\d+)(C)?", token, re.I)
        if not c or set(c) <= {"-", "---", ""} or not m: continue
        if len(c) != len(_FUSION): raise ValueError(f"融合表场次 {token} 列数错误: {len(c)}")
        mid, marked = int(m.group(1)), bool(m.group(2))
        if mid in fused:
            # The three display blocks repeat rows.  Identical rows are a
            # presentation duplicate; 1C is an explicit duplicate marker.
            if c[2:] != fused[mid][1][2:]: raise ValueError(f"融合表场次 {mid} 重复内容冲突")
            continue
        fused[mid] = (marked, c)
    if not fused: raise ValueError("融合表没有有效比赛行")
    base_ids = {mid for mid, _ in base}
    unknown = set(fused) - base_ids
    if unknown: raise ValueError(f"融合表引用不存在的场次: {sorted(unknown)}")
    result, seen = [], set()
    for mid, c in base:
        if mid in seen: raise ValueError(f"基础表场次 {mid} 重复")
        seen.add(mid); home, away = c[7].strip(), c[10].strip()
        if not home or not away:
            raise ValueError(f"基础表场次 {mid} 球队名为空")
        dna = {k: {"home": _num(c[i], k), "away": _num(c[i+1], k)} for k,i in (("attack",18),("defense",20),("head_to_head",22),("form",24))}
        kelly = None if c[15] == "-" else _num(c[15], "凯利比例")/100
        item = {"match_id": str(mid), "home_team": home, "away_team": away, "league": c[1], "kickoff": c[2], "result": c[3], "market": {"home_odds": _num(c[4], "主胜赔率"), "draw_odds": _num(c[5], "平赔率"), "away_odds": _num(c[6], "客胜赔率")}, "page_probability": None, "value": {"ev": None if c[14] == "-" else _num(c[14], "EV"), "kelly": kelly, "kelly_fraction": kelly, "stake": None if c[16] == "-" else _num(c[16], "建议下注"), "signal": c[17], "bet": c[17]}, "team_dna": dna, "page_prediction": {"scores": "", "htft": None, "total_goals": None}}
        if mid in fused:
            _, f = fused[mid]; pair = f[2].split(" vs ")
            if len(pair) != 2 or pair[0].strip() != home or pair[1].strip() != away: raise ValueError(f"融合场次 {mid} 球队与基础表不匹配")
            raw_prob = f[11].replace("%", "").strip()
            if not re.fullmatch(r"\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?", raw_prob): raise ValueError(f"融合场次 {mid} 的融合真实概率不完整")
            nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", raw_prob)]
            if any(x < 0 or x > 100 for x in nums) or sum(nums) <= 0: raise ValueError(f"融合场次 {mid} 的融合真实概率无效")
            total = sum(nums); item["page_probability"] = dict(zip(("home","draw","away"), (x/total for x in nums)))
            item["page_prediction"] = {"scores": f[19], "score_options": [{"home": int(a), "away": int(b)} for a,b in re.findall(r"(\d+)\s*-\s*(\d+)", f[19])], "htft": f[18], "total_goals": f[20], "single": f[10]}
        item["page_context"] = {
            "home_possession": _num(c[8], "主控球率"),
            "away_possession": _num(c[9], "客控球率"),
            "difference": None if c[11] == "-" else _num(c[11], "差值"),
            "interval": c[12],
            "smoothed_p": None if c[13] == "-" else _num(c[13], "平滑p") / 100,
            "smoothed_p_target": "未确认，不参与胜平负方向",
        }
        result.append(item)
    return result
