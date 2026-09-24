"""Single batched, cached Responses request; GPT is explanation-only in V3.5 Phase 1."""
import hashlib
import json
import os
import tempfile
from pathlib import Path
import requests
import yaml
from collector import cache_manager

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "HH520_Stable_V3_5_Phase1_Prediction_Prompt.md"
FIELDS = (
    "match_id", "score1", "score2", "htft1", "htft2", "total_goals",
    "direction", "alternate_direction", "state", "reason",
)
PROPERTIES = {name: {"type": "string"} for name in FIELDS}
PROPERTIES.update(status={"type": "string", "enum": ["GPT", "PASS"]})
_SCHEMA = {"type":"object","additionalProperties":False,"required":["predictions"],
           "properties":{"predictions":{"type":"array","items":{
               "type":"object","additionalProperties":False,"properties":PROPERTIES,
               "required":list(PROPERTIES)}}}}


def validate_rows(parsed, matches):
    if not isinstance(parsed, dict):
        raise ValueError("GPT格式错误")
    rows = parsed.get("predictions")
    if not isinstance(rows, list) or len(rows) != len(matches):
        raise ValueError("GPT数量不匹配")
    for row, match in zip(rows, matches):
        if not isinstance(row, dict) or set(row) != set(PROPERTIES):
            raise ValueError("GPT字段不匹配")
        if any(not isinstance(row[k], str) for k in FIELDS):
            raise ValueError("GPT字段类型错误")
        if row["match_id"] != match["match_id"]:
            raise ValueError("GPT比赛顺序错误")
        if row["status"] not in ("GPT","PASS"):
            raise ValueError("GPT状态错误")
    return rows


def request_predictions(matches):
    model=os.getenv("OPENAI_MODEL","").strip()
    if not model:
        raise RuntimeError("--gpt 要求设置账户可用的 OPENAI_MODEL")

    prompt=PROMPT_PATH.read_text(encoding="utf-8")+"""
HH520 Stable V3.5 Phase 1 已由本地模型完成 FT校准、风险等级、独立比分、Cross Gate、HTFT和总进球。
你的角色只有解释和审核，绝对不得重新预测或修改 locked_prediction。
必须逐字复制 direction/alternate_direction/state/score1/score2/htft1/htft2/total_goals。
不得使用 建议下注、是否下注、page_prediction，也不得引入未采集的外部事实。
保持 match_id 和输入顺序。"""

    config=yaml.safe_load((PROMPT_PATH.parents[1]/"config"/"stable.yaml").read_text(encoding="utf-8"))
    body={"version":"3.5-p1","model":model,"schema":_SCHEMA,"prompt":prompt,"config":config,"matches":matches}
    digest=hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    cache_dir=cache_manager.CACHE_DIR
    cache_dir.mkdir(parents=True,exist_ok=True)
    path=cache_dir/f"gpt_predictions_{digest}.json"
    if path.exists():
        return validate_rows(json.loads(path.read_text(encoding="utf-8")),matches)

    key=os.getenv("OPENAI_API_KEY","").strip()
    if not key:
        raise RuntimeError("--gpt 要求设置 OPENAI_API_KEY")
    try:
        with path.with_suffix(".requested").open("x",encoding="utf-8") as stream:
            stream.write("Reserved. No automatic retry.\n")
    except FileExistsError as exc:
        raise RuntimeError("相同GPT输入已有未完成请求；停止以避免重复扣费") from exc

    try:
        response=requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
            json={
                "model":model,
                "input":json.dumps({"config":config,"matches":matches},ensure_ascii=False),
                "instructions":prompt,"store":False,"max_output_tokens":6000,
                "text":{"format":{"type":"json_schema","name":"hh520_predictions","strict":True,"schema":_SCHEMA}},
            },
            timeout=90,allow_redirects=False,
        )
        if response.status_code!=200:
            raise RuntimeError(f"Responses API HTTP {response.status_code}；未重试")
        data=response.json()
        if data.get("status")!="completed":
            raise ValueError("Responses未完成")
        content=[c["text"] for output in data.get("output",[]) if output.get("type")=="message"
                 for c in output.get("content",[]) if c.get("type")=="output_text"]
        parsed=json.loads("".join(content))
        rows=validate_rows(parsed,matches)
    except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
        raise RuntimeError("Responses请求失败或格式无效；未重试、未缓存结果") from exc

    fd,temporary=tempfile.mkstemp(dir=cache_dir,suffix=".tmp")
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            json.dump(parsed,stream,ensure_ascii=False)
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return rows
