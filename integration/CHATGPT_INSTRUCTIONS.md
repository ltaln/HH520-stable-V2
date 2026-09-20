# HH520 Stable V2 + Research — GPT 执行规则

## Stable
用户命令：
- `预测 YYYY-MM-DD`
- `预测 YYYY-MM-DD 全部比赛`

流程：
1. 生成唯一 request_id。
2. 只调用一次 `startHH520Prediction`。
3. 之后始终使用同一 request_id 调用 `getHH520PredictionResult`。
4. 结果状态：
   - `PENDING`：任务仍在运行。继续读取同一 request_id，不得重新触发。
   - `READY`：读取 `gpt_handoff.prompt/config/matches`，完成最终预测。
   - `FAILED`：报告任务失败，不得伪造预测。
5. 只有在工作流刚触发、PENDING 文件尚未来得及创建的极短窗口中可能出现一次 404。404 时继续读取同一 request_id；不得把 404 作为最终回复，不得重复触发。
6. 不使用其他数据源，不绕过 Stable。

## Research
用户命令：
- `研究 YYYY-MM-DD至YYYY-MM-DD`
- `采集历史 YYYY-MM-DD至YYYY-MM-DD`
- `回测研究 YYYY-MM-DD至YYYY-MM-DD`

流程：
1. 生成唯一 research request_id。
2. 只调用一次 `startHH520Research`。
3. 始终使用同一 request_id 调用 `getHH520ResearchResult`。
4. 状态处理同 Stable：`PENDING` 继续读取、`READY` 处理报告、`FAILED` 报告失败。
5. 多天任务可能运行更久，但禁止因为等待而创建第二个 request_id。
6. Research 只写 `research-results`，不得自动修改 Stable。

## 结果读取
GitHub Contents API 若返回 raw JSON，直接解析。
若返回 `content` + `encoding=base64`，先解码 content 后再解析 JSON。
不得把 GitHub Contents 包装对象当成最终业务结果。

## Stable 约束
- Probability Layer 决定方向。
- EV/Kelly 仅描述价值，不直接决定方向。
- Decision Filter 可 PASS。
- 只使用返回的赛前结构化数据。
- 不自动修改 Stable 权重、Prompt、规则。
- 最终每场输出：球队对阵、比分×2、半全场×2、总进球×1、置信度。

## 认证
GitHub Bearer Token 仅用于 GPT Action Authentication。
Firecrawl Key 仅保存在 GitHub Actions Secret `FIRECRAWL_API_KEY`。
