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
        v=float(str(text).replace("%", "").strip())
    except Exception:
        raise ValueError(f"{field} 不是数字: {text!r}")
    if not math.isfinite(v):
        raise ValueError(f"{field} 无效")
    return v

def _rows(lines,start,end):
    out=[]
    for line in lines[start+1:end]:
        c=_cells(line)
        if len(c)>=1 and re.fullmatch(r"\d+", c[0].replace("*", "").strip()):
            if len(c)<26:
                continue
            out.append((int(c[0].replace("*", "")),c))
    return out

def parse_10023s_markdown(markdown: str) -> List[Dict]:
    lines=[x.strip() for x in markdown.splitlines() if x.strip()]
    b=[i for i,x in enumerate(lines) if _cells(x)[:len(_BASE)]==_BASE]
    if not b:
        raise ValueError("缺少基础表表头")
    f=[i for i,x in enumerate(lines) if _cells(x)[:len(_FUSION)]==_FUSION]
    base=_rows(lines,b[0],f[0] if f else len(lines))
    if not base:
        return []
    fusion={}
    if f:
        for line in lines[f[0]+1:]:
            c=_cells(line)
            if len(c)>1 and re.fullmatch(r"\d+C?",c[1].replace("*","")):
                fusion[int(re.sub('[^0-9]','',c[1]))]=c
    result=[]
    for mid,c in base:
        item={
            "match_id":str(mid),
            "home_team":c[7],
            "away_team":c[10],
            "league":c[1],
            "kickoff":c[2],
            "result":c[3],
            "market":{"home_odds":_num(c[4],"home"),"draw_odds":_num(c[5],"draw"),"away_odds":_num(c[6],"away")},
            "page_probability":None,
            "value":{"ev":_num(c[14],"ev",True),"kelly":_num(c[15],"kelly",True),"signal":c[17]},
            "team_dna":{"attack":{"home":_num(c[18],"attack"),"away":_num(c[19],"attack")},"defense":{"home":_num(c[20],"defense"),"away":_num(c[21],"defense")}},
            "page_prediction":{"scores":"","htft":None,"total_goals":None}
        }
        if mid in fusion and len(fusion[mid])>20:
            item["page_prediction"]={"scores":fusion[mid][19],"htft":fusion[mid][18],"total_goals":fusion[mid][20]}
        result.append(item)
    return result
