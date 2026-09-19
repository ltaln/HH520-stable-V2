import pytest

from collector.hh520_parser import parse_10023s_markdown


BASE = "| 场次 | 联赛 | 时间 | 比分 | 胜 | 平 | 负 | 主队 | 主控球率 | 客控球率 | 客队 | 差值 | 区间 | 平滑p | EV | 凯利比例 | 建议下注 | 是否下注 | 进攻 | 防守 | 交锋 | 状态 | 打出 | 图形 | 首发 | 复制 |"
FUSION = "| 排名 | 场次 | 对阵 | 比赛结果 | 官方赔率 | 平赔率 | 融合平值 | 优势差 | 平局综合分 | 优势方 | 单选 | 融合真实概率 | 结构 | 一致 | 规律 | 评分 | 评级 | 风险 | 半全场 | 最可能比分 | 总进球 | 盘口 | 忽略 |"


def sample(prob="40 / 30 / 30"):
    row = "| **1** | 联赛 | 12:00 | - / - | 2 | 3 | 4 | 主队 | 50 | 50 | 客队 | 0 | 0-5 | 55% | +0.1 | 2% | 100 | ✅ 下注 | 10 | 9 | 2 | 1 | 3 | 4 | 5 | 6 |  | 查看 | 首发 | 复制 |"
    fusion = f"| 1 | 1 | 主队<br>vs<br>客队 | - / - | 2/3/4 | 3 | 25% | 1% | 50 | 主 | 主胜 | {prob} | 均衡 | 一致 | - | 70 | B | 低 | 平/主 | 1-0、2-1 | 2—3球 | - | - |"
    return "\n".join([BASE, "| --- | " * 26 + "|", row, FUSION, "| --- | " * 23 + "|", fusion])


def test_schema_and_normalization():
    match = parse_10023s_markdown(sample())[0]
    assert match["match_id"] == "1"
    assert match["market"] == {"home_odds": 2, "draw_odds": 3, "away_odds": 4}
    assert sum(match["page_probability"].values()) == pytest.approx(1)
    assert match["result"] == "- / -"
    assert match["page_prediction"]["scores"] == "1-0、2-1"
    assert "kelly" in match["value"] and "signal" in match["value"]


def test_malformed_probability_is_rejected():
    with pytest.raises(ValueError):
        parse_10023s_markdown(sample("40 / nope / 30"))


def test_missing_schema_is_rejected():
    with pytest.raises(ValueError):
        parse_10023s_markdown("not a table " * 20)

def test_duplicate_display_block_deduplicates():
    markdown = sample()
    extra = markdown[markdown.index(FUSION):]
    assert len(parse_10023s_markdown(markdown + "\n" + extra)) == 1

@pytest.mark.parametrize("old,new", [
    ("40 / 30 / 30", "-40 / 30 / 30"),
    ("40 / 30 / 30", "101 / 30 / 30"),
    ("主队<br>vs<br>客队", "错误球队<br>vs<br>客队"),
    ("| 1 | 1 | 主队", "| 1 | 999 | 主队"),
    ("| 主队 | 50", "|  | 50"),
])
def test_bad_rows_fail_closed(old, new):
    with pytest.raises(ValueError):
        parse_10023s_markdown(sample().replace(old, new))

def test_declared_count_must_match():
    with pytest.raises(ValueError):
        parse_10023s_markdown(sample() + "\n共 2 场比赛")

def test_empty_schedule_is_valid():
    assert parse_10023s_markdown("📭 该日暂无赛事实力数据（当前阈值 > 1）") == []
