"""macOS 日历同步器。

职责：
- 方案 A（主选）：通过 AppleScript (osascript) 将事件写入 Calendar.app 指定日历
- 方案 B（兜底）：导出 .ics 文件供手动导入（任何平台可用）
- 同步去重：本地状态文件记录已同步 UID（~/.mcd-calendar-buddy/synced_uids.json）

仅使用 Python 标准库，无第三方依赖。
"""

import json
import os
import platform
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from event_builder import CalendarEvent

STATE_DIR = Path.home() / ".mcd-calendar-buddy"
STATE_FILE = STATE_DIR / "synced_uids.json"
DEFAULT_CALENDAR_NAME = "麦麦活动"


# ---------------------------------------------------------------------- #
# 本地 UID 状态（去重）
# ---------------------------------------------------------------------- #
def load_synced_uids() -> set:
    if not STATE_FILE.exists():
        return set()
    try:
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return set()


def save_synced_uids(uids: set) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(sorted(uids), ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


def filter_new(events: list[CalendarEvent]) -> tuple[list[CalendarEvent], list[CalendarEvent]]:
    """把事件分为 (新增, 已同步过) 两组。"""
    synced = load_synced_uids()
    fresh = [e for e in events if e.uid not in synced]
    skipped = [e for e in events if e.uid in synced]
    return fresh, skipped


# ---------------------------------------------------------------------- #
# 智能提醒策略
# ---------------------------------------------------------------------- #
def smart_alarms(event: CalendarEvent, remind_days_before: int = 1) -> list[int]:
    """按事件类型生成提醒触发点（返回相对事件开始的提前分钟数，负数=提前）。

    - 定时事件（如 10:45 开售）：提前 N 天 + 提前 1 小时各提醒一次
    - 全天事件：提前 N 天的 09:00 提醒一次
    """
    if not event.all_day:
        return sorted({-(remind_days_before * 24 * 60), -60})
    target = event.start.replace(hour=9, minute=0) - _days(remind_days_before - 1)
    minutes = int((event.start - target).total_seconds() // 60)
    return [minutes] if minutes > 0 else [-60]


def _days(n: int) -> timedelta:
    return timedelta(days=n)


# ---------------------------------------------------------------------- #
# 方案 B：.ics 导出（跨平台兜底）
# ---------------------------------------------------------------------- #
def _ics_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _ics_dt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def build_ics(events: list[CalendarEvent], remind_days_before: int = 1) -> str:
    """把事件列表构建为 iCalendar (.ics) 文本。"""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//mcd-calendar-buddy//CN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:麦麦活动",
    ]
    now = _ics_dt(datetime.now())
    for e in events:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{e.uid}@mcd-calendar-buddy",
            f"DTSTAMP:{now}",
            f"SUMMARY:{_ics_escape(e.title)}",
        ]
        if e.all_day:
            lines.append(f"DTSTART;VALUE=DATE:{e.start:%Y%m%d}")
            lines.append(f"DTEND;VALUE=DATE:{e.end:%Y%m%d}")
        else:
            lines.append(f"DTSTART:{_ics_dt(e.start)}")
            lines.append(f"DTEND:{_ics_dt(e.end)}")
        if e.description:
            lines.append(f"DESCRIPTION:{_ics_escape(e.description[:1800])}")
        for minutes in smart_alarms(e, remind_days_before):
            lines += [
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"TRIGGER:-PT{abs(minutes)}M",
                f"DESCRIPTION:{_ics_escape(e.title)}",
                "END:VALARM",
            ]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def export_ics(events: list[CalendarEvent], output: str, remind_days_before: int = 1) -> Path:
    path = Path(output).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_ics(events, remind_days_before).encode("utf-8"))
    return path


# ---------------------------------------------------------------------- #
# 方案 A：AppleScript 写入 Calendar.app（仅 macOS）
# ---------------------------------------------------------------------- #
def _applescript_quote(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _ensure_calendar_exists(script: list[str], calendar_name: str) -> None:
    script.append(
        f'''
        if not (exists calendar "{_applescript_quote(calendar_name)}") then
            make new calendar with properties {{name:"{_applescript_quote(calendar_name)}"}}
        end if'''
    )


def _event_applescript(e: CalendarEvent, remind_days_before: int) -> str:
    desc = e.description
    if e.notes:
        desc = f"{desc}\n[来源: 麦麦日历助手 · {'; '.join(e.notes)}]"
    props = (
        f'summary:"{_applescript_quote(e.title)}", '
        f'start date:date "{e.start:%Y-%m-%d %H:%M:%S}", '
        f'end date:date "{e.end:%Y-%m-%d %H:%M:%S}", '
        f'description:"{_applescript_quote(desc)}"'
    )
    alarms = ""
    for minutes in smart_alarms(e, remind_days_before):
        alarms += (
            f"\n            make new display alarm at end of theEvent "
            f"with properties {{trigger interval:{minutes}}}"
        )
    return f'''
        tell calendar "{_applescript_quote(DEFAULT_CALENDAR_NAME)}"
            set theEvent to make new event with properties {{{props}}}{alarms}
        end tell'''


def sync_to_macos_calendar(
    events: list[CalendarEvent],
    calendar_name: str = DEFAULT_CALENDAR_NAME,
    remind_days_before: int = 1,
) -> int:
    """通过 AppleScript 把事件写入 macOS 日历，返回写入数量。"""
    if platform.system() != "Darwin":
        raise RuntimeError(
            "sync_to_macos_calendar 仅支持 macOS。"
            "其他平台请使用 export_ics 导出 .ics 后手动导入日历。"
        )
    if not events:
        return 0
    script_parts = [
        'tell application "Calendar"',
        "    activate",
    ]
    _ensure_calendar_exists(script_parts, calendar_name)
    for e in events:
        script_parts.append(_event_applescript(e, remind_days_before))
    script_parts.append("end tell")
    script = "\n".join(script_parts)

    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "not allowed" in stderr.lower() or "-1743" in stderr:
            raise RuntimeError(
                "macOS 拒绝了日历自动化权限。请在 系统设置 > 隐私与安全性 > "
                "自动化 中允许终端/Python 控制『日历』，然后重试。"
            )
        raise RuntimeError(f"osascript 执行失败: {stderr[:300]}")
    return len(events)


def sync(
    events: list[CalendarEvent],
    calendar_name: str = DEFAULT_CALENDAR_NAME,
    remind_days_before: int = 1,
) -> dict:
    """同步入口：macOS 走 AppleScript，其他平台自动降级为 .ics 导出。

    :return: {"synced": N, "skipped": M, "fallback_ics": path 或 None}
    """
    fresh, skipped = filter_new(events)
    fallback_ics = None
    if fresh:
        if platform.system() == "Darwin":
            sync_to_macos_calendar(fresh, calendar_name, remind_days_before)
        else:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            fallback_ics = str(export_ics(fresh, f"mcd-events-{ts}.ics", remind_days_before))
        save_synced_uids(load_synced_uids() | {e.uid for e in fresh})
    return {
        "synced": len(fresh),
        "skipped": len(skipped),
        "fallback_ics": fallback_ics,
    }
