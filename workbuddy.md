# workbuddy.md — WorkBuddy 对话上下文

> 本文件用于麦当劳程序员创意开发大赛「WorkBuddy 专项奖励」核验：本项目在开发过程中真实使用了腾讯 WorkBuddy 智能体。以下为开发对话上下文的导出说明与关键记录。

## 开发环境

- 工具：腾讯 WorkBuddy（https://www.workbuddy.cn）
- 用途：创意构思、项目脚手架生成、MCP 连接器配置、代码开发与调试

## WorkBuddy MCP 连接器配置

在 WorkBuddy【连接器】→【自定义连接器】→【配置MCP】中添加：

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

配置后在对话中即可直接调用麦当劳 MCP 的活动日历查询工具进行开发调试。

## 关键开发对话记录（摘要）

1. **创意构思**：确定"麦当劳活动日历 → macOS 系统日历同步提醒"的产品方向，明确目标用户与核心场景。
2. **仓库脚手架**：由 WorkBuddy 生成项目整体结构（README、MCP_INTEGRATION、参赛声明、源码目录等）。
3. **MCP 对接**：通过 WorkBuddy 连接器调用麦当劳活动日历查询 Tool，确认返回字段，编写 `src/mcd_client.py`。
4. **日历写入**：由 WorkBuddy 编写并调试 AppleScript / EventKit 日历写入逻辑，实现活动事件 + 提前提醒。
5. **端到端联调**：一句话指令完成"查询活动 → 生成事件 → 写入日历 → 返回摘要"全流程验证。

## 完整对话导出

完整对话上下文将在开发完成后由 WorkBuddy 导出并替换/补充至本文件。

（待补充：WorkBuddy 对话导出内容）
