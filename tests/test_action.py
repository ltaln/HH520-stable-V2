from concurrent.futures import Future
from io import BytesIO
import json
from unittest.mock import Mock
from controller import chatgpt_action as action

def request(path,method="GET",body=None,token="test-token",query=""):
    raw=json.dumps(body or {},ensure_ascii=False).encode()
    captured={}
    def response(status,headers): captured["status"]=status
    result=action.application({"PATH_INFO":path,"REQUEST_METHOD":method,
        "CONTENT_LENGTH":str(len(raw)),"wsgi.input":BytesIO(raw),
        "HTTP_AUTHORIZATION":"Bearer "+token,"QUERY_STRING":query},response)
    return captured["status"],json.loads(b"".join(result))

def test_auth_blocks_work(monkeypatch):
    monkeypatch.setenv("HH520_ACCESS_TOKEN","test-token")
    assert request("/prepare","POST",{"command":"预测 2026-09-19"},token="wrong")[0].startswith("401")

def test_job_deduplication_paging_and_no_api(monkeypatch):
    monkeypatch.setenv("HH520_ACCESS_TOKEN","test-token")
    monkeypatch.setattr(action,"_jobs",{})
    future=Future()
    pool=Mock()
    pool.submit.return_value=future
    monkeypatch.setattr(action,"_pool",pool)
    command={"command":"预测 2026-09-19 全部比赛"}
    assert request("/prepare","POST",command)[0].startswith("202")
    request("/prepare","POST",command)
    assert pool.submit.call_count==1
    assert request("/prepared/2026-09-19")[1]["status"]=="pending"
    future.set_result({"date":"2026-09-19","captured_at":"now","source_url":"source","match_count":11,
        "excluded":[],"gpt_handoff":{"prompt":"prompt","config":{},"matches":[{"match_id":str(i)} for i in range(11)]}})
    page=request("/prepared/2026-09-19")[1]
    assert len(page["matches"])==10 and page["next_offset"]==10
    last=request("/prepared/2026-09-19",query="offset=10")[1]
    assert len(last["matches"])==1 and last["next_offset"] is None

def test_failed_job_does_not_resubmit(monkeypatch):
    monkeypatch.setenv("HH520_ACCESS_TOKEN","test-token")
    failure=Future(); failure.set_exception(ValueError("schema changed"))
    monkeypatch.setattr(action,"_jobs",{"2026-09-19":failure})
    assert request("/prepared/2026-09-19")[1]["error"]=="schema changed"

def test_handoff_runs_without_openai_key(monkeypatch):
    execute=Mock(return_value={"captured_at":"now","url":"source","matches":[],
        "predictions":[],"gpt_handoff":{"matches":[]}})
    monkeypatch.setattr(action,"execute_prediction",execute)
    assert action.prepare("2026-09-19")["match_count"]==0
    execute.assert_called_once_with("2026-09-19",use_gpt=False)
