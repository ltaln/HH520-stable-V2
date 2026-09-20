import math
import re
from typing import List, Dict

_BASE = ["场次", "联赛", "时间", "比分", "胜", "平", "负", "主队", "主控球率", "客控球率", "客队", "差值", "区间", "平滑p", "EV", "凯利比例", "建议下注", "是否下注", "进攻", "防守", "交锋", "状态", "打出", "图形", "首发", "复制"]
_FUSION = ["排名", "场次", "对阵", "比赛结果", "官方赔率", "平赔率", "融合平值", "优势差", "平局综合分", "优势方", "单选", "融合真实概率", "结构", "一致", "规律", "评分", "评级", "风险", "半全场", "最可能比分", "总进球", "盘口", "忽略"]

def _cells(line):
    return [x.strip().replace("<br>", " ") for x in line.strip().strip("|").split("|")] if line.lstrip().startswith("|") else []

def _num(text, field, allow_missing=False):
    if allow_missing and str(text).strip() in ("-", "", "--", "—"):
        return None
    try:
        v = float(text.strip().replace("%", ""))
    except (TypeError, ValueError):
        raise ValueError(f"{field} 不是数字: {text!r}") from None
    if not math.isfinite(v):
        raise ValueError(f"{field} 不是有限数字")
    return v
