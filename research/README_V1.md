# HH520 Research Lab V1（改动二）

Research Lab 是 Stable V2 的独立旁路研究系统。

原则：
- Stable 只读。
- Research 不自动修改 Stable 参数、Prompt、权重或预测代码。
- 历史数据进入研究前先经过 Historical Sanitizer。
- 研究结论只能形成 Candidate Rule，必须人工审核后才可能进入未来开发版。
- 不把赛后比分、结算、事件等字段作为赛前特征。
- 无真实赛果时，不伪造回测命中率。

支持的研究能力：
- 历史区间采集
- Historical Sanitizer
- Backtest 基础评估（沿用 evaluator.py）
- Hidden Model Reverse（研究观察）
- Risk Analysis
- League DNA
- Team DNA
- Causal Analysis（仅假设层）
- Confidence Analysis
- 统一 Research Report

CLI：

```bash
python -m research.runner 2026-09-01 2026-09-20 --output research_report.json
```

离线模式：

```bash
python -m research.runner 2026-09-01 2026-09-20 --input historical.json --output research_report.json
```

Research 输出不得直接写回 Stable。
