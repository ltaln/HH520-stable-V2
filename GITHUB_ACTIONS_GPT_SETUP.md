# GitHub Actions + GPT 接入状态

## 已完成的代码侧接入

- `.github/workflows/hh520-predict.yml`：GPT 触发的正式预测准备工作流。
- `.github/workflows/ci.yml`：main / PR 自动执行 pytest。
- `integration/chatgpt-action.openapi.json`：GPT 直接调用 GitHub API，不需要自建 HTTPS 服务。
- `integration/CHATGPT_INSTRUCTIONS.md`：GPT 固定执行规则。
- 运行结果写入独立 `action-results` 分支的 `results/<request_id>.json`，不会修改 Stable 正式模型。

## GitHub 侧必须存在

Repository → Settings → Secrets and variables → Actions：
- `FIRECRAWL_API_KEY`

Repository → Settings → Actions → General → Workflow permissions：
- Read and write permissions

## GPT 侧一次性设置

1. 导入 `integration/chatgpt-action.openapi.json`。
2. Authentication 选择 Bearer。
3. 使用 GitHub fine-grained PAT：
   - Repository access：只选 `HH520-stable-V2`
   - Actions：Read and write
   - Contents：Read
4. Instructions 使用 `integration/CHATGPT_INSTRUCTIONS.md`，并保留原 Stable V2 Prompt 的正式规则。

完成后，手机或电脑只需发送：
`预测 2026-09-20 全部比赛`
