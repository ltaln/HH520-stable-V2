from collector.dongqiudi_source import _header_matches


def test_dongqiudi_header_accepts_date_formats():
    for date_text in ("10-16", "10/16", "10月16日"):
        header = f"# 悉尼FC vs 西悉尼\n{date_text} 19:00\n"
        assert _header_matches(header, "2026-10-16", "悉尼FC", "西悉尼")


def test_dongqiudi_header_rejects_wrong_fixture_date():
    header = "# 悉尼FC vs 西悉尼\n10-19 19:00\n"
    assert not _header_matches(header, "2026-10-16", "悉尼FC", "西悉尼")
