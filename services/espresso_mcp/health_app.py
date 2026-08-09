"""Lightweight health API for the espresso MCP container.

The real MCP tool functions live in ``services.espresso_mcp.app``. The stdio
transport is intentionally handled later; this HTTP wrapper lets Docker Compose
verify that the MCP package imports and exposes tool metadata.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from services.espresso_mcp import app as espresso_tools

app = FastAPI(title="espresso-mcp-health")


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "espresso-mcp",
        "tool_count": len(espresso_tools.get_registered_tool_names()),
    }


@app.get("/tools")
def tools() -> dict[str, object]:
    tool_names = espresso_tools.get_registered_tool_names()
    return {"count": len(tool_names), "tools": tool_names}


@app.get("/metrics.prometheus", response_class=PlainTextResponse)
def prometheus_metrics() -> str:
    tool_count = len(espresso_tools.get_registered_tool_names())
    return "# TYPE dialedin_espresso_mcp_tool_count gauge\n" f"dialedin_espresso_mcp_tool_count {tool_count}\n"
