from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


class ToolError(Exception):
    pass


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class RunPaths:
    run_id: str
    directory: Path
    request: Path
    prompt: Path
    stdout: Path
    stderr: Path
    result: Path


def make_run_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:6]}"


def find_agy(find_executable: Callable[[str], str | None] = shutil.which) -> Path | None:
    explicit = os.environ.get("AGY_MCP_AGY_PATH")
    if explicit:
        path = Path(explicit)
        return path if path.exists() else None
    found = find_executable("agy")
    return Path(found) if found else None


def require_workspace(value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ToolError("workspace must be a non-empty string")
    workspace = Path(value).expanduser().resolve()
    if not workspace.exists() or not workspace.is_dir():
        raise ToolError(f"workspace does not exist or is not a directory: {workspace}")
    return workspace


def build_prompt(
    *,
    workspace: Path,
    task: str,
    acceptance_criteria: list[str],
    test_command: str | None,
) -> str:
    criteria = "\n".join(f"- {item}" for item in acceptance_criteria) or "- No explicit criteria supplied."
    test_line = test_command or "No test command supplied."
    return (
        "You are AGY acting as an implementation worker for Codex.\n\n"
        f"Workspace:\n{workspace}\n\n"
        f"Task:\n{task}\n\n"
        f"Acceptance criteria:\n{criteria}\n\n"
        f"Test command:\n{test_line}\n\n"
        "Rules:\n"
        "- Make the smallest correct code change.\n"
        "- Prefer existing project patterns.\n"
        "- Do not modify unrelated files.\n"
        "- Run the test command if provided.\n"
        "- At the end, report changed files, what changed, test result, and known issues.\n"
    )


def build_agy_command(
    *,
    agy_path: Path,
    workspace: Path,
    prompt: str,
    timeout_minutes: int,
    model: str | None,
    use_agy_sandbox: bool,
) -> list[str]:
    command = [str(agy_path)]
    if model:
        command.extend(["--model", model])
    command.extend(["--add-dir", str(workspace), "--print", "--print-timeout", f"{timeout_minutes}m"])
    if use_agy_sandbox:
        command.append("--sandbox")
    command.append(prompt)
    return command


def run_dir_for(run_id: str, base_dir: Path | None = None) -> RunPaths:
    root = base_dir or Path(__file__).resolve().parent.parent / ".agy-mcp-runs"
    directory = root / run_id
    return RunPaths(
        run_id=run_id,
        directory=directory,
        request=directory / "request.json",
        prompt=directory / "prompt.txt",
        stdout=directory / "stdout.log",
        stderr=directory / "stderr.log",
        result=directory / "result.json",
    )


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def parse_changed_files(status_output: str) -> list[str]:
    files: list[str] = []
    for line in status_output.splitlines():
        if not line.strip():
            continue
        files.append(line[3:].strip() if len(line) > 3 else line.strip())
    return files


def run_git(
    workspace: Path,
    args: list[str],
    runner: Runner = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    return runner(["git", *args], cwd=workspace, text=True, capture_output=True)


def tool_agy_status(
    _args: dict[str, Any] | None = None,
    *,
    find_executable: Callable[[str], str | None] = shutil.which,
) -> dict[str, Any]:
    agy = find_agy(find_executable)
    return {
        "agy_path": str(agy) if agy else None,
        "available": agy is not None,
        "help_detected": agy is not None,
        "notes": "Non-interactive --print mode is expected." if agy else "AGY CLI was not found.",
    }


def tool_agy_get_changed_files(
    args: dict[str, Any],
    *,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    workspace = require_workspace(args.get("workspace"))
    completed = run_git(workspace, ["status", "--short"], runner)
    if completed.returncode != 0:
        raise ToolError(completed.stderr.strip() or "git status failed")
    return {"changed_files": parse_changed_files(completed.stdout)}


def bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ToolError("timeout_minutes must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise ToolError(f"timeout_minutes must be between {minimum} and {maximum}")
    return parsed


def tool_agy_get_diff(
    args: dict[str, Any],
    *,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    workspace = require_workspace(args.get("workspace"))
    files = args.get("files") or []
    if not isinstance(files, list):
        raise ToolError("files must be a list")
    completed = run_git(workspace, ["diff", "--", *[str(item) for item in files]], runner)
    if completed.returncode != 0:
        raise ToolError(completed.stderr.strip() or "git diff failed")
    return {"diff": completed.stdout}


def tool_agy_get_run_log(
    args: dict[str, Any],
    *,
    runs_base_dir: Path | None = None,
) -> dict[str, Any]:
    run_id = args.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ToolError("run_id must be a non-empty string")
    max_chars = bounded_int(args.get("max_chars"), default=12000, minimum=1, maximum=100000)
    paths = run_dir_for(run_id, runs_base_dir)
    if not paths.stdout.exists():
        raise ToolError(f"run log not found: {run_id}")
    text = paths.stdout.read_text(encoding="utf-8", errors="replace")
    return {"run_id": run_id, "log_excerpt": text[-max_chars:]}


def tool_agy_execute_task(
    args: dict[str, Any],
    *,
    runner: Runner = subprocess.run,
    runs_base_dir: Path | None = None,
) -> dict[str, Any]:
    workspace = require_workspace(args.get("workspace"))
    agy = find_agy()
    if agy is None:
        raise ToolError("AGY CLI was not found")
    task = args.get("task")
    if not isinstance(task, str) or not task.strip():
        raise ToolError("task must be a non-empty string")
    acceptance = args.get("acceptance_criteria") or []
    if not isinstance(acceptance, list):
        raise ToolError("acceptance_criteria must be a list")
    test_command = args.get("test_command")
    if test_command is not None and not isinstance(test_command, str):
        raise ToolError("test_command must be a string")
    timeout_minutes = bounded_int(args.get("timeout_minutes"), default=20, minimum=1, maximum=120)
    model = args.get("model")
    if model is not None and not isinstance(model, str):
        raise ToolError("model must be a string")
    use_agy_sandbox = bool(args.get("use_agy_sandbox", True))

    run_id = make_run_id()
    paths = run_dir_for(run_id, runs_base_dir)
    paths.directory.mkdir(parents=True, exist_ok=False)
    prompt = build_prompt(
        workspace=workspace,
        task=task,
        acceptance_criteria=[str(item) for item in acceptance],
        test_command=test_command,
    )
    write_json(paths.request, args)
    paths.prompt.write_text(prompt, encoding="utf-8")

    command = build_agy_command(
        agy_path=agy,
        workspace=workspace,
        prompt=prompt,
        timeout_minutes=timeout_minutes,
        model=model,
        use_agy_sandbox=use_agy_sandbox,
    )
    try:
        completed = runner(
            command,
            cwd=workspace,
            text=True,
            capture_output=True,
            timeout=timeout_minutes * 60,
        )
        status = "completed" if completed.returncode == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        completed = subprocess.CompletedProcess(command, 124, exc.stdout or "", exc.stderr or "")
        status = "timeout"

    paths.stdout.write_text(completed.stdout or "", encoding="utf-8")
    paths.stderr.write_text(completed.stderr or "", encoding="utf-8")
    changed = tool_agy_get_changed_files({"workspace": str(workspace)}, runner=runner)["changed_files"]
    result = {
        "run_id": run_id,
        "status": status,
        "exit_code": completed.returncode,
        "changed_files": changed,
        "summary": (completed.stdout or completed.stderr or "").strip()[-1000:],
        "test_summary": "",
        "known_issues": [] if completed.returncode == 0 else [(completed.stderr or "AGY exited with an error").strip()[-1000:]],
        "log_path": str(paths.stdout),
    }
    write_json(paths.result, result)
    return result
