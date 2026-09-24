# HH520 Plugin — GitHub App Native Tool Contract

This contract replaces the old Custom Actions while keeping the existing GitHub Actions bridge unchanged.

## Native tools

The plugin package must attach the GitHub connector as a required app. Without
that attachment, a migrated mobile GPT can load the skill text but cannot call
the file tools, which produces a false "no READY result" conversation.

```json
{"apps":{"github":{"id":"connector_76869538009648d5b282a4bb21c3d157","required":true}}}
```

| Tool | Operation | Fixed values |
| --- | --- | --- |
| `github_create_file` | Create exactly one request file | repository `ltaln/HH520-stable-V2`, branch `main` |
| `github_fetch_file` | Poll one result file | prediction ref `action-results`; research ref `research-results` |

`github_create_file` is the only plugin write. The push to `main` causes
`.github/workflows/hh520-plugin-bridge.yml` to dispatch the appropriate
workflow. The plugin never calls `startHH520Prediction` or
`getHH520PredictionResult` and never dispatches a workflow directly.

## Exactly-once protocol

Generate one unique `request_id` per user command and write one JSON request.
A result 404 or `PENDING` is a read-state: fetch the same path again with a
new poll marker. It is never permission to write another request or trigger a
workflow. A create-file conflict is not permission to generate a replacement
ID; keep reading the original ID.

Prediction request: `plugin-requests/prediction/<request_id>.json` with
`{"type":"prediction","request_id":"<request_id>","command":"预测 YYYY-MM-DD 全部比赛"}`.
Read `results/<request_id>.json` on `action-results`.

Research request: `plugin-requests/research/<request_id>.json` with
`{"type":"research","request_id":"<request_id>","start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD"}`.
Read `research-results/results/<request_id>.json` on `research-results`.

## Result handling

- `PENDING` or HTTP 404: keep reading the same result path.
- `READY` prediction: render only `output_contract.display_rows`, the strict six-column contract; do not fetch the archive for ordinary display.
- `READY` research: return the compact research summary; detail pages remain isolated on `research-results`.
- `FAILED`: stop and report the returned error; do not auto-retry.

The GPT/plugin role is always `EXPLANATION_ONLY`. Stable V3.5.1 model logic,
probability layers, Failure Detector, HT/FT, score model, 10027S source, and
the six-column output contract are read-only from the plugin's perspective.

## Legacy OpenAPI Action compatibility

If a mobile client still has the legacy OpenAPI Action imported, its result GET
must use `ref=action-results`, a fresh `poll_timestamp` query value on every
request, and `Accept: application/vnd.github.raw+json`. The raw media type is
important: without it, GitHub returns a Contents API envelope with
`content`/`encoding` and the client can mistake a READY file for a missing
status. A raw `status=READY` response is rendered immediately from
`output_contract.display_rows`; it is never turned into a waiting message.
