"""Markdown renderer for Stable V3 calibration research."""


def _pct(value):
    return "-" if value is None else f"{value * 100:.1f}%"


def _candidate_line(name, candidate):
    if not candidate:
        return f"- {name}: 样本不足，暂不生成 Candidate Rule"
    threshold = candidate["threshold"]
    if isinstance(threshold, float):
        threshold = f"{threshold:.3f}"
    return (
        f"- {name}: {candidate['operator']} {threshold}; "
        f"n={candidate['sample_count']}; coverage={_pct(candidate['coverage'])}; "
        f"accuracy={_pct(candidate['accuracy'])}; "
        f"delta={_pct(candidate['delta_vs_all'])}; **CANDIDATE_ONLY**"
    )


def render_calibration_report(calibration, start=None, end=None):
    sample = calibration.get("sample") or {}
    lines = [
        "# HH520 Stable V3 Calibration Report",
        "",
        f"- 时间范围：{start or '-'} 至 {end or '-'}",
        f"- 有效样本：{sample.get('sample_count', 0)}",
        f"- 日期数：{sample.get('date_count', 0)}",
        f"- 当前方向准确率：{_pct(sample.get('accuracy'))}",
        "- Stable权限：READ_ONLY",
        "- 自动修改Stable：禁止",
        "",
        "## Candidate Thresholds",
        "",
        _candidate_line("Risk Score 最大阈值", (calibration.get("risk_score") or {}).get("candidate")),
        _candidate_line("Probability Margin 最小阈值", (calibration.get("probability_margin") or {}).get("candidate")),
        _candidate_line("Value Edge 最小阈值", (calibration.get("value_edge") or {}).get("candidate")),
        "",
        "## Match Type 独立阈值",
        "",
    ]
    for match_type, payload in (calibration.get("match_type") or {}).items():
        overall = payload.get("overall") or {}
        lines += [
            f"### {match_type}",
            f"- n={overall.get('sample_count', 0)}; accuracy={_pct(overall.get('accuracy'))}; coverage={_pct(overall.get('coverage'))}",
            _candidate_line("Risk", (payload.get("candidate") or {}).get("max_risk")),
            _candidate_line("Margin", (payload.get("candidate") or {}).get("min_margin")),
            _candidate_line("Edge", (payload.get("candidate") or {}).get("min_edge")),
            "",
        ]

    errors = (calibration.get("output_error") or {}).get("error_counts") or {}
    lines += ["## 比分 / 半全场 / 总进球生成误差", ""]
    if errors:
        lines += [f"- {name}: {count}" for name, count in errors.items()]
    else:
        lines.append("- 当前样本没有可统计的输出误差，或对应预测字段覆盖不足。")

    lines += [
        "",
        "## 升级策略",
        "",
        "本报告只生成 Candidate Rules。任何阈值或生成逻辑变更都必须人工审核后，才可进入 Stable V3.x。",
        "",
    ]
    return "\n".join(lines)
