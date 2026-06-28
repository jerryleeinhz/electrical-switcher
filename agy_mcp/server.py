from __future__ import annotations

import json
import sys
from typing import Any, Callable

from .core import (
    ToolError,
    tool_agy_execute_task,
    tool_agy_get_changed_files,
    tool_agy_get_diff,
    tool_agy_get_run_log,
    tool_agy_status,
)


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


TOOLS: dict[str, ToolHandler] = {
    "agy_status": tool_agy_status,
    "agy_execute_task": tool_agy_execute_task,
    "agy_get_diff": tool_agy_get_diff,
    "agy_get_run_log": tool_agy_get_run_log,
    "agy_get_changed_files": tool_agy_get_changed_files,
}


def tool_schema(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required or [],
            "additionalProperties": True,
        },
    }


TOOL_DEFINITIONS = [
    tool_schema("agy_status", "Check whether the AGY CLI is available.", {}),
    tool_schema(
        "agy_execute_task",
        "Ask AGY to implement a task in a workspace and return a compact run summary.",
        {
            "workspace": {"type": "string"},
            "task": {"type": "string"},
            "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
            "test_command": {"type": "string"},
            "timeout_minutes": {"type": "integer"},
            "model": {"type": "string"},
            "use_agy_sandbox": {"type": "boolean"},
        },
        ["workspace", "task"],
    ),
    tool_schema(
        "agy_get_diff",
        "Return git diff for a workspace, optionally scoped to files.",
        {"workspace": {"type": "string"}, "files": {"type": "array", "items": {"type": "string"}}},
        ["workspace"],
    ),
    tool_schema(
        "agy_get_run_log",
        "Return a bounded stdout log excerpt for a previous AGY run.",
        {"run_id": {"type": "string"}, "max_chars": {"type": "integer"}},
        ["run_id"],
    ),
    tool_schema(
        "agy_get_changed_files",
        "Return changed files from git status --short.",
        {"workspace": {"type": "string"}},
        ["workspace"],
    ),
]


def text_result(data: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]}


def error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def result_response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return result_response(
            request_id,
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "agy-mcp", "version": "0.1.0"},
            },
        )
    if method == "tools/list":
        return result_response(request_id, {"tools": TOOL_DEFINITIONS})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in TOOLS:
            return error_response(request_id, -32602, f"unknown tool: {name}")
        try:
            return result_response(request_id, text_result(TOOLS[name](arguments)))
        except ToolError as exc:
            return result_response(request_id, {"isError": True, **text_result({"error": str(exc)})})
        except Exception as exc:
            return error_response(request_id, -32000, str(exc))
    return error_response(request_id, -32601, f"method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
        except json.JSONDecodeError as exc:
            response = error_response(None, -32700, str(exc))
        if response is not None:
            print(json.dumps(response), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
