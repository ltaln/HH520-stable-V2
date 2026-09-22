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
2. Authentication 选择 Bearer。
3. 使用 fine-grained GitHub PAT：
   - Repository access：仅 `HH520-stable-V2`
   - Actions：Read and write
   - Contents：Read
4. Instructions 使用 `integration/CHATGPT_INSTRUCTIONS.md`。

## 重要规则
READY 后：
- 顶层 `predictions` 是冻结 Stable V3.2 的正式结果。
- `gpt_handoff` 仅用于解释和审核。
- GPT 不得重新预测，不得覆盖方向、比分、半全场、总进球或置信度。

## 一句命令
`预测 YYYY-MM-DD 全部比赛`
