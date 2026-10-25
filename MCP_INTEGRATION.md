# MCP_INTEGRATION.md — 麦当劳 MCP 集成说明

本项目基于麦当劳 MCP（Model Context Protocol）能力开发，以下是本项目实际使用的 MCP 资源、调用流程与业务价值。

## 1. 使用的 MCP Server

| 项目 | 说明 |
| --- | --- |
| Server 名称 | `mcd-mcp`（麦当劳中国官方 MCP Server） |
| 接入地址 | `https://mcp.mcd.cn` |
| 认证方式 | HTTP Header：`Authorization: Bearer <MCD_MCP_TOKEN>` |
| 协议类型 | Streamable HTTP |
| Token 获取 | 麦当劳 MCP 官网 → 登录 → 控制台 → 激活申请（详见活动仓库 README） |

## 2. 使用的 Tool

### `campaign-calendar`（营销活动日历查询）

- **用途**：查询麦当劳中国当月的营销活动日历，返回进行中、往期和未来日期的活动，并包含用户对活动的订阅状态。
- **入参**（已实测确认）：
  - `specifiedDate`（string，可选，格式 `yyyy-MM-dd`）：查询基准日期。传入时以该日为锚点，返回当天及时间线上最邻近的前后各一个有活动的日子（共三天）；不填时默认返回当前月所有活动。
- **出参**（已实测确认）：**Markdown 文本**，按日期分组（如 `#### 2026年10月25日 今日`），每个活动包含：
  - `活动标题`（如「韩式风味蘸酱上新」「麦当劳 X PEACEMINUSONE 联名徽章发售」）
  - `活动内容介绍`（图文混排 Markdown，含开售时间、价格等）
  - `活动图片介绍`（`<img src="https://cms-cdn.mcd.cn/...">`）
- **注意**：返回为非结构化文本，无活动唯一 ID、无独立起止时间字段；本项目在 `src/event_builder.py` 中解析该 Markdown 并做降级处理（详见 docs/design.md）。
- **调用时机**：用户发起"查询麦当劳活动"或"同步活动到日历"指令时触发。

## 3. 调用流程

```
用户指令（自然语言）
        │
        ▼
┌──────────────────┐
│  Skill / CLI 入口 │  src/cli.py
└────────┬─────────┘
         ▼
┌──────────────────┐      MCP (Streamable HTTP + Bearer Token)
│  麦当劳 MCP 客户端 │ ─────────────────────────────────────► https://mcp.mcd.cn
│  src/mcd_client.py│ ◄─────  campaign-calendar Tool（按日期分组的活动 Markdown）
└────────┬─────────┘
         ▼
┌──────────────────┐
│  事件构造器       │  src/event_builder.py：解析活动 Markdown → VEVENT（标题/日期/描述/提醒）
└────────┬─────────┘
         ▼
┌──────────────────┐
│  日历同步器       │  src/calendar_sync.py：写入 macOS 日历（Calendar.app）
└──────────────────┘
```

1. 用户通过自然语言或 CLI 指定要同步的时间范围与提醒策略；
2. 项目通过 MCP 协议调用麦当劳官方 Server 的 `campaign-calendar` Tool，获取按日期分组的活动 Markdown；
3. 解析 Markdown：提取日期分组头、活动标题、内容介绍（正则提取开售日期作为事件时间依据）；
4. 将每条活动转换为标准日历事件（iCalendar VEVENT）：活动标题为事件名，开售/活动日为日期（默认全天事件），内容介绍 + 图片链接写入事件备注，默认提前 1 天 VALARM 提醒；
5. 通过 macOS 日历接口（AppleScript / EventKit）写入本地"麦麦活动"日历，并做去重（基于 `标题+日期` 哈希 UID）；
6. 向用户返回同步结果摘要（新增 N 条 / 跳过 M 条重复）。

## 4. 业务价值

- **信息触达**：麦当劳活动散落在 App、小程序、门店等多个渠道，用户容易错过；本 Skill 把活动"推"到用户每天必看的系统日历里，实现被动信息的主动提醒。
- **决策辅助**：活动开始前提醒，帮助用户在优惠窗口期内决策"今天吃什么"。
- **场景延展**：验证了"MCP 数据 + 系统能力（日历/通知）"的组合玩法，可推广到门店上新、会员日等更多场景。

## 5. 安全说明

- 所有 Token 通过环境变量 `MCD_MCP_TOKEN` 注入，仓库中不包含任何真实凭证；
- `mcp-config.example.json` 仅含环境变量占位符，可直接复制使用。
