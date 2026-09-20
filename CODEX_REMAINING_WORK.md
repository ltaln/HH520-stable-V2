# HH520 Remaining Work for Codex

## Goal
Finish only the remaining integration/verification work for:
1. Stable V2 GitHub Actions + GPT
2. Research Lab V1 (改动二)

Do not redesign either system.

## A. Stable V2 remaining
1. Run and fix all tests for current main.
2. Verify .github/workflows/hh520-predict.yml can:
   - receive request_id + command
   - read FIRECRAWL_API_KEY
   - run main.py
   - publish results/<request_id>.json to action-results
3. Verify integration/chatgpt-action.openapi.json matches GitHub API and can:
   - dispatch hh520-predict.yml
   - read raw JSON from action-results
4. Do one real end-to-end test.
5. If a logged-in ChatGPT browser session is available, finish GPT Action import + Bearer token binding. If login/2FA/security confirmation is required, stop only for that confirmation.

## B. Research Lab V1 remaining
Current files already exist:
- research/sanitizer.py
- research/lab.py
- research/runner.py
- research/README_V1.md
- .github/workflows/hh520-research.yml
- tests/test_research_lab_v1.py

Finish:
1. Run tests and fix syntax/runtime issues.
2. Verify hh520-research.yml can collect a date range and publish to research-results.
3. Add Research endpoints to GPT OpenAPI without changing the existing Stable endpoints:
   - dispatch hh520-research.yml
   - read research-results/results/<request_id>.json
4. Add GPT instruction routing for commands:
   - 研究 YYYY-MM-DD至YYYY-MM-DD
   - 采集历史 YYYY-MM-DD至YYYY-MM-DD
   - 回测研究 YYYY-MM-DD至YYYY-MM-DD
   Research must remain read-only to Stable.
5. Perform one real Research workflow test.

## Hard rules
- Do not modify Stable model weights, Stable prompt logic, prediction algorithms, or data-source rules.
- Do not auto-promote Candidate Rule into Stable.
- Do not add a server or database.
- Do not commit any Firecrawl key, GitHub token, or OpenAI key.
- Research output must stay isolated from Stable output.

## Final acceptance
Report only:
- Stable Actions: PASS/FAIL
- Stable GPT Action: PASS/FAIL
- Research Actions: PASS/FAIL
- Research GPT Action: PASS/FAIL
- pytest result
- end-to-end test result
- final commit SHA
- READY_FOR_USE or NOT_READY

Execute directly. Do not ask the user questions except for unavoidable login/2FA/security confirmation.
