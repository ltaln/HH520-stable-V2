"""Publish PENDING/FAILED action state using the same isolated result branch."""
import json
import os
import sys
import tempfile
from pathlib import Path
from scripts.publish_action_result import publish

def main():
    if len(sys.argv) != 5:
        raise SystemExit("usage: publish_action_status.py BRANCH REQUEST_ID STATUS KIND")
    branch, request_id, status, kind = sys.argv[1:]
    if status not in {"PENDING", "FAILED"}:
        raise SystemExit("invalid status")
    payload = {
        "status": status,
        "kind": kind,
        "request_id": request_id,
        "message": (
            "Workflow accepted and is still running."
            if status == "PENDING"
            else "Workflow failed before a final result was published."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="hh520-status-") as td:
        path = Path(td) / f"{request_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        publish(str(path), branch, request_id)

if __name__ == "__main__":
    main()
