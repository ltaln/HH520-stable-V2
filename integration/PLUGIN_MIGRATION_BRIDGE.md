# HH520 Plugin Migration Bridge

This bridge exists because migrated ChatGPT Plugins do not inherit Custom GPT Actions automatically.

## Stable model protection

This bridge does **not** modify HH520 Stable V3.4 model logic.
It only converts a GitHub file write into the existing workflow_dispatch call.

## Prediction request

Create a new UTF-8 JSON file under:

`plugin-requests/prediction/<request_id>.json`

Example:

```json
{
  "type": "prediction",
  "request_id": "hh520-20260924-a1b2c3d4",
  "command": "预测 2026-09-24 全部比赛"
}
```

The bridge dispatches `.github/workflows/hh520-predict.yml` using the same request_id.

Poll the existing result path:

`results/<request_id>.json` on branch `action-results`.

## Research request

Create:

`plugin-requests/research/<request_id>.json`

Example:

```json
{
  "type": "research",
  "request_id": "hh520-research-20260924-a1b2c3d4",
  "start_date": "2026-09-20",
  "end_date": "2026-09-24"
}
```

The bridge dispatches `.github/workflows/hh520-research.yml`.

Poll:

`research-results/results/<request_id>.json` on branch `research-results`.

## Plugin execution rule

For prediction:
1. Generate one unique request_id.
2. Create exactly one request JSON file in `plugin-requests/prediction/`.
3. Never create a second request file for the same user command.
4. Poll the same request_id from `action-results`.
5. On PENDING or 404, keep polling.
6. On READY, render only the authoritative V3.4 6-column `display_rows`.
7. On FAILED, stop and report the failure.
8. Never recalculate or replace the frozen model output.

For research, use the same pattern with `plugin-requests/research/` and
`research-results/results/<request_id>.json` on the `research-results` branch.

## GitHub App native plugin entry

The migrated plugin does not use the legacy Custom GPT Action operations. It
uses the GitHub App `github_create_file` tool once to create the request file
on `main`, then uses `github_fetch_file` only for polling the result branch.
See `PLUGIN_NATIVE_TOOLS.md` and `CHATGPT_INSTRUCTIONS.md` for the exact
tool arguments and the exactly-once request protocol.
