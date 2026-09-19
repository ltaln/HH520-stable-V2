# 离线评估

从项目根目录运行：

```powershell
py -3 -m research.evaluator historical.json --output metrics.json
```

输入是记录数组，或包含records/matches数组的对象。每条记录示例：

```json
{"date":"2026-01-01","market":{"home_odds":2.0,"draw_odds":3.5,"away_odds":4.0},"actual":"home","probabilities":{"home":0.5,"draw":0.3,"away":0.2},"status":"LOCAL"}
```

示例仅展示结构，不是真实数据。actual取home/draw/away；probabilities为待验证候选模型输出，PASS表示放弃。

- baseline：所有有效赔率和标签记录的accuracy、log loss、Brier。
- candidate与baseline_on_candidate：相同有效、非PASS候选子集的公平比较。
- coverage：有效赔率且有标签记录数 / 输入记录数。
- candidate_coverage：有效非PASS候选数 / 有效赔率且有标签记录数。
- pass_rate：显式PASS数 / 有效赔率且有标签记录数。
- invalid_or_unlabelled_count：坏赔率、无效记录或缺标签数。
- invalid_candidate_count：非PASS但候选概率缺失/非法数。

按日期排序并给出范围；该排序不意味着已经完成样本外训练验证。
当前未提供60–90天真实赛果数据；比分/半全场命中率、特征消融和预测效果仍未验证。
本模块不联网、不训练、不自动修改Stable。
