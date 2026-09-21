"""Publish one result using checkout's existing authenticated Git worktree.

Research results use a compact polling envelope:
- results/<request_id>.json: small READY summary safe for ChatGPT Actions polling
- archive/<request_id>.json: complete Research report
- pages/<request_id>/manifest.json + error-attribution pages: bounded detail payloads

Prediction results retain the original single-file behavior.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

RESEARCH_PAGE_SIZE = 20


def git(*args, cwd=None, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, text=True, capture_output=True)


def _action_meta(request_id):
    data = {key: os.getenv(env, "") for key, env in (
        ("request_id", "REQUEST_ID"),
        ("repository", "GITHUB_REPOSITORY"),
        ("run_id", "GITHUB_RUN_ID"),
        ("run_attempt", "GITHUB_RUN_ATTEMPT"),
        ("source_sha", "GITHUB_SHA"),
    )}
    data["request_id"] = request_id
    return data


def _research_summary(data, request_id):
    hidden = data.get("hidden_model_reverse") or {}
    error = data.get("error_attribution") or {}
    return {
        "status": "READY",
        "kind": "research",
        "request_id": request_id,
        "system": data.get("system"),
        "stable_access": data.get("stable_access"),
        "source": data.get("source"),
        "window": data.get("window"),
        "input_count": data.get("input_count"),
        "clean_count": data.get("clean_count"),
        "sanitizer": {
            "pollution_events": (data.get("sanitizer") or {}).get("pollution_events"),
        },
        "backtest": data.get("backtest"),
        "prediction_coverage": data.get("prediction_coverage"),
        "result_collection": data.get("result_collection"),
        "prediction_snapshot_layer": data.get("prediction_snapshot_layer"),
        "result_label_layer": data.get("result_label_layer"),
        "error_attribution": {
            "summary": error.get("summary"),
            "detail_pages": None,
        },
        "hidden_model_reverse": {
            "status": hidden.get("status"),
            "stable_access": hidden.get("stable_access"),
            "baseline": hidden.get("baseline"),
            "min_bucket_sample": hidden.get("min_bucket_sample"),
            "top_signals": (hidden.get("top_signals") or [])[:20],
            "signal_count": len(hidden.get("signals") or []),
        },
        "league_dna": data.get("league_dna"),
        "team_dna": (data.get("team_dna") or [])[:30],
        "candidate_rule_engine": {
            "status": (data.get("candidate_rule_engine") or {}).get("status"),
            "candidate_count": (data.get("candidate_rule_engine") or {}).get("candidate_count"),
            "thresholds": (data.get("candidate_rule_engine") or {}).get("thresholds"),
            "rejected_signal_count": (data.get("candidate_rule_engine") or {}).get("rejected_signal_count"),
        },
        "candidate_rules": data.get("candidate_rules"),
        "promotion_policy": data.get("promotion_policy"),
        "detail_manifest_path": f"pages/{request_id}/manifest.json",
        "archive_path": f"archive/{request_id}.json",
        "message": "Research READY. This polling payload is compact; use detail_manifest_path for paged details.",
    }


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def _publish_research_files(target, data, request_id):
    archive = target / "archive" / f"{request_id}.json"
    _write_json(archive, data)

    error_matches = ((data.get("error_attribution") or {}).get("matches") or [])
    page_paths = []
    for index in range(0, len(error_matches), RESEARCH_PAGE_SIZE):
        page_no = index // RESEARCH_PAGE_SIZE + 1
        rel = f"pages/{request_id}/error-{page_no}.json"
        page_paths.append(rel)
        _write_json(
            target / rel,
            {
                "status": "READY",
                "kind": "research_error_attribution_page",
                "request_id": request_id,
                "page": page_no,
                "page_size": RESEARCH_PAGE_SIZE,
                "items": error_matches[index:index + RESEARCH_PAGE_SIZE],
            },
        )

    hidden = data.get("hidden_model_reverse") or {}
    signals = hidden.get("signals") or []
    signal_paths = []
    for index in range(0, len(signals), RESEARCH_PAGE_SIZE):
        page_no = index // RESEARCH_PAGE_SIZE + 1
        rel = f"pages/{request_id}/signals-{page_no}.json"
        signal_paths.append(rel)
        _write_json(
            target / rel,
            {
                "status": "READY",
                "kind": "research_hidden_signal_page",
                "request_id": request_id,
                "page": page_no,
                "page_size": RESEARCH_PAGE_SIZE,
                "items": signals[index:index + RESEARCH_PAGE_SIZE],
            },
        )

    manifest = {
        "status": "READY",
        "kind": "research_detail_manifest",
        "request_id": request_id,
        "archive_path": f"archive/{request_id}.json",
        "error_attribution": {
            "item_count": len(error_matches),
            "page_size": RESEARCH_PAGE_SIZE,
            "pages": page_paths,
        },
        "hidden_model_signals": {
            "item_count": len(signals),
            "page_size": RESEARCH_PAGE_SIZE,
            "pages": signal_paths,
        },
    }
    _write_json(target / "pages" / request_id / "manifest.json", manifest)

    summary = _research_summary(data, request_id)
    summary["error_attribution"]["detail_pages"] = len(page_paths)
    summary["hidden_model_reverse"]["detail_pages"] = len(signal_paths)
    return summary


def publish(result_file, branch, request_id):
    if branch not in ("action-results", "research-results"):
        raise ValueError("Invalid result branch")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id):
        raise ValueError("Invalid request_id")

    source = Path(result_file).resolve()
    data = json.loads(source.read_text(encoding="utf-8"))
    if "status" not in data:
        data["status"] = "READY"
    data["_action"] = _action_meta(request_id)

    root = Path(git("rev-parse", "--show-toplevel").stdout.strip())
    git("config", "user.name", "github-actions[bot]", cwd=root)
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com", cwd=root)
    refs = git("ls-remote", "--heads", "origin", branch, cwd=root).stdout

    with tempfile.TemporaryDirectory(prefix="hh520-publish-") as temporary:
        target = Path(temporary) / "tree"
        if refs:
            git("fetch", "--depth=1", "origin", branch, cwd=root)
            git("worktree", "add", "--detach", str(target), "FETCH_HEAD", cwd=root)
        else:
            git("worktree", "add", "--detach", str(target), "HEAD", cwd=root)
            git("checkout", "--orphan", branch, cwd=target)
            git("rm", "-rf", ".", cwd=target)

        try:
            destination = target / "results" / f"{request_id}.json"
            destination.parent.mkdir(exist_ok=True)
            if destination.exists():
                old = json.loads(destination.read_text(encoding="utf-8"))
                if old.get("_action", {}).get("run_id") not in ("", os.getenv("GITHUB_RUN_ID", "")):
                    raise ValueError("request_id already belongs to another workflow run")

            if branch == "research-results" and data.get("status") == "READY":
                poll_data = _publish_research_files(target, data, request_id)
                poll_data["_action"] = data["_action"]
            else:
                poll_data = data

            _write_json(destination, poll_data)

            git("add", "--", ".", cwd=target)
            if git("diff", "--cached", "--quiet", cwd=target, check=False).returncode == 0:
                return
            git("commit", "-m", f"{branch}: {request_id}", cwd=target)

            first = git("push", "origin", f"HEAD:{branch}", cwd=target, check=False)
            if first.returncode != 0:
                git("pull", "--rebase", "origin", branch, cwd=target)
                git("push", "origin", f"HEAD:{branch}", cwd=target)
        finally:
            git("worktree", "remove", "--force", str(target), cwd=root, check=False)


if __name__ == "__main__":
    import sys
    try:
        publish(*sys.argv[1:])
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Git result publication failed, exit {exc.returncode}")
