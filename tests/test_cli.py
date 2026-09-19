import json
from unittest.mock import Mock
import main

def test_invalid_command_does_not_execute(monkeypatch, capsys):
    execute = Mock()
    monkeypatch.setattr(main, "execute_prediction", execute)
    assert main.main(["预测", "2026-02-30"]) == 1
    execute.assert_not_called()
    assert "执行停止" in capsys.readouterr().err

def test_output_report_has_no_raw_page(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "execute_prediction", Mock(return_value={
        "date": "2026-09-19", "url": "url", "captured_at": "now",
        "matches": [], "predictions": [], "raw": {"secret": "large raw page"}
    }))
    target = tmp_path / "report.json"
    assert main.main(["预测 2026-09-19 全部比赛", "--output", str(target)]) == 0
    assert "raw" not in json.loads(target.read_text(encoding="utf-8"))
