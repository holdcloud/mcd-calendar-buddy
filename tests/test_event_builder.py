"""event_builder 解析器单元测试。

fixture 来自 campaign-calendar Tool 真实返回（2026-10-25 实测采样）。
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from event_builder import dedupe, filter_events, parse_campaign_markdown  # noqa: E402

SAMPLE_MARKDOWN = """### 当前时间：2026-10-25 11:14:21

### 活动列表：

#### 2026年10月25日 今日

-   **活动标题**：麦当劳「我就喜欢」限定丝巾正式开售🔥
    **活动内容介绍**：丝巾搭配棒球帽的潮流谁懂😎
任意餐品消费加 39.9 元即可得
颈间、包袋、手腕、头饰一巾多玩🤔
10月22日10:45开售
    **活动图片介绍**：
    <img src="https://cms-cdn.mcd.cn/img/short-content/fb40c37c172886ee1235c2ed21f3bde4.jpg" alt="" height="300" width="auto">

-   **活动标题**：🫐一口爆汁！蓝莓爆爆珠麦旋风上新
    **活动内容介绍**：🫐蓝莓爆爆珠麦旋风上新！
💜清甜蓝莓碰上醇厚奶香，酸甜清爽。
    **活动图片介绍**：
    <img src="https://cms-cdn.mcd.cn/img/short-content/105121c86e1023b6cc4b7fb4754ca145.jpg" alt="" height="300" width="auto">

#### 2026年10月26日

-   **活动标题**：下周麦麦省优惠预告来啦😁
    **活动内容介绍**：🌟麦麦省下周优惠抢先预告
优惠券、免单等你来！
"""


def test_parse_count():
    events = parse_campaign_markdown(SAMPLE_MARKDOWN)
    assert len(events) == 3


def test_timed_event_extracted_from_description():
    events = parse_campaign_markdown(SAMPLE_MARKDOWN)
    scarf = next(e for e in events if "丝巾" in e.title)
    assert not scarf.all_day
    assert scarf.start == datetime(2026, 10, 22, 10, 45)
    assert scarf.end == datetime(2026, 10, 22, 12, 45)
    assert "从介绍文本提取开售时间" in scarf.notes[0]


def test_all_day_fallback_to_group_date():
    events = parse_campaign_markdown(SAMPLE_MARKDOWN)
    icecream = next(e for e in events if "麦旋风" in e.title)
    assert icecream.all_day
    assert icecream.start == datetime(2026, 10, 25)


def test_uid_stable_and_distinct():
    events = parse_campaign_markdown(SAMPLE_MARKDOWN)
    uids = [e.uid for e in events]
    assert len(uids) == len(set(uids))
    # 同样输入再次解析，UID 应一致（去重依据）
    again = [e.uid for e in parse_campaign_markdown(SAMPLE_MARKDOWN)]
    assert uids == again


def test_image_and_description_captured():
    events = parse_campaign_markdown(SAMPLE_MARKDOWN)
    scarf = next(e for e in events if "丝巾" in e.title)
    assert scarf.image.startswith("https://cms-cdn.mcd.cn/")
    assert "39.9 元" in scarf.description
    assert "**活动图片介绍**" not in scarf.description  # 噪音标记应被剔除


def test_dedupe():
    events = parse_campaign_markdown(SAMPLE_MARKDOWN)
    assert len(dedupe(events + events)) == len(events)


def test_filter_by_keyword():
    events = parse_campaign_markdown(SAMPLE_MARKDOWN)
    assert len(filter_events(events, "麦旋风")) == 1
    assert len(filter_events(events, "优惠券")) == 1  # 命中描述里的"优惠券"
    assert len(filter_events(events, "联名,麦旋风")) == 1
    assert filter_events(events, None) == events
    assert filter_events(events, "") == events


def test_malformed_input_does_not_crash():
    assert parse_campaign_markdown("") == []
    assert parse_campaign_markdown("随机文本，无活动结构") == []
    partial = "#### 2026年10月25日 今日\n\n-   **活动标题**：只有标题没有内容\n"
    events = parse_campaign_markdown(partial)
    assert len(events) == 1
    assert events[0].title == "只有标题没有内容"
    assert events[0].all_day  # 无介绍文本 → 降级为分组日期全天事件
