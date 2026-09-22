import pytest

from collector.hh520_10027_parser import parse_10027s_markdown


BASE = "| 日期 | 场次 | 联赛 | 时间 | 比分 | 胜 | 平 | 负 | 主队 | 主控球率 | 客控球率 | 客队 | 半场比分 | 全场比分 | 差值 | 区间 | 平滑p | EV | 凯利比例 | 建议下注 | 是否下注 |"
FUSION = "| 日期 | 排名 | 场次 | 对阵 | 比赛结果 | 官方赔率 | 赔率判断 | 平赔率 | 融合平值 | 优势差 | 平局综合分 | 优势方 | 单选 | 融合真实概率 | 结构 | 一致 | 规律 | 评分 | 评级 | 风险 | 半全场 | 盘口 | 忽略 |"


def sample(prob="60 / 25 / 15", full_score="-"):
    row = f"| 2026-09-19 | 1 | 联赛 | 12:00 | - / {full_score} | 2 | 3 | 4 | 主队 | 50 | 50 | 客队 | - | {full_score} | 0 | 0-5 | 55% | 0.1 | 2 | 100 | ✅下注 |"
    fusion = f"| 2026-09-19 | 1 | 1 | 主队 vs 客队 | - | 2/3/4 | 正常 | 3 | 25% | 1% | 50 | 主 | 主胜 | {prob} | 强优 | ✅一致 | 🔶风控赔率 | 70 | B+ | 低 | 平/主 | 主让半一低水/一球高水 | - |"
    return "\n".join([BASE, "| --- | " * 21 + "|", row, FUSION, "| --- | " * 23 + "|", fusion])


def test_schema_and_normalization():
    match = parse_10027s_markdown(sample())[0]
    assert match["match_id"] == "1"
    assert match["market"] == {"home_odds": 2, "draw_odds": 3, "away_odds": 4}
    assert sum(match["page_probability"].values()) == pytest.approx(1)
    assert match["research_factors"]["structure"] == "强优"


def test_betting_advice_columns_are_never_stored():
    match = parse_10027s_markdown(sample())[0]
    assert "signal" not in match["value"]
    blob = repr(match)
    assert "✅下注" not in blob
    assert "建议下注" not in blob
    assert "是否下注" not in blob


def test_actual_score_is_result_label():
    match = parse_10027s_markdown(sample(full_score="2-1"))[0]
    assert match["result"] == "2-1"


def test_malformed_probability_is_ignored_not_fabricated():
    match = parse_10027s_markdown(sample("60 / nope / 15"))[0]
    assert match["page_probability"] is None


def test_missing_schema_is_rejected():
    with pytest.raises(ValueError):
        parse_10027s_markdown("not a table " * 20)


def test_duplicate_fusion_block_does_not_duplicate_matches():
    markdown = sample()
    extra = markdown[markdown.index(FUSION):]
    assert len(parse_10027s_markdown(markdown + "\n" + extra)) == 1


def test_historical_10027_layout_without_explicit_half_full_columns():
    base = "| 日期 | 场次 | 联赛 | 时间 | 比分 | 胜 | 平 | 负 | 主队 | 主控球率 | 客控球率 | 客队 | 差值 | 区间 | 平滑p | EV | 凯利比例 | 建议下注 | 是否下注 | 进攻 | 防守 | 交锋 | 状态 | 打出 | 图形 | 首发 | 复制 |"
    row = "| **2026-05-01** | **1** | 挪超 | 00:00 | 2:0 / 3:0 | 1.24 | 5.25 | 7.60 | 维京 | 55.17 | 53.17 | 罗森博格 | 2.0 | 0-5 | 53.85% | -0.3323 | 0.00% | 0.00 | ❌ 不下注 | 18 | 8 | 3.00 | 1.17 | 13 | 4 | 0.67 | 1.17 | 中 | 📊 查看 | 看首发 | 复制预测 |"
    fusion_header = "| 日期 | 排名 | 场次 | 对阵 | 比赛结果 | 官方赔率<br>主/平/客 | 标准赔率<br>主/平/客 | 风控赔率<br>主/平/客 | 赔率判断 ⇅ | 平赔率 | 融合平值 | 优势差 | 平局综合分 | 优势方 | 单选 | 融合真实概率 | 结构 | 一致 | 规律 | 评分 | 评级 | 风险 | 半全场 | 盘口 | 忽略 |"
    fusion_row = "| **2026-05-01** | **1** | 1 | 维京<br>vs<br>罗森博格 | 2:0 / 3:0 | 1.24<br>5.25<br>7.60 | 1.80<br>3.36<br>3.61 | 2.04<br>3.86<br>2.63 | 111 | **5.25** | **20.4%** | **51.24%** | 0.00 | 主 | **主胜** | 65 / 20 / 14 | 强优 | ⚠️部分 | 🔶风控赔率 | **75** | B+ | 低 | 平/主胜 | 主让半一低水/一球高水 | - |"
    markdown = "\n".join([base, "| --- | " * 27 + "|", row, fusion_header, "| --- | " * 25 + "|", fusion_row])
    match = parse_10027s_markdown(markdown)[0]
    assert match["half_score"] == "2-0"
    assert match["result"] == "3-0"
    assert match["possession"]["diff"] == pytest.approx(2.0)
    assert match["value"]["ev"] == pytest.approx(-0.3323)
    assert match["page_prediction"]["single"] == "主胜"
    assert match["research_factors"]["structure"] == "强优"


def test_10027_explicit_no_match_date_is_valid_empty_schedule():
    markdown = "📭 该日期区间暂无赛事实力数据（当前阈值 > 1）"
    assert parse_10027s_markdown(markdown) == []
