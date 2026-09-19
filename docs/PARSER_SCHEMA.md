# 10023s parser schema

`collector.hh520_parser.parse_10023s_markdown(markdown)` 返回比赛对象列表。
解析器要求基础表和融合表表头存在；基础行必须为 30 列，坏行、缺列、球队不匹配和融合表引用不存在的场次都会抛出 `ValueError`。

每个对象包含：

- `match_id`, `home_team`, `away_team`, `league`, `kickoff`：场次及基本资料。
- `result`：基础表原始比分；预测流程仅用于判断是否跳过，不能作为模型输入或预测答案。
- `market.home_odds`, `market.draw_odds`, `market.away_odds`：三项赔率数字。
- `page_probability`：融合表中完整的三项“融合真实概率”按总和归一后的 `{home, draw, away}`。没有融合记录时为 `null`。基础表的“平滑p”是未知目标概率，只保留为页面字段来源，不能填充 1X2。
- `value`：`ev`, `kelly`, `kelly_fraction`, `stake`, `signal`（并保留 `bet` 别名）。
- `team_dna`：`attack`, `defense`, `head_to_head`, `form`，每项含 `home`、`away` 数字；这些值来自多层表头展开后的 8 列。
- `page_prediction`：融合页推演字段。`scores` 和 `htft`、`total_goals` 来自预测区；`score_options` 是解析后的比分数组。基础比分不会复制到这里，以防赛果泄漏。

融合区块按场次去重，识别1C后缀；重复记录实质内容冲突会报错。页面总场次数存在时必须与行数匹配。
page_context保留控球率、差值、区间及smoothed_p，但未确认平滑p对应事件，不参与方向计算。
真实样本解析为27场基础比赛、13场有融合概率的比赛。进攻/防守等数值的统计口径尚未证实，不设权重。
