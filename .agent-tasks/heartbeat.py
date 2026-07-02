"""Local heartbeat reviewer for AGY/Codex handoff files.

This script does not call Codex or AGY. It watches AGY's report, runs a
deterministic pre-review when AGY marks work ready, and writes a markdown report
that Codex can use for final review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


READY_STATUS = "READY_FOR_CODEX_REVIEW"
DEFAULT_TEST_COMMANDS = [
    ["python", "-m", "unittest", "discover", "-s", "tests", "-v"],
    [
        "python",
        "-m",
        "pytest",
        "tests/test_channels.py",
        "tests/test_app.py",
        "tests/test_keithley2400.py",
        "tests/test_scan_logic.py",
        "-q",
    ],
]
EXPECTED_CHANGED_PREFIXES = (
    ".agent-tasks/",
    "scan_logic.py",
    "keithley2400.py",
    "keithley_switcher.ipynb",
    "README.md",
    "tests/test_scan_logic.py",
    "tests/test_keithley2400.py",
    "tests/test_dual_2400_scan.py",
    "tests/test_agent_heartbeat.py",
)


def parse_status(text: str) -> str:
    for line in str(text).splitlines():
        if line.strip().lower().startswith("status:"):
            return line.split(":", 1)[1].strip()
    return ""


def run_once(
    workspace: str | Path,
    *,
    runner=subprocess.run,
    test_commands: list[list[str]] | None = None,
    now=None,
    use_state: bool = False,
) -> dict:
    workspace = Path(workspace).resolve()
    tasks_dir = workspace / ".agent-tasks"
    report_path = tasks_dir / "agy-report.md"
    state_path = tasks_dir / "heartbeat-state.json"
    output_path = tasks_dir / "codex-auto-review.md"

    if not report_path.exists():
        return {"status": "SKIPPED", "reason": "agy-report.md does not exist"}

    report_text = report_path.read_text(encoding="utf-8")
    report_status = parse_status(report_text)
    if report_status != READY_STATUS:
        return {
            "status": "SKIPPED",
            "reason": f"agy-report.md is {report_status or 'missing status'}, not {READY_STATUS}",
        }

    trigger_hash = _hash_text(report_text)
    if use_state:
        state = _load_state(state_path)
        if state.get("last_reviewed_hash") == trigger_hash:
            return {"status": "SKIPPED", "reason": "agy-report.md already reviewed"}

    timestamp = now() if now else datetime.now().isoformat(timespec="seconds")
    commands = test_commands if test_commands is not None else DEFAULT_TEST_COMMANDS

    git_status = _run_command(["git", "status", "--short"], workspace, runner)
    changed_names = _changed_names(git_status["stdout"])
    diff_names = _run_command(["git", "diff", "--name-only"], workspace, runner)
    diff_check = _run_command(["git", "diff", "--check"], workspace, runner)
    test_results = [_run_command(command, workspace, runner) for command in commands]

    findings = []
    if git_status["returncode"] != 0:
        findings.append("git status failed")
    if diff_names["returncode"] != 0:
        findings.append("git diff --name-only failed")
    if diff_check["returncode"] != 0:
        findings.append("git diff --check failed")

    disallowed = _disallowed_files(changed_names)
    if disallowed:
        findings.append("Files outside expected AGY scope: " + ", ".join(disallowed))

    failed_tests = [result for result in test_results if result["returncode"] != 0]
    if failed_tests:
        findings.append(f"{len(failed_tests)} test command(s) failed")

    result_status = "FAILED" if findings else "PASS"
    output_path.write_text(
        _render_review(
            timestamp=timestamp,
            status=result_status,
            report_status=report_status,
            changed_names=changed_names,
            findings=findings,
            git_status=git_status,
            diff_check=diff_check,
            test_results=test_results,
        ),
        encoding="utf-8",
    )

    if use_state:
        _save_state(state_path, {"last_reviewed_hash": trigger_hash, "last_reviewed_at": timestamp})

    return {"status": result_status, "report_path": str(output_path), "findings": findings}


def watch(workspace: str | Path, interval_s: float, *, runner=subprocess.run) -> None:
    print(f"Watching .agent-tasks/agy-report.md every {interval_s:g}s. Press Ctrl+C to stop.")
    while True:
        result = run_once(workspace, runner=runner, use_state=True)
        if result["status"] != "SKIPPED":
            print(f"[{datetime.now().isoformat(timespec='seconds')}] auto-review: {result['status']}")
        time.sleep(interval_s)


def _run_command(command: list[str], cwd: Path, runner) -> dict:
    try:
        completed = runner(command, cwd=str(cwd), capture_output=True, text=True)
    except TypeError:
        completed = runner(command)
    except Exception as exc:
        return {
            "command": command,
            "returncode": 1,
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "command": command,
        "returncode": int(getattr(completed, "returncode", 1)),
        "stdout": getattr(completed, "stdout", "") or "",
        "stderr": getattr(completed, "stderr", "") or "",
    }


def _changed_names(status_output: str) -> list[str]:
    names = []
    for line in status_output.splitlines():
        if not line.strip():
            continue
        name = line[3:] if len(line) > 3 else line.strip()
        if " -> " in name:
            name = name.split(" -> ", 1)[1]
        names.append(_normalize_path(name))
    return names


def _disallowed_files(paths: list[str]) -> list[str]:
    disallowed = []
    for path in paths:
        normalized = _normalize_path(path)
        if not any(normalized == prefix or normalized.startswith(prefix) for prefix in EXPECTED_CHANGED_PREFIXES):
            disallowed.append(path)
    return disallowed


def _normalize_path(path: str) -> str:
    return str(path).replace("\\", "/").strip().strip('"')


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _render_review(
    *,
    timestamp: str,
    status: str,
    report_status: str,
    changed_names: list[str],
    findings: list[str],
    git_status: dict,
    diff_check: dict,
    test_results: list[dict],
) -> str:
    lines = [
        "# Codex Auto Review",
        "",
        f"Generated: {timestamp}",
        f"Status: {status}",
        f"AGY report status: {report_status}",
        "",
        "This is a deterministic heartbeat pre-review. Codex still needs to inspect the diff before marking the task `ACCEPTED`.",
        "",
        "## Findings",
        "",
    ]
    if findings:
        lines.extend(f"- {finding}" for finding in findings)
    else:
        lines.append("- None")

    lines.extend(["", "## Changed Files", ""])
    if changed_names:
        lines.extend(f"- `{name}`" for name in changed_names)
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Git Status",
            "",
            _format_command_block(git_status),
            "",
            "## Diff Check",
            "",
            _format_command_block(diff_check),
            "",
            "## Test Results",
            "",
        ]
    )
    if test_results:
        for result in test_results:
            lines.extend([_format_command_block(result), ""])
    else:
        lines.append("- No test commands configured")
    return "\n".join(lines).rstrip() + "\n"


def _format_command_block(result: dict) -> str:
    command = " ".join(result["command"])
    output = (result["stdout"] + result["stderr"]).strip()
    if not output:
        output = "<no output>"
    return f"Command: `{command}`\n\nReturn code: `{result['returncode']}`\n\n```text\n{output}\n```"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Heartbeat pre-review for AGY/Codex handoff files.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run one heartbeat check and exit.")
    mode.add_argument("--watch", action="store_true", help="Watch for READY_FOR_CODEX_REVIEW and auto-review.")
    parser.add_argument("--interval", type=float, default=10.0, help="Watch interval in seconds.")
    parser.add_argument("--workspace", default=".", help="Repository root. Defaults to current directory.")
    args = parser.parse_args(argv)

    if args.watch:
        try:
            watch(args.workspace, args.interval)
        except KeyboardInterrupt:
            print("Stopped heartbeat.")
            return 0
    result = run_once(args.workspace, use_state=args.watch)
    print(result["status"] + (f": {result.get('reason')}" if result.get("reason") else ""))
    if result.get("report_path"):
        print(result["report_path"])
    return 0 if result["status"] in {"PASS", "SKIPPED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
