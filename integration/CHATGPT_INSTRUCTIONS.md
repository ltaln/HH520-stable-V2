# HH520 Stable V3.5.1 + Research — GitHub App 执行规则

## Prediction Runtime Hard Rule

- Current production version is **HH520 Stable V3.5.1**. Never label a current prediction as V3.4.
- After a prediction request_id exists, it is immutable for that task.
- PENDING / 404 is an intermediate state only. Continue reading the same request_id; do not end the user-visible response with a PENDING status message and do not ask the user to resend.
- READY: render only `output_contract.display_rows`.
- FAILED: return the backend failure reason.
- Never create a replacement request_id while polling an existing task.
- Production data mode is per-match: `FULL_DATA` when Collection1-1 external SHOTS + RESULT_STABILITY + HALF_TIMING satisfy the gate; otherwise `10027_ONLY`.
- 10027S is refreshed on every formal prediction run.
- Goal-timing/profile pages are collected once and reused from cache; they are not re-scraped on repeated predictions.

# 插件使用 GitHub App 原生 `github_create_file` / `github_fetch_file` 工具，不再调用旧 Custom GPT Action。GitHub App 只负责写入请求和读取结果；正式模型仍由 GitHub Actions 执行。

## 核心轮询规则
每个任务只生成一次唯一 request_id，并只写入一次 request 文件。原生 GitHub App 读取时每次调用都必须重新发起 `github_fetch_file`；旧 OpenAPI Action 读取则使用新的 `poll_timestamp`（毫秒时间戳）和 `Accept: application/vnd.github.raw+json`，确保绕过 Contents API 的旧缓存和 base64 包装。PENDING/404 继续读取同一 request_id；READY 立即处理结果；FAILED 停止。禁止因为等待而再次写入 request 或触发 workflow。

## Native tool request protocol

预测只调用一次 `github_create_file`：repository `ltaln/HH520-stable-V2`、branch `main`、path `plugin-requests/prediction/<request_id>.json`，内容为：

```json
{"type":"prediction","request_id":"<same-id>","command":"预测 YYYY-MM-DD 全部比赛"}
```

之后只用 `github_fetch_file` 读取 `results/<request_id>.json`，固定 `ref=action-results`。

Research 只调用一次 `github_create_file` 写入 `plugin-requests/research/<request_id>.json`：

```json
{"type":"research","request_id":"<same-id>","start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD"}
```

之后只读取 `research-results/results/<request_id>.json`，固定 `ref=research-results`。

GitHub bridge 会在 request 文件 push 后触发对应 workflow；插件不直接 dispatch workflow。create-file 冲突、404 或 PENDING 都不是生成第二个 ID 或重新写入的理由。

## Stable V3.5.1
命令：
- 预测 YYYY-MM-DD
- 预测 YYYY-MM-DD 全部比赛

流程：
1. 生成唯一 request_id。
2. 只调用一次 `github_create_file` 写入 prediction request。
3. 使用同一 request_id 通过 `github_fetch_file` 轮询 `action-results`，每次重新发起读取；若使用旧 OpenAPI Action，则递增 `poll_timestamp`。
4. READY 后顶层 predictions 是冻结模型事实；用户展示只读取 `output_contract.display_rows`。
5. 优先直接展示 output_contract.display_rows。
6. READY 文件保持紧凑；完整审计内容位于 archive_path。
7. 正式契约固定 6 列，不得恢复旧 9 列。
8. GPT 只允许解释/审核，不得重算或覆盖 locked_prediction。

## 正式输出
固定 6 列：
球队对阵 | 胜平负场景 | 市场概率 | 比分×2及概率 | 半全场×2及概率 | 总进球及概率

语义：
- 市场概率 = 官方1X2赔率去水概率。
- 模型概率 = Draw Anchor + Side Layer 后的内部基础概率。
- CONFIRM / BALANCED / TAIL_ALERT / PASS = 市场可靠度，不是概率。
- 半全场概率 = FT 条件联合概率。
- 比分概率 = HT/FT 条件模板概率。

## V3.5.1 模型保护
- 正式基础源仅 10027S。
- Draw Layer：PD_anchor = 0.789×PD_market + 0.211×25.74%。
- Side Layer：HomeShare = (1/OH)/[(1/OH)+(1/OA)]。
- 10027S remains the base H/D/A anchor; FULL_DATA matches may use the bounded Collection1-1 challenger (SHOTS + RESULT_STABILITY + HALF_TIMING).
- Failure Detector 输出 CONFIRM / BALANCED / TAIL_ALERT / PASS。
- PASS 不等于自动反方向，只表示该市场方向不作为强推荐。
- 10027S 融合真实概率只作研究/诊断，不覆盖正式 FT 方向。
- Value Layer 只判断价值，不决定胜平负。
- HT/FT on FULL_DATA matches may use bounded Collection1-1 timing correction; 10027_ONLY matches use the frozen base split.
- Score on FULL_DATA matches may use Collection1-1 SHOTS + RESULT_STABILITY lambda correction; 10027_ONLY matches use the frozen base score layer.
- External goal-timing/profile enrichment is part of production collection, cached for reuse after first successful capture.
- GPT：EXPLANATION_ONLY。
- 禁止使用 建议下注、是否下注、page_prediction 改写预测。

## Research
Research 与 Stable 隔离。V3.5.1 本轮规则来自 2026-09-10 至 2026-09-20 开发窗口；未来比赛用于 Forward/Shadow 验证。Candidate Rule 不得自动修改 Stable。

## GitHub App 读取
`github_fetch_file` 只传：
- repository `ltaln/HH520-stable-V2`
- path `results/<request_id>.json`（prediction）或 `research-results/results/<request_id>.json`（research）
- 对应固定 ref
每次轮询重新读取；旧 OpenAPI Action 使用新的 `poll_timestamp`；不得因 404/PENDING 写入新文件。

Prediction 的旧 Action 读取接口必须传 `ref=action-results`、新的
`poll_timestamp` 和 `Accept: application/vnd.github.raw+json`。返回值应是
直接 JSON；若仍收到 `content+encoding=base64` 包装，先解码再按同一状态规则解析。

## ResponseTooLarge 防护
- prediction READY 只返回紧凑 polling envelope。
- output_contract.display_rows 与 compact predictions 保留在 results/<request_id>.json。
- 完整 analysis / decision_filter / consistency / gpt_handoff 存放在 archive/<request_id>.json。
- 正式展示不需要读取 archive。

## Plugin role
GPT / Plugin 永远是 `EXPLANATION_ONLY`；不得重新预测、修改 locked prediction、修改 Stable V3.5.1、概率算法、Failure Detector、HT/FT、比分模型、10027S 正式数据源或固定 6 列输出。
