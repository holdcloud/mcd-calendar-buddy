# 麦麦日历助手（McD Activity Calendar Buddy）

> 麦当劳程序员创意开发大赛参赛作品：基于麦当劳 MCP「活动日历查询」能力，把麦当劳的优惠/主题活动自动同步到 macOS 日历，再也不错过任何一场麦麦活动。

## 项目简介

**麦麦日历助手**是一个面向 Mac 用户的日历提醒 Skill：

1. 通过麦当劳 MCP Server 的**活动日历查询工具**获取近期麦当劳活动（新品上市、优惠券有效期、主题节日活动等）；
2. 将活动自动转换为日历事件（含开始/结束时间、活动说明、提醒时间）；
3. 一键同步写入 **macOS 日历（Calendar.app）**，到点自动弹窗提醒。

示例场景：*"帮我把麦当劳最近两周的活动都加到日历里，活动开始前一天提醒我"* —— 助手查询活动日历 → 生成事件 → 写入系统日历，完成。

## 目标用户

- 喜欢麦当劳、不想错过优惠和限定活动的用户
- 使用 macOS 日历管理日程、依赖提醒通知的用户
- 希望通过自然语言一句话搞定信息整理的效率党

## 安装方法

项目**零第三方依赖**，仅需 Python 3.10+。

```bash
# 1. 克隆仓库
git clone https://github.com/<你的用户名>/mcd-calendar-buddy.git
cd mcd-calendar-buddy

# 2. 配置麦当劳 MCP Token（获取方式：麦当劳 MCP 官网 → 登录 → 控制台 → 激活）
export MCD_MCP_TOKEN="你的麦当劳MCP Token"        # macOS / Linux
setx MCD_MCP_TOKEN "你的麦当劳MCP Token"          # Windows

# 3. 运行
python src/cli.py query              # 查询当月麦当劳活动
python src/cli.py sync               # 同步到 macOS 日历（默认提前 1 天提醒）
python src/cli.py export -o mc.ics   # 导出 .ics（任何平台可用）
```

macOS 权限说明：首次 `sync` 写入日历时，系统会请求「日历」自动化权限，请在 系统设置 > 隐私与安全性 > 自动化 中允许；Windows/Linux 等平台会自动降级为导出 `.ics` 文件，双击导入即可。

## 使用示例

```bash
$ python src/cli.py query
共查询到 21 条活动：

  [2026-10-22 10:45] 麦当劳「我就喜欢」限定丝巾正式开售🔥
      丝巾搭配棒球帽的潮流谁懂😎…
  [2026-10-08 10:30] 韩式风味蘸酱上新❤️就「酱」心有所「薯」
      🆕韩式辣椒黄油风味酱…
  ...

$ python src/cli.py sync
✅ 新增 21 条，跳过已同步 0 条
事件已写入日历「麦麦活动」，到点自动提醒。
```

自然语言场景（配合 WorkBuddy / 支持 MCP 的智能体使用）：

```text
用户：最近麦当劳有什么活动？帮我把开售时间加到日历里，提前一天提醒我
助手：（调用麦当劳 MCP campaign-calendar 工具 → 解析活动 → 生成日历事件 → 写入系统日历）
```

## 功能清单

| 功能 | 状态 |
| --- | --- |
| 调用麦当劳 MCP `campaign-calendar` 查询活动 | ✅ 已实现（真实联调通过） |
| 活动 Markdown 解析 → 日历事件（含开售时间提取） | ✅ 已实现 |
| 写入 macOS 日历（Calendar.app，AppleScript） | ✅ 已实现 |
| .ics 导出兜底（跨平台） | ✅ 已实现 |
| UID 去重（重复同步不产生冗余事件） | ✅ 已实现 |
| 活动开始前自动提醒（VALARM / display alarm） | ✅ 已实现 |
| 自然语言入口（WorkBuddy 智能体联动） | 🚧 规划中 |

## 项目结构

```
mcd-calendar-buddy/
├── README.md                  # 本文件：项目介绍、安装、使用示例
├── CONTEST_DECLARATION.md     # 参赛声明（官方要求，内容不可改动）
├── MCP_INTEGRATION.md         # 麦当劳 MCP 集成说明
├── mcp-config.example.json    # 脱敏后的 MCP 配置示例
├── workbuddy.md               # WorkBuddy 对话上下文（联动活动）
├── requirements.txt           # Python 依赖
├── docs/
│   └── design.md              # 架构与设计说明
├── src/
│   ├── __init__.py
│   ├── mcd_client.py          # 麦当劳 MCP 客户端（活动日历查询）
│   ├── event_builder.py       # 活动数据 → 日历事件转换
│   ├── calendar_sync.py       # macOS 日历写入（AppleScript / EventKit）
│   └── cli.py                 # 命令行入口
└── examples/
    └── sample_events.json     # 活动数据与日历事件示例
```

## 参赛声明

本项目为麦当劳程序员节创意开发大赛参赛作品，非麦当劳官方产品。活动信息以麦当劳官方渠道实时结果为准，详见 [CONTEST_DECLARATION.md](CONTEST_DECLARATION.md)。

## 许可证

MIT License
