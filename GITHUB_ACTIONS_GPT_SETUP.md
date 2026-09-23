# GitHub Actions + ChatGPT 接入状态 — HH520 Stable V3.2

## 已完成
- `.github/workflows/hh520-predict.yml`：Stable V3.2 正式预测工作流。
- `.github/workflows/ci.yml`：main / PR 自动执行 pytest。
- `integration/chatgpt-action.openapi.json`：ChatGPT 通过 GitHub Actions 触发预测，不需要自建 HTTPS 服务。
- `integration/CHATGPT_INSTRUCTIONS.md`：Stable V3.2 固定执行规则。
- `prompts/HH520_Stable_V3_2_Prediction_Prompt.md`：GPT 仅解释/审核。
- 预测结果写入 `action-results/results/<request_id>.json`。

## GitHub 侧
Repository → Settings → Secrets and variables → Actions：
- `FIRECRAWL_API_KEY`

Repository → Settings → Actions → General → Workflow permissions：
- Read and write permissions

## ChatGPT 侧
1. 导入 `integration/chatgpt-action.openapi.json`。
2. 在 GPT 编辑器的 Action Authentication 中选择：
   - 类型：`API key`
   - Auth Type：`Bearer`
   - Header name：`Authorization`
   - API key：只粘贴 GitHub PAT 本身，不要手动添加 `Bearer ` 前缀；编辑器会生成 `Authorization: Bearer <PAT>`。
3. 使用 fine-grained GitHub PAT：
   - Repository access：仅 `HH520-stable-V2`
   - Actions：Read and write
   - Contents：Read
4. 保存 Action 后，在 Preview 中确认请求的实际头部是 `Authorization: Bearer <PAT>`，并确认 dispatch 返回 `204 No Content`。
5. Instructions 使用 `integration/CHATGPT_INSTRUCTIONS.md`。

### 连接故障定位

- `401`：Bearer token 未注入、前缀被重复添加，或 PAT 已失效。
- `403`：PAT 没有该仓库的 Actions/Contents 权限，或组织策略阻止 Actions。
- `404`：仓库、workflow 文件名或 `ref=main` 不匹配。
- `204`：dispatch 已被 GitHub 接收；保持同一个 `request_id`，继续轮询 `action-results`，不要重复 dispatch。

## 重要规则
READY 后：
- 顶层 `predictions` 是冻结 Stable V3.2 的正式结果。
- `gpt_handoff` 仅用于解释和审核。
- GPT 不得重新预测，不得覆盖方向、比分、半全场、总进球或置信度。

## 一句命令
`预测 YYYY-MM-DD 全部比赛`
