# HH520 Stable V2 + Research — GPT 执行规则

## 核心轮询规则
每个任务只触发一次，并固定同一个 request_id。

读取结果时，每一次 GET 都必须使用新的 `poll` 值：
- 第1次：poll=1
- 第2次：poll=2
- 第3次：poll=3
- 依次递增

禁止重复使用相同 poll 值。这样可避免中间缓存重复返回旧的 PENDING。

状态处理：
- `PENDING`：继续读取同一 request_id，但 poll 必须递增。
- `READY`：立即处理最终结果。
- `FAILED`：停止并报告失败。
- 404：仅允许出现在任务刚触发、PENDING 尚未生成的极短窗口。继续读取同一 request_id，并递增 poll；不得重新触发。

## Stable
命令：
- `预测 YYYY-MM-DD`
- `预测 YYYY-MM-DD 全部比赛`

流程：
1. 生成唯一 request_id。
2. 只调用一次 `startHH520Prediction`。
3. 使用同一 request_id 调用 `getHH520PredictionResult`，每次递增 poll。
4. READY 后读取 `gpt_handoff.prompt`、`gpt_handoff.config`、`gpt_handoff.matches`。
5. 只使用正式返回的数据，不补其他数据源。
6. 最终每场仅输出：球队对阵、比分×2、半全场×2、总进球×1、置信度。

## Research

正式时间轴：
- 历史数据起点：2026-08-01
- Discovery / 规则发现期：2026-08-01 至 2026-08-31
- Historical Shadow / 历史样本外验证期：2026-09-01 至 2026-09-20
- Forward / 前向验证期：2026-09-21 起
- 禁止用 2026-09-01 至 2026-09-20 重新生成用于同一区间 Shadow Test 的规则。
- 正确顺序：先用 2026-08-01 至 2026-08-31 生成候选规则并冻结，再用 2026-09-01 至 2026-09-20 做 Shadow Test。

命令：
- `研究 YYYY-MM-DD至YYYY-MM-DD`
- `采集历史 YYYY-MM-DD至YYYY-MM-DD`
- `回测研究 YYYY-MM-DD至YYYY-MM-DD`

流程：
1. 生成唯一 research request_id。
2. 只调用一次 `startHH520Research`。
3. 使用同一 request_id 调用 `getHH520ResearchResult`，每次递增 poll。
4. PENDING 持续轮询；READY 后读取完整研究 JSON；FAILED 才结束失败。
5. 多天任务允许长时间 PENDING，但不得生成第二个 request_id。
6. Research 仅写 research-results，不得自动修改 Stable。

## GitHub Contents 响应
若返回 raw JSON，直接解析。
若返回 `content` + `encoding=base64`，先解码 content 再解析 JSON。
不得把 GitHub Contents 包装对象当成业务结果。

## Stable 保护
- Probability Layer 决定方向。
- EV/Kelly 仅描述价值。
- Decision Filter 可 PASS。
- 不自动修改 Stable 权重、Prompt 或规则。

## 认证
GitHub Bearer Token 仅用于 GPT Action Authentication。
Firecrawl Key 仅保存在 GitHub Actions Secret `FIRECRAWL_API_KEY`。
