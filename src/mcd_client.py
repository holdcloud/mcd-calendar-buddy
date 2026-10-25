"""麦当劳 MCP 客户端。

职责：
- 通过 Streamable HTTP (JSON-RPC 2.0) 与麦当劳 MCP Server 通信
- 调用 campaign-calendar Tool 获取营销活动日历
- Token 通过环境变量 MCD_MCP_TOKEN 注入，禁止硬编码

仅使用 Python 标准库，无第三方依赖。
"""

import json
import os
import urllib.request
import urllib.error

MCP_SERVER_URL = "https://mcp.mcd.cn"

# 已实测确认的 Tool（2026-10-25）
TOOL_CAMPAIGN_CALENDAR = "campaign-calendar"
# 入参: specifiedDate (可选, yyyy-MM-dd)
# 出参: Markdown 文本, 按日期分组的活动列表（标题/内容介绍/图片）

_CLIENT_INFO = {"name": "mcd-calendar-buddy", "version": "0.1.0"}
_REQUEST_TIMEOUT = 30  # seconds


class MCPClientError(RuntimeError):
    """MCP 调用失败。"""


class McDonaldMCPClient:
    """麦当劳中国官方 MCP Server 客户端。"""

    def __init__(self, base_url: str = MCP_SERVER_URL, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token or os.environ.get("MCD_MCP_TOKEN", "")
        if not self.token:
            raise MCPClientError(
                "缺少麦当劳 MCP Token，请设置环境变量 MCD_MCP_TOKEN"
                "（获取方式见麦当劳 MCP 官网控制台）"
            )
        self._next_id = 0
        self._session_id: str | None = None
        self._initialized = False

    # ------------------------------------------------------------------ #
    # 底层通信
    # ------------------------------------------------------------------ #
    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.token}",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _post(self, payload: dict) -> dict | None:
        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
                session_id = resp.headers.get("Mcp-Session-Id")
                if session_id:
                    self._session_id = session_id
                body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise MCPClientError(f"MCP HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise MCPClientError(f"MCP 连接失败: {exc.reason}") from exc

        if not body.strip():
            return None  # notification 无响应体
        return self._parse_body(body)

    @staticmethod
    def _parse_body(body: str) -> dict:
        """兼容纯 JSON 与 SSE (event-stream) 两种响应格式。"""
        text = body.strip()
        if text.startswith("{"):
            data = json.loads(text)
        else:  # SSE: 取最后一个 data: 行
            chunks = [
                line[len("data:"):].strip()
                for line in text.splitlines()
                if line.startswith("data:")
            ]
            if not chunks:
                raise MCPClientError(f"MCP 返回了无法解析的内容: {text[:200]}")
            data = json.loads(chunks[-1])
        if "error" in data:
            raise MCPClientError(f"MCP 错误: {data['error']}")
        return data

    def _rpc(self, method: str, params: dict | None = None, notify: bool = False) -> dict | None:
        payload: dict = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        if not notify:
            self._next_id += 1
            payload["id"] = self._next_id
        return self._post(payload)

    # ------------------------------------------------------------------ #
    # MCP 生命周期
    # ------------------------------------------------------------------ #
    def initialize(self) -> dict:
        if self._initialized:
            return {}
        data = self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": _CLIENT_INFO,
            },
        )
        self._rpc("notifications/initialized", notify=True)
        self._initialized = True
        return (data or {}).get("result", {})

    # ------------------------------------------------------------------ #
    # 业务 Tool
    # ------------------------------------------------------------------ #
    def call_tool(self, name: str, arguments: dict | None = None) -> str:
        """调用 Tool，返回拼接后的文本内容。"""
        self.initialize()
        data = self._rpc(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        result = (data or {}).get("result", {})
        if result.get("isError"):
            raise MCPClientError(f"Tool {name} 执行失败: {result.get('content')}")
        parts = [
            item.get("text", "")
            for item in result.get("content", [])
            if item.get("type") == "text"
        ]
        return "\n".join(parts)

    def fetch_campaign_calendar(self, specified_date: str | None = None) -> str:
        """查询营销活动日历。

        :param specified_date: 可选，格式 yyyy-MM-dd。传入时返回该日及
            时间线上最邻近的前后各一个有活动的日子；不填返回当月全部活动。
        :return: 按日期分组的活动 Markdown 文本。
        """
        arguments = {}
        if specified_date:
            arguments["specifiedDate"] = specified_date
        return self.call_tool(TOOL_CAMPAIGN_CALENDAR, arguments)
