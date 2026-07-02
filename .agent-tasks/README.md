# AGY / Codex 交接流程

这个目录用于在 Codex 和 AGY 之间交接一次具体开发任务。它不是复杂的项目管理系统，只记录当前任务、AGY 完成报告和 Codex 验收清单。

推荐用法很简单：

- Codex 写清楚任务、范围、约束和验收标准。
- AGY 读取任务并实现，不提交 git commit。
- AGY 完成后填写报告，把状态交给 Codex 验收。
- Codex 检查 diff、运行必要验证，然后接受或要求返工。
- 用户决定什么时候开始下一步、是否提交和推送。

## 文件说明

- `.agent-tasks/current-task.md`：当前交给 AGY 的任务。通常由 Codex 创建和更新。
- `.agent-tasks/agy-report.md`：AGY 的完成报告。AGY 实现完成后填写。
- `.agent-tasks/review-checklist.md`：Codex 验收时使用的检查清单。
- `.agent-tasks/archive/`：可选，用于保存已完成任务的快照。

## 当前任务

当前 `current-task.md` 已经准备好交给 AGY：实现“两台 Keithley 2400 + switcher 联动”的 SD/Gate sweep 功能。

可以直接在 AGY / Antigravity 中发送：

```text
Read .agent-tasks/current-task.md and implement the task.
When finished, fill out .agent-tasks/agy-report.md.
Do not commit.
```

AGY 完成后，回到 Codex 发送：

```text
请根据 .agent-tasks/agy-report.md 验收 AGY 的工作。
```

## Heartbeat 自动预审

如果不想反复手动检查 AGY 是否完成，可以在本地开一个 heartbeat：

```powershell
python .agent-tasks/heartbeat.py --watch
```

它会定期检查 `.agent-tasks/agy-report.md`。当 AGY 把状态改成 `READY_FOR_CODEX_REVIEW` 时，heartbeat 会自动运行：

- `git status --short`
- `git diff --name-only`
- `git diff --check`
- 当前仓库的默认 unittest / pytest 命令

然后生成：

```text
.agent-tasks/codex-auto-review.md
```

这个文件是自动预审报告，不等于最终 Codex 验收。AGY 完成后，你可以回到 Codex 发送：

```text
请根据 .agent-tasks/agy-report.md 和 .agent-tasks/codex-auto-review.md 做最终验收。
```

只运行一次 heartbeat：

```powershell
python .agent-tasks/heartbeat.py --once
```

heartbeat 不依赖 AGY MCP，不调用 Codex API，不会 commit。它只做本地检查和报告生成。

## 状态字段

请只使用下面四个状态值，拼写保持一致。

### `READY_FOR_AGY`

表示 Codex 已经把任务写好，AGY 可以开始实现。

使用时机：

- `current-task.md` 已经写明目标、背景、可编辑文件、约束和验收标准。
- 任务还没有开始，或者 Codex 已经根据返工要求重新整理好了任务。

谁来设置：Codex。

### `READY_FOR_CODEX_REVIEW`

表示 AGY 已经完成实现，等待 Codex 验收。

使用时机：

- AGY 已经完成代码或文档修改。
- AGY 已经填写 `agy-report.md`。
- AGY 已经记录运行过的测试、手动检查、已知问题和疑问。
- AGY 停止继续修改，等待 Codex 检查。

谁来设置：AGY。

### `CHANGES_REQUESTED`

表示 Codex 验收后发现需要返工。

使用时机：

- 实现没有满足验收标准。
- 测试失败，且失败和本次任务相关。
- 改动范围过大或包含无关修改。
- 安全、错误处理、硬件控制流程仍有风险。
- AGY 报告不完整，无法判断结果。

谁来设置：Codex。Codex 应该在 `current-task.md` 的返工区域写清楚具体要改什么。

### `ACCEPTED`

表示 Codex 已经验收通过。

使用时机：

- 验收标准已经满足。
- 相关测试通过，或者未运行的原因已经清楚记录。
- diff 范围合理，没有必须处理的风险。
- 不再需要 AGY 返工。

谁来设置：Codex。

注意：`ACCEPTED` 不等于已经提交 git commit。是否 commit/push 仍然由用户决定。

## 标准流程

### 1. 用户让 Codex 创建任务

示例：

```text
请创建一个 AGY 任务：给 Notebook 扫描结果增加 CSV 路径校验。
```

Codex 应该更新 `current-task.md`，必要时清空或重置 `agy-report.md`，并设置：

```text
Status: READY_FOR_AGY
Owner: AGY
```

### 2. 用户让 AGY 实现

在 AGY / Antigravity 中打开同一个仓库，然后发送：

```text
Read .agent-tasks/current-task.md and implement the task.
When finished, fill out .agent-tasks/agy-report.md.
Do not commit.
```

AGY 应该读取任务、查看指定文件、检查 `git status --short`、完成最小必要改动、尽量运行任务中列出的检查，然后填写 `agy-report.md`。

完成后，AGY 把报告状态设为：

```text
Status: READY_FOR_CODEX_REVIEW
```

### 3. 用户让 Codex 验收

回到 Codex 后发送：

```text
请根据 .agent-tasks/agy-report.md 验收 AGY 的工作。
```

Codex 应该读取任务和报告，检查 `git status --short` 和 `git diff`，运行必要验证，并对照验收标准判断结果。

### 4. Codex 接受或要求返工

如果通过，Codex 设置：

```text
Status: ACCEPTED
Owner: User
```

如果需要返工，Codex 设置：

```text
Status: CHANGES_REQUESTED
Owner: AGY
```

并在 `current-task.md` 的返工区域写清楚具体事项。

### 5. 返工循环

用户把同一个任务再交给 AGY。AGY 只处理 Codex 写出的返工项，完成后再次更新报告并设为 `READY_FOR_CODEX_REVIEW`。Codex 再次验收，直到 `ACCEPTED` 或用户决定停止。

## 基本规则

- 不要自动 commit，除非用户明确要求。
- 不要隐藏不确定性，直接写进报告。
- 每次任务尽量小，方便 review。
- 文件路径要写具体。
- 修改前先看 `git status --short`。
- 不要覆盖用户自己的改动。
- AGY 不设置 `ACCEPTED`，只能提交给 Codex review。
- Codex 不能只看 AGY 总结就接受，必须检查 diff 和验证结果。
