import argparse
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
from collector.service import import_response
from controller.command_router import parse_command
from controller.execution_manager import execute_prediction
from formatter.output_formatter import format_prediction

ROOT = Path(__file__).resolve().parent

def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="HH520 Stable V2.1：10027s采集 + Decision Filter V2，默认不调用GPT")
    parser.add_argument("command", nargs="*", help="预测 YYYY-MM-DD 全部比赛")
    parser.add_argument("--gpt", action="store_true", help="显式启用可选GPT API分析")
    parser.add_argument("--import-response", type=Path, help="离线导入已保存的Firecrawl响应JSON")
    parser.add_argument("--output", type=Path, help="保存本次结构化结果JSON")
    args = parser.parse_args(argv)
    try:
        text = " ".join(args.command).strip() or input("请输入命令：").strip()
        command = parse_command(text)
        if args.import_response:
            raw = json.loads(args.import_response.read_text(encoding="utf-8-sig"))
            import_response(command["date"], raw)
        data = execute_prediction(command["date"], use_gpt=args.gpt)
        print(f"日期：{command['date']} | 比赛：{len(data['matches'])} | 模式：{'GPT最终推理' if args.gpt else '准备GPT输入，尚非最终预测'}")
        print(f"数据快照：{data.get('captured_at', '未知')}；同日期缓存不会自动更新")
        for prediction in data["predictions"]:
            print("\n" + format_prediction(prediction))
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            # No full raw page in the prediction report.
            report = {key: data[key] for key in ("date", "url", "captured_at", "predictions")}
            if "gpt_handoff" in data:
                report["gpt_handoff"] = data["gpt_handoff"]
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"执行停止：{exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
