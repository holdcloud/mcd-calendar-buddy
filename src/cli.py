"""麦麦日历助手 — 命令行入口。

用法：
    python src/cli.py query                    # 查询当月麦当劳活动
    python src/cli.py query --date 2026-11-01  # 查询指定日期附近的活动
    python src/cli.py sync                     # 同步当月活动到 macOS 日历（默认提前 1 天提醒）
    python src/cli.py sync --remind-days 2     # 提前 2 天提醒
    python src/cli.py export -o events.ics     # 导出 .ics（任何平台可用）

Token 通过环境变量 MCD_MCP_TOKEN 注入。
"""

import argparse
import json
import os
import sys

# 允许 python src/cli.py 直接运行
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from calendar_sync import DEFAULT_CALENDAR_NAME, export_ics, sync  # noqa: E402
from event_builder import dedupe, parse_campaign_markdown  # noqa: E402
from mcd_client import MCPClientError, McDonaldMCPClient  # noqa: E402


def _client() -> McDonaldMCPClient:
    try:
        return McDonaldMCPClient()
    except MCPClientError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)


def _fetch_events(date: str | None):
    client = _client()
    markdown = client.fetch_campaign_calendar(date)
    return dedupe(parse_campaign_markdown(markdown))


def cmd_query(args) -> int:
    events = _fetch_events(args.date)
    if not events:
        print("未查询到活动。")
        return 0
    print(f"共查询到 {len(events)} 条活动：\n")
    for e in events:
        kind = "全天" if e.all_day else e.start.strftime("%H:%M")
        print(f"  [{e.start:%Y-%m-%d} {kind}] {e.title}")
        if e.description:
            first_line = e.description.splitlines()[0][:60]
            print(f"      {first_line}…")
    return 0


def cmd_sync(args) -> int:
    events = _fetch_events(args.date)
    if not events:
        print("未查询到活动，无需同步。")
        return 0
    try:
        result = sync(
            events,
            calendar_name=args.calendar,
            remind_days_before=args.remind_days,
        )
    except RuntimeError as exc:
        print(f"同步失败: {exc}", file=sys.stderr)
        return 2
    print(f"✅ 新增 {result['synced']} 条，跳过已同步 {result['skipped']} 条")
    if result["fallback_ics"]:
        print(f"当前平台不支持直接写入 macOS 日历，已导出: {result['fallback_ics']}")
        print("双击该 .ics 文件即可导入日历应用。")
    else:
        print(f"事件已写入日历「{args.calendar}」，到点自动提醒。")
    return 0


def cmd_export(args) -> int:
    events = _fetch_events(args.date)
    if not events:
        print("未查询到活动，未生成文件。")
        return 0
    path = export_ics(events, args.output, remind_days_before=args.remind_days)
    print(f"✅ 已导出 {len(events)} 条活动到 {path}")
    print("双击该文件即可导入 macOS 日历 / iOS 日历 / Google 日历。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcd-calendar-buddy",
        description="麦麦日历助手：把麦当劳 MCP 营销活动日历同步到 macOS 日历",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_date_opt(p):
        p.add_argument("--date", help="查询基准日期 yyyy-MM-dd（默认当月全部活动）")

    p_query = sub.add_parser("query", help="查询麦当劳活动")
    add_date_opt(p_query)
    p_query.set_defaults(func=cmd_query)

    p_sync = sub.add_parser("sync", help="同步活动到 macOS 日历")
    add_date_opt(p_sync)
    p_sync.add_argument("--remind-days", type=int, default=1, help="提前提醒天数（默认 1）")
    p_sync.add_argument("--calendar", default=DEFAULT_CALENDAR_NAME, help="目标日历名称")
    p_sync.set_defaults(func=cmd_sync)

    p_export = sub.add_parser("export", help="导出 .ics 文件")
    add_date_opt(p_export)
    p_export.add_argument("-o", "--output", default="mcd-events.ics", help="输出路径")
    p_export.add_argument("--remind-days", type=int, default=1, help="提前提醒天数（默认 1）")
    p_export.set_defaults(func=cmd_export)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
