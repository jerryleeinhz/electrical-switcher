# AGY MCP Server Design

Date: 2026-06-28

## Goal

Build a local MCP server that lets Codex delegate implementation and test execution to the Antigravity CLI (`agy.exe`), while Codex remains responsible for review, verification, and final acceptance.

The first version should be small and reliable:

- Codex sends a structured task to the MCP server.
- The MCP server invokes `agy.exe` in non-interactive print mode.
- AGY edits code and optionally runs tests inside the target workspace.
- The MCP server records the run and returns only a compact summary.
- Codex inspects changed files, diffs, logs, and test evidence on demand.

## Local Findings

The current machine has an AGY CLI available:

- `agy.exe` is installed at `C:\Users\liy56\AppData\Local\agy\bin\agy.exe`.
- `agy --help` exposes non-interactive options: `--print`, `--prompt`, `--print-timeout`.
- `agy --help` also exposes workspace and session controls: `--add-dir`, `--conversation`, `--continue`, `--model`, `--sandbox`.
- `agy plugin list` runs successfully and reports no imported plugins.
- `agy models` needs normal user environment access for login, network, and user-directory state. It should be run outside Codex's restricted sandbox when used for real AGY work.

## API, CLI, and MCP

API and CLI are different interface shapes, not simply cloud versus local.

- CLI means Codex or the MCP server starts a command-line program such as `agy.exe`.
- API means Codex or the MCP server calls a structured programmatic interface, usually HTTP or an SDK.
- Either one can be local or cloud-backed.
- In this design, MCP is the adapter layer that exposes AGY as agent-callable tools.

First version:

```text
Codex -> AGY MCP server -> agy.exe CLI -> Antigravity service/runtime
```

Future version, if Antigravity exposes a stable SDK/API:

```text
Codex -> AGY MCP server -> Antigravity SDK/API
```

The MCP interface should stay stable so Codex usage does not change when the backend moves from CLI to API.

## Recommended Approach

Use the AGY CLI, not the graphical Antigravity interface.

CLI advantages:

- Can be invoked from a local MCP stdio server.
- Supports timeouts and exit-code handling.
- Produces stdout and stderr that can be captured.
- Can be paired with `git diff`, changed-file detection, and test logs.
- Avoids brittle GUI automation around window focus, layout changes, and interactive prompts.

GUI automation should remain a last-resort fallback if CLI automation proves impossible.

## MCP Server Shape

Use a local stdio MCP server. A Python implementation is preferred for the first version because it can be kept dependency-light and easy to inspect.

Proposed directory:

```text
agy-mcp/
  server.py
  README.md
  runs/
```

If this is kept inside a repository, `runs/` should be ignored by git.

## Tools

### `agy_status`

Checks local AGY availability without modifying code.

Input:

```json
{}
```

Output:

```json
{
  "agy_path": "C:\\Users\\liy56\\AppData\\Local\\agy\\bin\\agy.exe",
  "available": true,
  "help_detected": true,
  "notes": "Non-interactive --print mode is available."
}
```

### `agy_execute_task`

Delegates a coding task to AGY.

Input:

```json
{
  "workspace": "C:\\path\\to\\repo",
  "task": "Implement the requested change.",
  "acceptance_criteria": [
    "All relevant tests pass.",
    "Do not modify unrelated files."
  ],
  "test_command": "pytest",
  "timeout_minutes": 20,
  "model": null,
  "use_agy_sandbox": true
}
```

Output:

```json
{
  "run_id": "20260628-153500-a1b2c3",
  "status": "completed",
  "exit_code": 0,
  "changed_files": [
    "app.py",
    "tests/test_app.py"
  ],
  "summary": "AGY completed the requested change and reported tests passing.",
  "test_summary": "pytest: 12 passed",
  "known_issues": [],
  "log_path": "agy-mcp/runs/20260628-153500-a1b2c3/output.log"
}
```

Status values:

- `completed`
- `failed`
- `timeout`
- `blocked`
- `no_changes`

### `agy_get_diff`

Returns the current git diff for the workspace, optionally scoped to files.

Input:

```json
{
  "workspace": "C:\\path\\to\\repo",
  "files": []
}
```

Output:

```json
{
  "diff": "..."
}
```

### `agy_get_changed_files`

Returns changed files based on `git status --short`.

Input:

```json
{
  "workspace": "C:\\path\\to\\repo"
}
```

Output:

```json
{
  "changed_files": [
    "app.py",
    "tests/test_app.py"
  ]
}
```

### `agy_get_run_log`

Returns a bounded log excerpt for a prior run.

Input:

```json
{
  "run_id": "20260628-153500-a1b2c3",
  "max_chars": 12000
}
```

Output:

```json
{
  "run_id": "20260628-153500-a1b2c3",
  "log_excerpt": "..."
}
```

## AGY CLI Invocation

The MCP server should construct a prompt file or structured prompt, then call:

```powershell
agy --add-dir "<workspace>" --print --print-timeout 20m --sandbox "<prompt>"
```

If a model is supplied:

```powershell
agy --model "<model>" --add-dir "<workspace>" --print --print-timeout 20m --sandbox "<prompt>"
```

Do not use `--dangerously-skip-permissions` by default.

If AGY cannot complete non-interactively because it needs permission approval, the MCP server should return `blocked` and include the shortest useful diagnostic. Permission bypass can be added later as an explicit opt-in.

## Prompt Template

The MCP server should give AGY a narrow implementer prompt:

```text
You are AGY acting as an implementation worker for Codex.

Workspace:
<workspace>

Task:
<task>

Acceptance criteria:
<acceptance_criteria>

Test command:
<test_command>

Rules:
- Make the smallest correct code change.
- Prefer existing project patterns.
- Do not modify unrelated files.
- Run the test command if provided.
- At the end, report:
  - changed files
  - what changed
  - test command and result
  - known issues or blockers
```

Codex should still verify the final diff and rerun important tests where practical.

## Run Records

Each run should create a directory:

```text
runs/<run_id>/
  request.json
  prompt.txt
  stdout.log
  stderr.log
  result.json
```

`result.json` should hold the compact structured result returned to Codex.

The MCP server should avoid returning full logs by default. Long logs should be retrieved only with `agy_get_run_log`.

## Safety and Permissions

The MCP server should require `workspace` to be an existing directory.

The first version should reject:

- empty workspace paths
- paths outside an allowed root list, if configured
- missing AGY executable
- timeout values above a configured maximum

The first version should not:

- delete files
- reset git state
- commit changes
- push branches
- auto-approve AGY permissions

Codex remains the reviewer and should not accept AGY output solely because AGY reports success.

## Error Handling

If AGY exits non-zero, return:

```json
{
  "status": "failed",
  "exit_code": 1,
  "summary": "AGY exited with an error.",
  "known_issues": [
    "short diagnostic"
  ],
  "log_path": "..."
}
```

If AGY times out, kill the process and return `timeout`.

If AGY asks for login, permission, or network access that the MCP process cannot provide, return `blocked`.

## Testing Plan

Test the MCP server in stages:

1. `agy_status` finds the installed CLI.
2. `agy_get_changed_files` works in a git repository.
3. `agy_get_diff` returns a bounded diff.
4. `agy_execute_task` can run a harmless no-op prompt in a temporary workspace.
5. `agy_execute_task` can make a small controlled change in a disposable repository.
6. Codex can review the resulting diff and rerun the relevant test command.

## Codex Workflow

For real tasks, Codex should use this sequence:

1. Understand the user request and define acceptance criteria.
2. Call `agy_execute_task`.
3. Inspect `changed_files`.
4. Call `agy_get_diff`.
5. Rerun key tests directly from Codex when feasible.
6. Either accept, ask AGY for a follow-up fix, or take over manually.

This preserves the intended split:

```text
AGY writes and tests.
Codex reviews and accepts.
```

## Open Questions

1. Should the MCP server live inside each project, or in a personal global tools directory?
2. Should AGY runs be allowed only inside the current workspace root?
3. Should there be an explicit opt-in for `--dangerously-skip-permissions`?
4. Should Codex pass AGY a full implementation plan or only the immediate task?

Recommended defaults:

- Store the MCP server in a personal tools directory once stable.
- Restrict workspaces to configured allowed roots.
- Do not enable `--dangerously-skip-permissions` in version 1.
- Pass only the immediate task plus acceptance criteria to reduce token use.
