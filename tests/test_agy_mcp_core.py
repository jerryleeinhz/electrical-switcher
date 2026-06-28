from pathlib import Path
from unittest.mock import Mock

from agy_mcp.core import (
    ToolError,
    build_agy_command,
    build_prompt,
    find_agy,
    make_run_id,
    tool_agy_execute_task,
    tool_agy_get_changed_files,
    tool_agy_get_diff,
    tool_agy_get_run_log,
    tool_agy_status,
)


def test_find_agy_prefers_explicit_path(tmp_path, monkeypatch):
    agy = tmp_path / "agy.exe"
    agy.write_text("", encoding="utf-8")
    monkeypatch.setenv("AGY_MCP_AGY_PATH", str(agy))
    assert find_agy() == agy


def test_build_prompt_contains_acceptance_criteria():
    prompt = build_prompt(
        workspace=Path("C:/repo"),
        task="Fix the bug",
        acceptance_criteria=["Tests pass", "No unrelated edits"],
        test_command="pytest",
    )
    assert "Fix the bug" in prompt
    assert "- Tests pass" in prompt
    assert "pytest" in prompt


def test_build_agy_command_uses_print_mode(tmp_path):
    agy = tmp_path / "agy.exe"
    command = build_agy_command(
        agy_path=agy,
        workspace=tmp_path,
        prompt="hello",
        timeout_minutes=7,
        model="gemini-test",
        use_agy_sandbox=True,
    )
    assert command[:2] == [str(agy), "--model"]
    assert "--print" in command
    assert "--print-timeout" in command
    assert "7m" in command
    assert "--sandbox" in command
    assert "hello" in command


def test_make_run_id_is_stable_shape():
    run_id = make_run_id()
    assert len(run_id) >= 17
    assert "-" in run_id


def test_agy_status_reports_missing_cli(monkeypatch):
    monkeypatch.delenv("AGY_MCP_AGY_PATH", raising=False)
    result = tool_agy_status(find_executable=lambda _: None)
    assert result["available"] is False


def test_changed_files_parses_git_status(tmp_path):
    runner = Mock(return_value=Mock(returncode=0, stdout=" M app.py\n?? tests/test_app.py\n", stderr=""))
    result = tool_agy_get_changed_files({"workspace": str(tmp_path)}, runner=runner)
    assert result["changed_files"] == ["app.py", "tests/test_app.py"]


def test_changed_files_rejects_missing_workspace(tmp_path):
    missing = tmp_path / "missing"
    try:
        tool_agy_get_changed_files({"workspace": str(missing)})
    except ToolError as exc:
        assert "workspace does not exist" in str(exc)
    else:
        raise AssertionError("expected ToolError")


def test_get_diff_returns_git_diff(tmp_path):
    runner = Mock(return_value=Mock(returncode=0, stdout="diff --git a/app.py b/app.py\n", stderr=""))
    result = tool_agy_get_diff({"workspace": str(tmp_path)}, runner=runner)
    assert result["diff"].startswith("diff --git")


def test_execute_task_writes_run_record(tmp_path, monkeypatch):
    agy = tmp_path / "agy.exe"
    agy.write_text("", encoding="utf-8")
    monkeypatch.setenv("AGY_MCP_AGY_PATH", str(agy))
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        if command[0] == "git":
            return Mock(returncode=0, stdout=" M app.py\n", stderr="")
        return Mock(returncode=0, stdout="done: tests pass", stderr="")

    result = tool_agy_execute_task(
        {
            "workspace": str(tmp_path),
            "task": "Make a tiny change",
            "acceptance_criteria": ["Tests pass"],
            "test_command": "pytest",
            "timeout_minutes": 1,
        },
        runner=runner,
        runs_base_dir=tmp_path / "runs",
    )
    assert result["status"] == "completed"
    assert result["changed_files"] == ["app.py"]
    assert Path(result["log_path"]).exists()
    assert any(str(agy) in command for command in calls)


def test_get_run_log_bounds_output(tmp_path):
    run_id = "run-1"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    (run_dir / "stdout.log").write_text("abcdef", encoding="utf-8")
    result = tool_agy_get_run_log({"run_id": run_id, "max_chars": 3}, runs_base_dir=tmp_path)
    assert result["log_excerpt"] == "def"
