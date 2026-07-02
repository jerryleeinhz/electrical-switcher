# Current AGY Task

Status: READY_FOR_AGY
Owner: AGY
Created by: Codex
Last updated: 2026-07-02

## 目标

实现“两台 Keithley 2400 + Keithley 3706A-S / 3723-ST switcher 联动”的 Notebook 扫描功能。

新的实验模式中，一台 2400 作为 source-drain instrument，简称 `SD 2400`；另一台 2400 作为 gate instrument，简称 `Gate 2400`。Switcher 负责切换不同的 source-drain channel pair。每导通一对 SD 后，SD bias 保持固定，Gate 2400 做 gate sweep，并记录每个 gate setpoint 下的 voltage、current、resistance、conductance 和完整元数据。

## 背景摘要

当前项目已经从 Flask 原型转为 Jupyter Notebook + ipywidgets 主流程，原因是 Flask 端口 5000 容易连接到旧 Python 进程并产生假错误。现在推荐入口是 `keithley_switcher.ipynb`。

当前硬件和接线结论：

- Switcher 是 Keithley 3706A-S。
- 端子板是 Keithley 3723-ST，对应 3723 multiplexer card。
- 3723 是 MUX，不是 matrix。
- 用户观察到当前实验室实际接在 slot 4 的 MUX 上，所以默认 channel prefix 是 `4000`。
- slot 4 下，MUX1 通道一般是 `4001-4030`，MUX2 通道一般是 `4031-4060`。
- 不要再用 `slot.cardtype` 自动探测卡槽；它之前触发过 3706 TSP runtime error。
- 当前已有单 2400 continuity scan，默认 A side `4001-4030`，B side `4031-4060`。

旧单 2400 安全流程必须保留：

```text
2400 output off
3706 open all
3706 close selected channels
wait settle time
2400 output on
measure
2400 output off
3706 open all
```

新双 2400 模式的核心安全规则：

```text
任何 3706 relay 切换之前，SD 2400 和 Gate 2400 的 output 都必须是 off。
```

## 需要先阅读的文件

- `keithley_switcher.ipynb` - 当前 Notebook UI 和扫描入口。
- `keithley2400.py` - 2400 连接、source 配置、output on/off、measure API。
- `keithley3706.py` - 3706 通道格式、open/close/open all、VISA detect。
- `scan_logic.py` - 当前 pair generation、continuity classification、单 2400 scan orchestration。
- `tests/test_scan_logic.py` - 当前 scan orchestration 测试风格。
- `tests/test_keithley2400.py` - 2400 fake instrument 测试风格。
- `README.md` - 当前用户说明，完成后需要更新新模式说明。

## 允许修改的文件

AGY 可以按需修改或新增这些文件：

- `scan_logic.py`
- `keithley2400.py`
- `keithley_switcher.ipynb`
- `README.md`
- `tests/test_scan_logic.py`
- `tests/test_keithley2400.py`
- `tests/test_dual_2400_scan.py`，如果更清晰可以新建

不要修改 AGY MCP server、Flask legacy UI、`.agent-tasks/` 以外的流程文档，除非实现确实需要并在报告中说明。

## 功能需求

### 1. 三个仪器角色

Notebook 中要明确区分三个角色：

- `Switcher`：Keithley 3706A-S。
- `SD 2400`：固定 source-drain bias，并测量 SD voltage/current。
- `Gate 2400`：执行 gate sweep，并测量 gate voltage/current。

要求：

- Detect instruments 仍然使用 PyVISA list resources 和 `*IDN?`。
- 如果检测到两个 2400，要允许用户手动指定哪个是 SD，哪个是 Gate。
- 不允许 SD 2400 和 Gate 2400 使用同一个 VISA resource，除非用户明确绕过；默认应报错。
- 现有单 2400 continuity scan 和手动 relay 控制不能被删除。

### 2. SD pair 选择

沿用当前 switcher pair 逻辑：

- A range / B range 自动生成 pair。
- 手动输入 pair，例如：

```text
4001,4031
4002,4032
```

默认仍然使用 slot 4：

- A start：`4001`
- A end：`4030`
- B start：`4031`
- B end：`4060`

### 3. SD fixed bias 设置

SD 2400 需要支持：

- source voltage 或 source current。
- fixed setpoint。
- compliance。
- SD settle time，必要时可复用已有 settle time。

### 4. Gate sweep 设置

Gate 2400 需要支持：

- source voltage 或 source current。
- start。
- stop。
- step 或 number of points，优先实现 step。
- compliance。
- gate settle time。
- gate output mode：
  - `hold_on_during_sweep`：Gate output 在整个 sweep 中保持 on，只改变 setpoint。
  - `toggle_each_point`：每个 gate point 单独 output on / measure / output off。

Gate sweep point generation 要放在纯 Python 函数里，方便测试。必须支持正向和反向 sweep，拒绝 step 为 0 的配置。

### 5. 双 2400 安全扫描流程

实现新的 scan orchestration，例如 `run_sd_gate_sweep(...)`，名字可由 AGY 根据代码风格调整，但要有测试覆盖。

概念流程：

```text
for each SD pair:
    SD 2400 output off
    Gate 2400 output off
    3706 open all
    3706 close selected SD pair
    wait relay settle time

    configure SD 2400 fixed bias
    configure Gate 2400 source mode and first/current setpoint

    SD 2400 output on
    for each gate setpoint:
        set Gate 2400 source level
        if gate mode is hold_on_during_sweep:
            Gate output should already be on after first setup
        if gate mode is toggle_each_point:
            Gate output on before measuring this point
        wait gate settle time
        measure SD 2400
        measure Gate 2400
        append one normalized row
        if gate mode is toggle_each_point:
            Gate output off

    Gate 2400 output off
    SD 2400 output off
    3706 open all
```

异常处理要求：

- 任何异常后都要尽力关闭两台 2400 output。
- 任何异常后都要尽力 `switch.open_all()`。
- 如果 `stop_on_error=True`，遇到第一个 `ERROR` 后停止后续 SD pair。
- 已经测到的数据不能因为后续错误丢失。
- 每个 error row 要有 `status="ERROR"` 和 `error_message`。

### 6. 规范化数据保存格式

采用一行一个 measurement point：

```text
one SD pair + one gate setpoint + one measured result = one row
```

建议 columns 至少包含：

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

计算规则：

- `sd_resistance_ohm = sd_voltage_V / sd_current_A`，但当 current 缺失或接近 0 时写 `None` / `NaN`。
- `sd_conductance_S = sd_current_A / sd_voltage_V`，但当 voltage 缺失或接近 0 时写 `None` / `NaN`。
- 不要把仪器错误伪装成 0 或有效数值。
- CSV 保存应使用这些稳定 column names，便于后续 Python / Origin / Excel 分析。

### 7. Notebook UI

在 `keithley_switcher.ipynb` 中增加双 2400 SD/Gate sweep 区域。UI 不需要花哨，但要能实际操作：

- 选择 / 显示 Switcher resource 和 IDN。
- 选择 / 显示 SD 2400 resource 和 IDN。
- 选择 / 显示 Gate 2400 resource 和 IDN。
- Connect / Disconnect / Emergency Off。
- SD pair 输入区域。
- SD fixed bias 参数。
- Gate sweep 参数。
- Run SD/Gate Sweep 按钮。
- 显示 pandas DataFrame。
- 保存 CSV。

Emergency Off 必须同时：

```text
SD 2400 output off
Gate 2400 output off
3706 open all
```

### 8. README 更新

更新 `README.md`，简要说明：

- 现有单 2400 continuity scan 仍可用。
- 新增 dual-2400 SD/Gate sweep 模式。
- 两台 2400 的角色和基本接线逻辑。
- CSV 数据是一行一个 `SD pair + gate setpoint`。
- 真实硬件验证前应使用低 compliance 和小 pair list。

## 验收标准

- [ ] 保留现有手动 switcher 控制和单 2400 continuity scan 功能。
- [ ] Notebook 能连接并区分 Switcher、SD 2400、Gate 2400 三个角色。
- [ ] SD 和 Gate 默认不能选择同一个 VISA resource。
- [ ] 能为每个 SD pair 执行 gate sweep。
- [ ] Relay 切换前，两台 2400 output 都会关闭。
- [ ] 异常、interrupt 或测量失败时，代码会尽力关闭两台 2400 output 并 open all。
- [ ] 输出 DataFrame / CSV 使用规范化 column names。
- [ ] 每个 gate setpoint 产生一行结果。
- [ ] 结果包含 SD voltage/current/resistance/conductance 和 Gate voltage/current。
- [ ] `stop_on_error=True` 时，第一个 error 后停止后续 pair。
- [ ] 增加或更新测试覆盖 gate sweep point generation、normalized row schema、安全调用顺序、异常 cleanup。
- [ ] README 说明新模式和安全注意事项。

## 建议验证命令

```powershell
python -m unittest discover -s tests -v
python -m pytest tests/test_channels.py tests/test_app.py tests/test_keithley2400.py tests/test_scan_logic.py -q
```

如果新增了 `tests/test_dual_2400_scan.py`，也要把它纳入 pytest 命令，例如：

```powershell
python -m pytest tests/test_dual_2400_scan.py -q
```

如果 Notebook 修改无法自动测试，AGY 要至少说明：

- 是否清理了不必要的 cell output。
- 是否检查了关键 cell 的 import 和函数调用。
- 是否没有连接真实仪器，因此硬件实测未运行。

## 实现提示

- 优先把可测试逻辑放在 `scan_logic.py`，Notebook 只负责 UI 和调用。
- 不要把双 2400 逻辑只写在 Notebook cell 里，否则很难测试。
- 尽量复用 `Keithley2400.configure_source_voltage()`、`configure_source_current()`、`output_on()`、`output_off()`、`measure()`。
- 如果需要动态改变 gate setpoint，可以在 `keithley2400.py` 中增加小而明确的方法，例如设置当前 source level；同时加 fake-instrument 测试。
- 不要重新引入 Flask 依赖或端口方案。
- 不要重新启用 `slot.cardtype` 探测。

## Codex 要求的返工

当前没有返工项。AGY 首次实现完成后，请填写 `.agent-tasks/agy-report.md` 并把报告状态改为 `READY_FOR_CODEX_REVIEW`。

## AGY 操作步骤

1. 完整阅读本文件。
2. 检查 `git status --short`，不要覆盖用户未提交改动。
3. 阅读列出的相关源码和测试。
4. 先补纯 Python 测试，再实现扫描逻辑。
5. 更新 Notebook UI。
6. 更新 README。
7. 运行建议测试。
8. 填写 `.agent-tasks/agy-report.md`。
9. 不要 commit，不要 push。
