from collector.hh520_10027_parser import parse_10027s_markdown


def test_10027_parser_preserves_possession_and_dynamic_fusion_fields():
    md = """
| 日期 | 场次 | 联赛 | 时间 | 比分 | 胜 | 平 | 负 | 主队 | 主控球率 | 客控球率 | 客队 | 半场比分 | 全场比分 | 差值 | 区间 | 平滑p | EV | 凯利比例 | 建议下注 | 是否下注 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-08-01 | 1 | 英超 | 20:00 | 1-0 / 2-1 | 1.80 | 3.40 | 4.20 | A | 58% | 42% | B | 1-0 | 2-1 | 16 | 15-20 | 0.64 | 0.12 | 0.08 | 主 | 是 |
| 日期 | 排名 | 场次 | 对阵 | 比赛结果 | 盘口 | 主队进攻 | 客队进攻 | 主队防守 | 客队防守 | 主队交锋 | 客队交锋 | 主队状态 | 客队状态 | 主水 | 客水 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-08-01 | 1 | 1 | A vs B | 主胜 | -0.5 | 72 | 55 | 68 | 50 | 61 | 44 | 70 | 48 | 0.88 | 0.96 |
"""
    m=parse_10027s_markdown(md)[0]
    assert m["possession"]["home"] == 58
    assert m["possession"]["away"] == 42
    assert m["possession"]["diff"] == 16
    assert m["possession"]["interval"] == "15-20"
    assert m["possession"]["smooth_p"] == 0.64
    assert m["research_factors"]["home_attack"] == 72
    assert m["research_factors"]["away_defense"] == 50
    assert m["research_factors"]["home_water"] == 0.88
    assert m["raw_fusion_fields"]["主队状态"] == "70"


def test_10027_parser_reads_two_level_grouped_base_factors():
    md = """
| 日期 | 场次 | 联赛 | 时间 | 比分 | 胜 | 平 | 负 | 主队 | 主控球率 | 客控球率 | 客队 | 半场比分 | 全场比分 | 差值 | 区间 | 平滑p | EV | 凯利比例 | 建议下注 | 是否下注 | 进攻 |  | 防守 |  | 交锋 |  | 状态 |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 主 | 客 | 主 | 客 | 主 | 客 | 主 | 客 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-08-01 | 1 | 英超 | 20:00 | 1-0 / 2-1 | 1.80 | 3.40 | 4.20 | A | 58% | 42% | B | 1-0 | 2-1 | 16 | 15-20 | 0.64 | 0.12 | 0.08 | 主 | 是 | 10 | 13 | 1.50 | 1.83 | 7 | 7 | 1.17 | 0.83 |
"""
    m = parse_10027s_markdown(md)[0]
    f = m["research_factors"]
    assert f["home_attack"] == 10
    assert f["away_attack"] == 13
    assert f["home_defense"] == 1.50
    assert f["away_defense"] == 1.83
    assert f["home_h2h"] == 7
    assert f["away_h2h"] == 7
    assert f["home_form"] == 1.17
    assert f["away_form"] == 0.83
