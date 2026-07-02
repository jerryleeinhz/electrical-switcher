import importlib.util
from pathlib import Path
from types import SimpleNamespace


def load_heartbeat_module():
    module_path = Path(__file__).resolve().parents[1] / ".agent-tasks" / "heartbeat.py"
    spec = importlib.util.spec_from_file_location("agent_heartbeat", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_status_reads_report_status():
    heartbeat = load_heartbeat_module()

    assert heartbeat.parse_status("# AGY Report\n\nStatus: READY_FOR_CODEX_REVIEW\n") == "READY_FOR_CODEX_REVIEW"


def test_once_skips_when_report_is_not_ready(tmp_path):
    heartbeat = load_heartbeat_module()
    workspace = tmp_path
    tasks = workspace / ".agent-tasks"
    tasks.mkdir()
    (tasks / "agy-report.md").write_text("Status: READY_FOR_AGY\n", encoding="utf-8")

    result = heartbeat.run_once(workspace, runner=lambda *args, **kwargs: None, test_commands=[])

    assert result["status"] == "SKIPPED"
    assert "not READY_FOR_CODEX_REVIEW" in result["reason"]
    assert not (tasks / "codex-auto-review.md").exists()


def test_once_generates_review_report_when_ready(tmp_path):
    heartbeat = load_heartbeat_module()
    workspace = tmp_path
    tasks = workspace / ".agent-tasks"
    tasks.mkdir()
    (tasks / "agy-report.md").write_text(
        "Status: READY_FOR_CODEX_REVIEW\n\n## 完成摘要\nImplemented feature.\n",
        encoding="utf-8",
    )
    (tasks / "current-task.md").write_text("Status: READY_FOR_AGY\n", encoding="utf-8")

    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        if command == ["git", "status", "--short"]:
            return SimpleNamespace(returncode=0, stdout=" M scan_logic.py\n?? tests/test_dual_2400_scan.py\n", stderr="")
        if command == ["git", "diff", "--name-only"]:
            return SimpleNamespace(returncode=0, stdout="scan_logic.py\ntests/test_dual_2400_scan.py\n", stderr="")
        if command == ["git", "diff", "--check"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="2 passed", stderr="")

    result = heartbeat.run_once(
        workspace,
        runner=runner,
        test_commands=[["python", "-m", "pytest", "tests/test_dual_2400_scan.py", "-q"]],
        now=lambda: "2026-07-02T12:00:00",
    )

    report = (tasks / "codex-auto-review.md").read_text(encoding="utf-8")
    assert result["status"] == "PASS"
    assert "Status: PASS" in report
    assert "READY_FOR_CODEX_REVIEW" in report
    assert "scan_logic.py" in report
    assert "python -m pytest tests/test_dual_2400_scan.py -q" in report
    assert ["git", "diff", "--check"] in calls


def test_once_fails_for_disallowed_changed_file(tmp_path):
    heartbeat = load_heartbeat_module()
    workspace = tmp_path
    tasks = workspace / ".agent-tasks"
    tasks.mkdir()
    (tasks / "agy-report.md").write_text("Status: READY_FOR_CODEX_REVIEW\n", encoding="utf-8")
    (tasks / "current-task.md").write_text("Status: READY_FOR_AGY\n", encoding="utf-8")

    def runner(command, **kwargs):
        if command == ["git", "status", "--short"]:
            return SimpleNamespace(returncode=0, stdout=" M unrelated.txt\n", stderr="")
        if command == ["git", "diff", "--name-only"]:
            return SimpleNamespace(returncode=0, stdout="unrelated.txt\n", stderr="")
        if command == ["git", "diff", "--check"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    result = heartbeat.run_once(workspace, runner=runner, test_commands=[])

    report = (tasks / "codex-auto-review.md").read_text(encoding="utf-8")
    assert result["status"] == "FAILED"
    assert "Files outside expected AGY scope" in report
    assert "unrelated.txt" in report


def test_state_prevents_reprocessing_same_ready_report(tmp_path):
    heartbeat = load_heartbeat_module()
    workspace = tmp_path
    tasks = workspace / ".agent-tasks"
    tasks.mkdir()
    report_path = tasks / "agy-report.md"
    report_path.write_text("Status: READY_FOR_CODEX_REVIEW\n", encoding="utf-8")
    (tasks / "current-task.md").write_text("Status: READY_FOR_AGY\n", encoding="utf-8")

    def runner(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    first = heartbeat.run_once(workspace, runner=runner, test_commands=[], use_state=True)
    second = heartbeat.run_once(workspace, runner=runner, test_commands=[], use_state=True)

    assert first["status"] == "PASS"
    assert second["status"] == "SKIPPED"
    assert "already reviewed" in second["reason"]
