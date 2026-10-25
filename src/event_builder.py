"""活动数据 → 日历事件转换器。

职责：
- 解析 campaign-calendar Tool 返回的活动 Markdown
- 转换为标准日历事件（iCalendar VEVENT / Calendar.app 事件属性）
- 字段缺失时的降级策略（见 docs/design.md 3.4）：
  * 事件日期优先取活动介绍中可提取的开售日期（如「10月22日10:45开售」）；
  * 提取不到时，退回所属日期分组头，按全天事件处理；
  * UID = SHA1(活动标题 + 事件日期)，用于跨次同步去重。

仅使用 Python 标准库，无第三方依赖。
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# 日期分组头，如 "#### 2026年10月25日 今日"
_DATE_HEADER_RE = re.compile(r"#{2,6}\s*(\d{4})年(\d{1,2})月(\d{1,2})日")
# 活动标题，如 "-   **活动标题**：xxx"
_TITLE_RE = re.compile(r"^\s*-\s*\*\*活动标题\*\*[:：]\s*(.+)$")
# 活动内容介绍起始行
_DESC_RE = re.compile(r"\*\*活动内容介绍\*\*[:：]?\s*(.*)$")
# 活动图片，如 <img src="https://cms-cdn.mcd.cn/..." ...>
_IMG_RE = re.compile(r'<img\s+src="([^"]+)"')
# 介绍文本中的开售日期，如 "10月22日10:45开售" / "10月8日 10:30起正式开售"
_SALE_DATE_RE = re.compile(
    r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})?"
)
# 需要从描述中剔除的 Markdown 噪音
_IMG_TAG_RE = re.compile(r"<img[^>]*>|</?img[^>]*>")


@dataclass
class CalendarEvent:
    """一条可写入日历的活动事件。"""

    uid: str
    title: str
    start: datetime          # 全天事件时为当天 00:00
    end: datetime            # 全天事件时为次日 00:00
    all_day: bool
    description: str = ""
    image: str = ""
    group_date: str = ""     # Markdown 中的原始分组日期（yyyy-mm-dd）
    notes: list = field(default_factory=list)  # 解析过程备注（降级说明）

    def summary_text(self) -> str:
        return self.title


def _make_uid(title: str, date_str: str) -> str:
    raw = f"{title}|{date_str}|mcd-calendar-buddy"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _clean_description(text: str) -> str:
    text = _IMG_TAG_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_start_date(desc: str, group_year: int, fallback: datetime) -> tuple[datetime, bool, str]:
    """从活动介绍中提取开售日期；提取不到则退回分组日期（全天）。

    :return: (start, all_day, note)
    """
    matches = _SALE_DATE_RE.findall(desc)
    for year_s, month_s, day_s, time_s in matches:
        year = int(year_s) if year_s else group_year
        if time_s:  # 有精确时间 → 定时事件
            hh, mm = map(int, time_s.split(":"))
            start = datetime(year, int(month_s), int(day_s), hh, mm)
            return start, False, f"从介绍文本提取开售时间 {start:%Y-%m-%d %H:%M}"
        # 仅日期无时间 → 当天全天事件
        start = datetime(year, int(month_s), int(day_s))
        return start, True, f"从介绍文本提取开售日期 {start:%Y-%m-%d}（全天）"
    return fallback, True, "未提取到开售日期，使用活动分组日期（全天）"


def parse_campaign_markdown(markdown: str) -> list[CalendarEvent]:
    """把 campaign-calendar 返回的 Markdown 解析为日历事件列表。"""
    lines = markdown.splitlines()
    events: list[CalendarEvent] = []
    group_year, group_date_str = None, ""
    current: dict | None = None

    def flush():
        nonlocal current
        if not current or not current.get("title"):
            current = None
            return
        title = current["title"].strip()
        desc = _clean_description("\n".join(current["desc_lines"]))
        image = current["image"]
        if image and image not in desc:
            desc = f"{desc}\n\n活动图片: {image}".strip()
        fallback = datetime(group_year, 1, 1) if group_year else datetime.now()
        if group_year and group_date_str:
            try:
                fallback = datetime.strptime(group_date_str, "%Y-%m-%d")
            except ValueError:
                pass
        start, all_day, note = _extract_start_date(desc, group_year or datetime.now().year, fallback)
        end = (start + timedelta(days=1)) if all_day else (start + timedelta(hours=2))
        events.append(CalendarEvent(
            uid=_make_uid(title, start.strftime("%Y-%m-%d")),
            title=title,
            start=start,
            end=end,
            all_day=all_day,
            description=desc,
            image=image,
            group_date=group_date_str,
            notes=[note],
        ))
        current = None

    for line in lines:
        date_match = _DATE_HEADER_RE.search(line)
        if date_match:
            flush()
            year, month, day = map(int, date_match.groups())
            group_year = year
            group_date_str = f"{year:04d}-{month:02d}-{day:02d}"
            continue
        title_match = _TITLE_RE.match(line)
        if title_match:
            flush()
            current = {"title": title_match.group(1), "desc_lines": [], "image": ""}
            continue
        if current is None:
            continue
        if "**活动图片介绍**" in line:
            continue
        desc_match = _DESC_RE.search(line)
        if desc_match:
            if desc_match.group(1):
                current["desc_lines"].append(desc_match.group(1))
            continue
        img_match = _IMG_RE.search(line)
        if img_match:
            current["image"] = img_match.group(1)
            continue
        if line.strip() and not line.strip().startswith("#"):
            current["desc_lines"].append(line.rstrip())
    flush()
    return events


def dedupe(events: list[CalendarEvent]) -> list[CalendarEvent]:
    """按 UID 去重，保留先出现的。"""
    seen, result = set(), []
    for event in events:
        if event.uid in seen:
            continue
        seen.add(event.uid)
        result.append(event)
    return result
