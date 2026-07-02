# Codex Review Checklist

当 AGY 完成双 2400 SD/Gate sweep 后，Codex 使用这份清单验收。

Codex 负责最终判断。AGY 不应该把任务标记为 `ACCEPTED`。

## 1. 阅读交接文件

- [ ] 阅读 `.agent-tasks/current-task.md`。
- [ ] 阅读 `.agent-tasks/agy-report.md`。
- [ ] 确认 AGY report 状态是 `READY_FOR_CODEX_REVIEW`。
- [ ] 确认 AGY 填写了修改文件、测试、手动检查、已知问题和问题。

如果 report 仍是 `READY_FOR_AGY` 或内容明显是模板，不要验收通过。

## 2. 保护已有工作

- [ ] 运行 `git status --short`。
- [ ] 判断哪些文件是 AGY 本次改的。
- [ ] 判断是否存在用户自己的无关改动。
- [ ] 不要 revert 或覆盖用户的无关改动。

特别注意：Notebook 可能因为执行 cell 产生无关 diff，需要区分真实代码改动和 execution state 改动。

## 3. 检查 diff 范围

预期可能修改：

- `scan_logic.py`
- `keithley2400.py`
- `keithley_switcher.ipynb`
- `README.md`
- `tests/test_scan_logic.py`
- `tests/test_keithley2400.py`
- `tests/test_dual_2400_scan.py`

检查：

- [ ] 没有无关重构。
- [ ] 没有删除 Flask legacy 文件，除非用户明确要求。
- [ ] 没有删除原单 2400 scan。
- [ ] 没有删除手动 switcher control。
- [ ] 没有重新加入 `slot.cardtype` 自动探测。
- [ ] 没有新增不必要依赖。

## 4. 检查双 2400 功能

- [ ] Notebook 中有明确的 Switcher / SD 2400 / Gate 2400 三个角色。
- [ ] 可以手动选择 SD 2400 和 Gate 2400 resource。
- [ ] 默认禁止 SD 和 Gate 使用同一个 VISA resource。
- [ ] SD fixed bias 支持 source voltage 或 source current。
- [ ] Gate sweep 支持 source voltage 或 source current。
- [ ] Gate sweep 支持 start / stop / step。
- [ ] Gate sweep 支持正向和反向，拒绝 step 为 0。
- [ ] Gate output mode 至少支持 hold-on 或 toggle-each-point 中的一个；如果两个都实现，要检查行为正确。
- [ ] 每个 SD pair 会展开为多个 gate setpoint measurement row。

## 5. 检查硬件安全

这是本任务最高优先级。

- [ ] 每次 relay 切换前，SD 2400 output off。
- [ ] 每次 relay 切换前，Gate 2400 output off。
- [ ] `switch.open_all()` 在 close selected pair 前调用。
- [ ] 每个 SD pair 结束后，Gate 2400 output off。
- [ ] 每个 SD pair 结束后，SD 2400 output off。
- [ ] 每个 SD pair 结束后，3706 open all。
- [ ] 异常路径也会尽力关闭两台 2400 output。
- [ ] 异常路径也会尽力 3706 open all。
- [ ] Emergency Off 同时关闭两台 2400 output 并 open all。
- [ ] `stop_on_error=True` 时，第一个 `ERROR` 后停止后续 pair。

如果这些安全点有任何一个不满足，应设置 `CHANGES_REQUESTED`。

## 6. 检查数据格式

输出应是一行一个：

```text
SD pair + gate setpoint + measurement result
```

检查 DataFrame / CSV column schema 是否稳定，至少应包含：

```text
run_id
timestamp_iso
elapsed_s
operator_note
switch_idn
sd_2400_idn
gate_2400_idn
slot
sd_pair_index
sd_channel_a
sd_channel_b
sd_pair_label
gate_step_index
gate_source_mode
gate_setpoint
gate_voltage_V
gate_current_A
sd_source_mode
sd_setpoint
sd_voltage_V
sd_current_A
sd_resistance_ohm
sd_conductance_S
sd_compliance
gate_compliance
relay_settle_s
gate_settle_s
status
error_message
```

检查计算规则：

- [ ] resistance 用 SD voltage/current 计算。
- [ ] conductance 用 SD current/voltage 计算。
- [ ] 分母缺失或接近 0 时不会产生误导性数值。
- [ ] 仪器错误进入 `status` 和 `error_message`，不会伪装成有效数据。

## 7. 检查测试

应有测试覆盖：

- [ ] Gate sweep point generation。
- [ ] 正向和反向 sweep。
- [ ] step 为 0 报错。
- [ ] 双 2400 safe sequence。
- [ ] 异常 cleanup。
- [ ] stop-on-first-error。
- [ ] normalized row columns。
- [ ] SD/Gate resource 不能相同。
- [ ] 现有单 2400 scan 测试仍通过。

建议运行：

```powershell
python -m unittest discover -s tests -v
python -m pytest tests/test_channels.py tests/test_app.py tests/test_keithley2400.py tests/test_scan_logic.py -q
```

如果 AGY 新增了测试文件，也运行它，例如：

```powershell
python -m pytest tests/test_dual_2400_scan.py -q
```

## 8. Notebook 检查

- [ ] Notebook 没有大量无关 output。
- [ ] Notebook 没有无关 execution count churn，或 churn 很小且可接受。
- [ ] 关键 import 能看出和 Python 模块一致。
- [ ] UI 文案能让用户分清 SD 2400 和 Gate 2400。
- [ ] 默认通道仍是 slot 4：`4001-4030` 和 `4031-4060`。
- [ ] 用户能保存 CSV。

## 9. README 检查

- [ ] README 说明单 2400 continuity scan 仍可用。
- [ ] README 说明双 2400 SD/Gate sweep 模式。
- [ ] README 说明 Switcher 只切 SD pair，Gate 2400 默认直接接 gate。
- [ ] README 说明真实硬件测试前使用低 compliance 和小 pair list。
- [ ] README 说明每行数据对应一个 SD pair + gate setpoint。

## 10. 做决定

### `ACCEPTED`

只有当下面条件都满足时使用：

- 功能满足 `current-task.md` 验收标准。
- 相关测试通过，或未运行原因合理且已记录。
- 安全流程没有明显漏洞。
- 没有必须返工的问题。

更新状态：

```text
Status: ACCEPTED
Owner: User
```

然后向用户说明改了什么、验证了什么、剩余注意事项。

### `CHANGES_REQUESTED`

如果存在以下任一情况，使用该状态：

- 安全流程不满足。
- 测试失败且与任务相关。
- Notebook 不能区分 SD/Gate 角色。
- 数据格式不稳定或缺关键字段。
- 单 2400 旧功能被破坏。
- AGY 报告缺少关键信息。

更新 `current-task.md`：

```text
Status: CHANGES_REQUESTED
Owner: AGY
```

并在 `Codex 要求的返工` 区域写明确 checklist。

## 11. 返工后再次验收

AGY 返工回来后：

- [ ] 阅读更新后的 AGY report。
- [ ] 尽量只检查上次 review 后的新 diff。
- [ ] 重新运行相关验证。
- [ ] 决定 `ACCEPTED` 或再次 `CHANGES_REQUESTED`。
