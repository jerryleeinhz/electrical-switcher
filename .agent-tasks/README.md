# AGY / Codex Handoff Workflow

这个目录用于方案 D：Codex 负责任务拆解、验收和回归检查；AGY 负责在同一个项目里写代码、改代码、运行它能运行的测试。

## 角色分工

- User: 决定目标，并在 Codex 和 AGY 之间切换。
- Codex: 写清楚任务、约束、验收标准；AGY 完成后读取 diff、运行测试、验收或退回修改。
- AGY: 读取 `.agent-tasks/current-task.md`，按要求修改代码，并填写 `.agent-tasks/agy-report.md`。

## 推荐流程

1. 在 Codex 里说：`请为 AGY 创建任务：...`
2. Codex 更新 `.agent-tasks/current-task.md`。
3. 在 AGY / Antigravity 中打开同一个项目目录，然后输入：

   ```text
   请读取 .agent-tasks/current-task.md，按验收标准实现。
   完成后请填写 .agent-tasks/agy-report.md。
   不要提交 git commit。
   ```

4. AGY 完成后，回到 Codex 说：

   ```text
   请根据 .agent-tasks/agy-report.md 验收 AGY 的改动。
   ```

5. Codex 会检查 `git diff`、运行测试，并在必要时把返工意见写回 `.agent-tasks/current-task.md`。

## 状态值

在 `current-task.md` 和 `agy-report.md` 中使用这些状态：

- `READY_FOR_AGY`: Codex 已经写好任务，等待 AGY 实现。
- `IN_PROGRESS`: AGY 正在处理。
- `READY_FOR_CODEX_REVIEW`: AGY 已完成，等待 Codex 验收。
- `CHANGES_REQUESTED`: Codex 发现问题，需要 AGY 返工。
- `ACCEPTED`: Codex 验收通过。

## 文件说明

- `.agent-tasks/current-task.md`: 当前交给 AGY 的任务。
- `.agent-tasks/agy-report.md`: AGY 完成后的报告。
- `.agent-tasks/review-checklist.md`: Codex 验收时使用的清单。
- `.agent-tasks/archive/`: 完成后的旧任务可以移动到这里备份。

