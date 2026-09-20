"""Publish one result using checkout's existing authenticated Git worktree."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

def git(*args, cwd=None, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, text=True, capture_output=True)

def publish(result_file, branch, request_id):
    if branch not in ("action-results", "research-results"):
        raise ValueError("Invalid result branch")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id):
        raise ValueError("Invalid request_id")
    source=Path(result_file).resolve()
    data=json.loads(source.read_text(encoding="utf-8"))
    data["_action"]={key:os.getenv(env,"") for key,env in (
        ("request_id","REQUEST_ID"),("repository","GITHUB_REPOSITORY"),
        ("run_id","GITHUB_RUN_ID"),("run_attempt","GITHUB_RUN_ATTEMPT"),
        ("source_sha","GITHUB_SHA"))}
    data["_action"]["request_id"]=request_id
    root=Path(git("rev-parse","--show-toplevel").stdout.strip())
    git("config","user.name","github-actions[bot]",cwd=root)
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com",cwd=root)
    refs=git("ls-remote","--heads","origin",branch,cwd=root).stdout
    with tempfile.TemporaryDirectory(prefix="hh520-publish-") as temporary:
        target=Path(temporary)/"tree"
        if refs:
            git("fetch","--depth=1","origin",branch,cwd=root)
            git("worktree","add","--detach",str(target),"FETCH_HEAD",cwd=root)
        else:
            git("worktree","add","--detach",str(target),"HEAD",cwd=root)
            git("checkout","--orphan",branch,cwd=target)
            git("rm","-rf",".",cwd=target)
        try:
            destination=target/"results"/f"{request_id}.json"
            destination.parent.mkdir(exist_ok=True)
            if destination.exists():
                old=json.loads(destination.read_text(encoding="utf-8"))
                if old.get("_action",{}).get("run_id")!=os.getenv("GITHUB_RUN_ID",""):
                    raise ValueError("request_id already belongs to another workflow run")
            destination.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
            git("add","--",f"results/{request_id}.json",cwd=target)
            if git("diff","--cached","--quiet",cwd=target,check=False).returncode==0:
                return
            git("commit","-m",f"{branch}: {request_id}",cwd=target)
            git("push","origin",f"HEAD:{branch}",cwd=target)
        finally:
            git("worktree","remove","--force",str(target),cwd=root,check=False)

if __name__=="__main__":
    import sys
    try:
        publish(*sys.argv[1:])
    except subprocess.CalledProcessError as exc:
        # Never echo Git headers or credential-bearing command output.
        raise SystemExit(f"Git result publication failed, exit {exc.returncode}")
