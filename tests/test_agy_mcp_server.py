from agy_mcp.server import handle_request


def test_initialize_returns_protocol_info():
    response = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert response["id"] == 1
    assert response["result"]["serverInfo"]["name"] == "agy-mcp"


def test_tools_list_contains_expected_tools():
    response = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    names = {tool["name"] for tool in response["result"]["tools"]}
    assert {"agy_status", "agy_execute_task", "agy_get_diff", "agy_get_run_log", "agy_get_changed_files"} <= names


def test_tools_call_status_returns_content():
    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "agy_status", "arguments": {}},
        }
    )
    assert response["result"]["content"][0]["type"] == "text"
