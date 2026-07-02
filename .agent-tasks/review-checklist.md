# Codex Review Checklist

Codex 在验收 AGY 改动时使用这份清单。

## Before Review

- [ ] 读取 `.agent-tasks/current-task.md`。
- [ ] 读取 `.agent-tasks/agy-report.md`。
- [ ] 检查 `git status --short`，区分 AGY 改动和用户已有改动。
- [ ] 检查 `git diff`，确认没有无关大改。

## Functional Review

- [ ] 逐条核对 acceptance criteria。
- [ ] 检查边界情况和错误处理。
- [ ] 检查是否有硬件副作用、路径依赖、环境假设。
- [ ] 检查是否破坏已有 API 或工作流。

## Verification

- [ ] 运行建议测试命令。
- [ ] 如果测试无法运行，记录原因。
- [ ] 对高风险改动做额外手动检查。

## Decision

- [ ] `ACCEPTED`: 改动通过，可以由用户决定是否提交。
- [ ] `CHANGES_REQUESTED`: 把具体返工意见写回 `.agent-tasks/current-task.md`。

