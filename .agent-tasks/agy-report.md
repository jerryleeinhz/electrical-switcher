# AGY Report

Status: READY_FOR_AGY
Completed by: AGY
Last updated: YYYY-MM-DD

AGY 完成双 2400 SD/Gate sweep 实现后，请把 `Status` 改为 `READY_FOR_CODEX_REVIEW`，并填写下面所有区域。不要 commit。

## 完成摘要

简短说明本次实现了什么。

请覆盖这些点：

- 是否新增双 2400 SD/Gate sweep。
- 是否保留原单 2400 continuity scan 和手动 switcher 控制。
- Notebook UI 做了哪些新增。
- 数据保存格式是否使用规范化 columns。

## 修改文件

列出每个修改文件和原因。

示例：

- `scan_logic.py` - 新增 gate sweep point generation、dual-2400 scan orchestration、normalized row schema。
- `keithley2400.py` - 新增设置当前 source level 的方法。
- `keithley_switcher.ipynb` - 新增 SD 2400 / Gate 2400 UI 和 Run SD/Gate Sweep 按钮。
- `tests/test_dual_2400_scan.py` - 新增双 2400 安全流程和数据格式测试。
- `README.md` - 增加双 2400 使用说明。

## 实现细节

请说明：

- SD 2400 和 Gate 2400 如何连接和区分。
- 如何防止同一个 VISA resource 被同时用作 SD 和 Gate。
- Gate sweep point 如何生成，是否支持正向和反向 sweep。
- Gate output mode 支持哪些选项。
- 每个 measurement row 包含哪些关键字段。
- 发生异常时 cleanup 顺序是什么。

## 运行过的测试

粘贴准确命令和结果。

```text
python -m unittest discover -s tests -v
Result: ...

python -m pytest tests/test_channels.py tests/test_app.py tests/test_keithley2400.py tests/test_scan_logic.py tests/test_dual_2400_scan.py -q
Result: ...
```

如果某个测试无法运行，写出原因和错误信息。

## 手动检查

记录 Notebook 或手动检查结果。

请至少说明：

- 是否打开或检查了 `keithley_switcher.ipynb`。
- 是否确认新增 SD/Gate UI cell 不依赖真实仪器也能 import。
- 是否清理了不必要的 Notebook outputs / execution counts。
- 是否没有真实仪器连接，因此未做硬件实测。

如果做了真实仪器检查，请记录：

- 使用的 switcher resource。
- SD 2400 resource。
- Gate 2400 resource。
- 使用的 channel pair。
- 使用的 compliance。
- 是否确认 Emergency Off 有效。

## 数据格式确认

请确认输出 DataFrame / CSV 是否包含这些字段，或者说明差异原因：

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

## 安全确认

请逐项填写：

- [ ] Relay 切换前 SD 2400 output 会关闭。
- [ ] Relay 切换前 Gate 2400 output 会关闭。
- [ ] Scan 正常结束后 SD 2400 output 会关闭。
- [ ] Scan 正常结束后 Gate 2400 output 会关闭。
- [ ] Scan 正常结束后 3706 会 open all。
- [ ] 异常时会尽力关闭两台 2400 output。
- [ ] 异常时会尽力 3706 open all。
- [ ] Emergency Off 同时覆盖两台 2400 和 switcher。

## 已知问题

列出已知限制、风险或未确认点。

- 如果没有，写 `None`。

## 问题

写给 Codex 或用户的问题。

- 如果没有，写 `None`。

## 给 Codex 的 review 提示

请提醒 Codex 重点看：

- 双 2400 cleanup 是否真的覆盖所有异常路径。
- Notebook 是否有不必要输出。
- CSV column schema 是否稳定。
- 现有单 2400 scan 是否被破坏。

## AGY 自查

- [ ] 我在修改前检查了 `git status --short`。
- [ ] 我没有删除原有单 2400 continuity scan。
- [ ] 我没有删除手动 switcher 控制。
- [ ] 我没有重新启用 `slot.cardtype` 探测。
- [ ] 我没有 commit。
- [ ] 我记录了测试结果，或者说明了无法运行的原因。
- [ ] 我把 `Status` 设置为 `READY_FOR_CODEX_REVIEW`。
