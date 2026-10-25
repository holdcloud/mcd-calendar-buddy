# workbuddy.md — WorkBuddy 对话上下文

> 本文件用于麦当劳程序员创意开发大赛「WorkBuddy 专项奖励」核验：本项目在开发过程中真实使用了腾讯 WorkBuddy 智能体完成创意构思、架构设计、编码与调试。以下为开发对话上下文的关键记录。

## 开发环境

- 工具：腾讯 WorkBuddy（https://www.workbuddy.cn）
- 用途：比赛规则解读、创意构思、项目脚手架生成、MCP 连接器配置、全部代码的开发与调试、单元测试、CI 配置、发布部署

## WorkBuddy MCP 连接器配置

在 WorkBuddy【连接器】→【自定义连接器】→【配置MCP】中添加（Token 使用环境变量，不落盘）：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer ${MCD_MCP_TOKEN}"
      }
    }
  }
}
```

配置后即可在 WorkBuddy 对话框中直接调用麦当劳 MCP 的活动日历工具进行开发调试。

## 开发对话记录（时间线）

### 第一轮：比赛解读与创意构思

- 向 WorkBuddy 提供活动仓库地址（M-China/mcd-developer-innovation-challenge），由其完整解读活动规则：报名流程、必备文件、Star 排名机制、奖励结构。
- 讨论创意方向后确定：**调用麦当劳 MCP 的活动日历查询能力，做一个"日历提醒助手"，把麦当劳活动自动同步到 macOS 系统日历**——解决"活动散落在 App/小程序多渠道、用户容易错过"的真实痛点。

### 第二轮：仓库骨架

- 由 WorkBuddy 生成参赛标准的项目结构：README、CONTEST_DECLARATION（官方原文）、MCP_INTEGRATION、mcp-config.example.json（脱敏占位符）、workbuddy.md、docs/design.md 架构文档、四个源码模块存根。

### 第三轮：MCP 真实联调

- 配置麦当劳 MCP Token 后，WorkBuddy 实测发现：活动日历工具真实名称为 `campaign-calendar`（入参 `specifiedDate` 可选，格式 yyyy-MM-dd），返回**按日期分组的 Markdown 文本**而非结构化 JSON，无活动唯一 ID 和精确时间字段。
- 基于真实返回修正设计：UID 采用 SHA1(活动标题+日期)；事件优先从介绍文本正则提取开售时间（如"10月22日10:45开售"），提取不到降级为全天事件。

### 第四轮：核心代码实现与端到端验证

- WorkBuddy 实现四个模块（纯 Python 标准库，零第三方依赖）：
  - `mcd_client.py`：JSON-RPC over Streamable HTTP，兼容纯 JSON 与 SSE 响应；
  - `event_builder.py`：Markdown 解析、开售时间提取、UID 去重；
  - `calendar_sync.py`：AppleScript 写入 Calendar.app（自动建"麦麦活动"日历）、.ics 导出兜底、本地 UID 状态去重；
  - `cli.py`：query / sync / export / schedule 子命令。
- 真实数据端到端验证：解析出 21 条活动；第一次 sync 新增 21 条，第二次 sync 自动跳过 21 条（去重生效）。

### 第五轮：功能优化（智能提醒 / 订阅过滤 / 定时同步）

- 智能提醒策略：开售类活动提前 1 天 + 提前 1 小时双提醒；全天活动提前 1 天 09:00 单次提醒。
- `--filter` 关键词订阅过滤（如 `--filter 联名,新品`），避免日历被无关活动刷屏。
- `schedule` 子命令一键生成 macOS launchd plist，实现每天定时自动同步。
- 补齐 8 个解析器单测（真实返回采样为 fixture，覆盖定时提取、全天降级、UID 稳定性、异常输入容错）。
- 配置 GitHub Actions CI（Python 3.10 / 3.13 双版本矩阵），README 增加演示动图与徽章。

### 第六轮：发布部署

- WorkBuddy 通过 GitHub API（Git Data API）完成仓库首次发布与优化迭代推送，并逐文件验证远程内容完整性。

## 完整对话导出

以上为 WorkBuddy 对话上下文的关键节点摘要。完整对话可在 WorkBuddy 会话历史中查看（本项目开发会话，创建于 2026-10-25）。
