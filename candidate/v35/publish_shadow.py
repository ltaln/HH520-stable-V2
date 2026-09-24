import json,os,re,subprocess,tempfile
from pathlib import Path

def git(*args,cwd=None,check=True):
    return subprocess.run(["git",*args],cwd=cwd,check=check,text=True,capture_output=True)

def publish(source_file,request_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}",request_id):
        raise ValueError("invalid request_id")
    data=json.loads(Path(source_file).read_text(encoding="utf-8"))
    data["_action"]={"request_id":request_id,"run_id":os.getenv("GITHUB_RUN_ID",""),"source_sha":os.getenv("GITHUB_SHA","")}
    root=Path(git("rev-parse","--show-toplevel").stdout.strip())
    git("config","user.name","github-actions[bot]",cwd=root)
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com",cwd=root)
    branch="v35-shadow-results"
    refs=git("ls-remote","--heads","origin",branch,cwd=root).stdout
    with tempfile.TemporaryDirectory(prefix="v35-shadow-") as tmp:
        target=Path(tmp)/"tree"
        if refs:
            git("fetch","--depth=1","origin",branch,cwd=root)
            git("worktree","add","--detach",str(target),"FETCH_HEAD",cwd=root)
        else:
            git("worktree","add","--detach",str(target),"HEAD",cwd=root)
            git("checkout","--orphan",branch,cwd=target)
            git("rm","-rf",".",cwd=target)
        try:
            p=target/"results"/f"{request_id}.json"; p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
            git("add","--",".",cwd=target); git("commit","-m",f"v35-shadow: {request_id}",cwd=target)
            first=git("push","origin",f"HEAD:{branch}",cwd=target,check=False)
            if first.returncode!=0:
                git("pull","--rebase","origin",branch,cwd=target)
                git("push","origin",f"HEAD:{branch}",cwd=target)
        finally:
            git("worktree","remove","--force",str(target),cwd=root,check=False)

if __name__=="__main__":
    import sys; publish(sys.argv[1],sys.argv[2])
