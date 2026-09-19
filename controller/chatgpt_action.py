"""Minimal WSGI bridge for V1.5 ChatGPT execution, not a replacement website."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs
import json
import os
import secrets
from dotenv import load_dotenv
from controller.command_router import parse_command
from collector.url_builder import validate_date
from controller.execution_manager import execute_prediction

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
_pool = ThreadPoolExecutor(max_workers=1)
_jobs = {}
_lock = Lock()

def prepare(date):
    data = execute_prediction(date, use_gpt=False)
    return {"date": date, "captured_at": data["captured_at"], "source_url": data["url"],
            "match_count": len(data["matches"]), "gpt_handoff": data["gpt_handoff"],
            "excluded": [{"match_id": r["match_id"], "status": r["status"], "reason": r["reason"]}
                         for r in data["predictions"] if r["status"] != "READY_FOR_GPT"]}

def application(environ, start_response):
    def reply(status, body):
        content = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        start_response(status, [("Content-Type", "application/json; charset=utf-8"),
                                ("Content-Length", str(len(content))), ("Cache-Control", "no-store")])
        return [content]
    path = environ.get("PATH_INFO", "")
    method = environ.get("REQUEST_METHOD", "")
    if path == "/health" and method == "GET":
        return reply("200 OK", {"ok": True})
    token = os.getenv("HH520_ACCESS_TOKEN", "").strip()
    if not token or token == "generate-a-long-random-token":
        return reply("503 Service Unavailable", {"error": "Action访问令牌未配置"})
    provided = environ.get("HTTP_AUTHORIZATION", "")
    if not secrets.compare_digest(provided.encode(), ("Bearer " + token).encode()):
        return reply("401 Unauthorized", {"error": "访问令牌无效"})
    try:
        if path == "/prepare" and method == "POST":
            length = int(environ.get("CONTENT_LENGTH") or "0")
            if not 0 < length <= 4096:
                raise ValueError("命令请求大小无效")
            payload = json.loads(environ["wsgi.input"].read(length))
            if not isinstance(payload, dict) or not isinstance(payload.get("command"), str):
                raise ValueError("需要字符串command")
            date = parse_command(payload["command"])["date"]
            # Return quickly to fit the Action timeout. The only scraping task is
            # deduplicated by date; collector's persistent ledger also prevents refetch.
            with _lock:
                if date not in _jobs:
                    _jobs[date] = _pool.submit(prepare, date)
            return reply("202 Accepted", {"date": date, "status": "pending",
                                         "result_path": "/prepared/" + date})
        if path.startswith("/prepared/") and method == "GET":
            date = validate_date(path.removeprefix("/prepared/"))
            query = parse_qs(environ.get("QUERY_STRING", ""))
            offset = int(query.get("offset", ["0"])[0])
            if offset < 0:
                raise ValueError("offset不能为负")
            with _lock:
                job = _jobs.get(date)
            if job is None:
                return reply("404 Not Found", {"error": "请先提交预测命令"})
            if not job.done():
                return reply("202 Accepted", {"date": date, "status": "pending"})
            result = job.result()
            handoff = result["gpt_handoff"]
            matches = handoff["matches"]
            end = offset + 10
            return reply("200 OK", {
                "status": "ready", "date": date, "captured_at": result["captured_at"],
                "source_url": result["source_url"], "match_count": result["match_count"],
                "eligible_count": len(matches), "excluded": result["excluded"],
                "prompt": handoff["prompt"], "config": handoff["config"],
                "matches": matches[offset:end], "next_offset": end if end < len(matches) else None,
            })
        return reply("404 Not Found", {"error": "未知接口"})
    except (ValueError, RuntimeError, OSError) as exc:
        return reply("400 Bad Request", {"error": str(exc)})

if __name__ == "__main__":
    # Development only. Production must provide HTTPS:443 and one WSGI worker
    # with persistent cache storage; do not expose this HTTP listener publicly.
    from wsgiref.simple_server import make_server
    with make_server("127.0.0.1", 8787, application) as httpd:
        print("Action development endpoint: http://127.0.0.1:8787")
        httpd.serve_forever()
