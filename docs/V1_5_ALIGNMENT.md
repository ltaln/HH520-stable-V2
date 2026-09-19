# V1.5逐文件对齐审计

基准ZIP SHA-256：13398534179a506d106eb861281f3f9ab2e968932e41ff74d2e6f46d749dcef6

仅以用户提供V1.5包为规格，不引入V3规则或其他项目规范。

## 发现并修正的偏差

1. 旧版GPT只能保留网页比分；与原GPT角色冲突。已恢复按结构化数据生成最终比分/半全场。
2. 旧版硬加60%置信度上限；无原包依据，已移除，保留原confidence函数。
3. 旧版仅有网页比分的比赛进入GPT且不提供team_dna；已改为有效概率场次进入模型并提供完整分析。
4. 旧版默认网页复制结果被当作完整模型完成；现在默认只准备GPT输入，状态READY_FOR_GPT。
5. 旧局域网页面非原包ChatGPT入口，且启动未完成验证；已移出正式包，不再称其已上线。
6. 旧版改写GPT角色文档、README和依赖列表；已还原原文，操作细节另写RUNBOOK。
7. 旧setup脚本可能测试失败仍打印READY；现检查进程退出码。

## 14条必须项

| 原包条款 | 要求 | 状态/证据 |
| --- | --- | --- |
| 1–2 | 10023s唯一入口与固定URL | 已实现；source/URL常量与验证 |
| 3、5–7 | 仅v2/scrape、markdown、basic；不用其他页面/crawl | 已实现；真实记录及请求契约测试 |
| 4 | 日期最多一次抓取，本地缓存优先 | 已实现；原始响应先保存、请求账本、并发和失败测试 |
| 8–9 | 主链与research隔离，研究不改Stable | 已实现；独立离线入口，无自动回填/调参 |
| 10 | EV/Kelly保留但不决定方向 | 已实现；仅作为价值层输入 |
| 11 | 真实markdown字段映射，不猜列 | 已实现；9/18、9/19实样本；未证实口径明确保留 |
| 12 | URL、路由、市场基线、缓存测试 | 已实现；测试通过 |
| 13 | 手机/电脑ChatGPT一句命令 | 代码及配置材料已准备；GitHub、HTTPS部署和ChatGPT真实端到端未完成 |
| 14 | 不提交.env、缓存、历史原始数据 | 已实现；忽略规则与发行ZIP检查 |

## 原始文件逐项比较

| 文件 | 当前状态 |
| --- | --- |
| DEPLOYMENT_STEPS.md | 原文保留 |
| HH520-Stable-V2/.env.example | 实现补齐/修正 |
| HH520-Stable-V2/.gitignore | 实现补齐/修正 |
| HH520-Stable-V2/analysis/confidence.py | 实现补齐/修正 |
| HH520-Stable-V2/analysis/match_analysis.py | 原文保留 |
| HH520-Stable-V2/cache/.gitkeep | 原文保留 |
| HH520-Stable-V2/CODEX_ONE_SHOT_EXECUTION.md | 原文保留 |
| HH520-Stable-V2/collector/cache_manager.py | 实现补齐/修正 |
| HH520-Stable-V2/collector/firecrawl_client.py | 实现补齐/修正 |
| HH520-Stable-V2/collector/hh520_parser.py | 实现补齐/修正 |
| HH520-Stable-V2/collector/service.py | 实现补齐/修正 |
| HH520-Stable-V2/collector/url_builder.py | 实现补齐/修正 |
| HH520-Stable-V2/config/stable.yaml | 原文保留 |
| HH520-Stable-V2/controller/command_router.py | 实现补齐/修正 |
| HH520-Stable-V2/controller/execution_manager.py | 实现补齐/修正 |
| HH520-Stable-V2/engine/decision_filter.py | 实现补齐/修正 |
| HH520-Stable-V2/engine/market_baseline.py | 实现补齐/修正 |
| HH520-Stable-V2/engine/probability_layer.py | 实现补齐/修正 |
| HH520-Stable-V2/engine/value_layer.py | 原文保留 |
| HH520-Stable-V2/FIRECRAWL_COST_RULES.md | 原文保留 |
| HH520-Stable-V2/formatter/output_formatter.py | 实现补齐/修正 |
| HH520-Stable-V2/GPT_INTEGRATION.md | 原文保留 |
| HH520-Stable-V2/main.py | 实现补齐/修正 |
| HH520-Stable-V2/prompts/HH520_Stable_V2_Prediction_Prompt.md | 原文保留 |
| HH520-Stable-V2/README.md | 原文保留 |
| HH520-Stable-V2/requirements.txt | 原文保留 |
| HH520-Stable-V2/research/evaluator.py | 实现补齐/修正 |
| HH520-Stable-V2/research/README.md | 实现补齐/修正 |
| HH520-Stable-V2/tests/test_core.py | 原文保留 |
| PACKAGE_MANIFEST.md | 原文保留 |

## 新增文件及范围

新增文件用于实现原包缺失功能、测试、或原包要求的ChatGPT命令入口；不是新增数据源或新模型。

- HH520-Stable-V2/COMPLETION_REPORT.md
- HH520-Stable-V2/controller/chatgpt_action.py
- HH520-Stable-V2/docs/PARSER_SCHEMA.md
- HH520-Stable-V2/docs/RUNBOOK.md
- HH520-Stable-V2/docs/SOURCES.md
- HH520-Stable-V2/docs/V1_5_ALIGNMENT.md
- HH520-Stable-V2/integration/chatgpt-action.openapi.json
- HH520-Stable-V2/integration/CHATGPT_INSTRUCTIONS.md
- HH520-Stable-V2/prediction/__init__.py
- HH520-Stable-V2/prediction/builder.py
- HH520-Stable-V2/prediction/gpt.py
- HH520-Stable-V2/pytest.ini
- HH520-Stable-V2/run.cmd
- HH520-Stable-V2/setup.ps1
- HH520-Stable-V2/tests/test_action.py
- HH520-Stable-V2/tests/test_cli.py
- HH520-Stable-V2/tests/test_collection.py
- HH520-Stable-V2/tests/test_engine.py
- HH520-Stable-V2/tests/test_gpt.py
- HH520-Stable-V2/tests/test_parser.py
- HH520-Stable-V2/tests/test_prediction.py
- HH520-Stable-V2/tests/test_research.py

## 新增文件的必要性

- prediction/：原包GPT推理调用、校验和缓存。
- controller/chatgpt_action.py、integration/：原包ChatGPT入口的最小接入层；不附加独立网站。
- tests/、pytest.ini：原包规定的测试及解析/推理/缓存回归。
- docs/、报告：实际映射、变更依据、操作和未完成项。
- run.cmd、setup.ps1：本地运行和依赖检查辅助，不改变模型。

## 已有增强保留理由

- 原始Parser占位会把整页当成一条比赛；严格解析、异常失败是原包明确要求。
- 已出比分场次跳过仅防止赛果泄漏，不是假设模型预测正确。
- 日期/赔率/概率校验、坏缓存停止、并发请求账本是采集/测试要求的必要实现。
- 原confidence规则与Decision Filter集中度阈值保留；没有新添固定特征权重。

## 尚缺的真实样本解释

平滑p对应哪个事件；进攻/防守/交锋/状态指标的统计窗口和单位。保留原数值，不猜事件、不调权重。
已映射当前真实模板；模板变动需复核。无60–90天标签集，不能宣称历史效果验证通过。

## 不能冒充完成的外部步骤

GitHub仓库已指定：https://github.com/ltaln/HH520-stable-V2 。仍需HTTPS部署环境及自定义GPT接入权限。
目前未向公网发布任何服务，不能宣称手机ChatGPT一句话已在线跑通。
如果采用ChatGPT侧推理，不需要另行配置OPENAI_MODEL；程序侧API模式才需要。

Action部署要求依据：https://developers.openai.com/api/docs/actions/production
