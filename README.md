# Keithley 3706A-S / 3723-ST + Keithley 2400 Continuity Scanner

Notebook-first tool for controlling a Keithley 3706A-S with a 3723-ST multiplexer terminal board and a Keithley 2400 source meter for continuity scanning.

The original Flask UI is still present as a legacy prototype, but the recommended workflow is `keithley_switcher.ipynb`.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

For Windows GPIB adapters, install the vendor VISA runtime first, such as NI-VISA or Keysight IO Libraries. The app uses the default PyVISA backend so it can find that runtime.

For VS Code Notebook use, select the AI conda kernel if that is where PyVISA is installed:

```text
C:\Users\liy56\.conda\envs\AI\python.exe
```

If needed, install the kernel dependencies into that exact environment:

```powershell
C:\Users\liy56\.conda\envs\AI\python.exe -m pip install -r requirements.txt
C:\Users\liy56\.conda\envs\AI\python.exe -m ipykernel install --user --name electrical-switcher-ai --display-name "Electrical Switcher AI"
```

## Notebook Workflow

Open `keithley_switcher.ipynb` in VS Code or Jupyter.

The Notebook provides:

- VISA resource detection with `*IDN?`
- Manual resource overrides for the 3706A-S and 2400
- Connect/disconnect controls
- Manual 3706 channel close/open/open all controls
- Emergency safe state button: 2400 output off plus 3706 open all
- Generated A x B scans
- Manual channel pair scans
- 2400 source voltage/current settings
- Stop on first scan error option
- Safe scan orchestration
- pandas DataFrame output and CSV saving

The per-pair safety sequence is:

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

## 3723-ST Wiring Note

The 3723-ST is a multiplexer terminal board, not a matrix. A generated A x B scan assumes the DUT ports are wired to two mux banks, for example:

- 2400 FORCE HI -> MUX1 OUT H
- 2400 FORCE LO -> MUX2 OUT H
- A ports -> MUX1 channels, currently defaulting to slot 4 channels `4001` to `4030`
- B ports -> MUX2 channels, currently defaulting to slot 4 channels `4031` to `4060`

The current lab wiring uses the slot 4 MUX outputs, so the Notebook defaults to `4001-4060`. If you move the 2400 leads to another slot's MUX OUT terminals, change the channel prefix manually.

## Manual Switch Control

The Notebook includes a manual 3706 control panel for individual switch operations:

- `Close`: close channels such as `1001`, `1001,1002`, or `1001:1008`
- `Open`: open the entered channels
- `Open All`: open every 3706 relay channel
- `Refresh Closed`: query `channel.getclose()`
- `Emergency Off`: turn the 2400 output off and then open all 3706 channels

Before manually changing relays, make sure the 2400 output is off unless you intentionally use the `Emergency Off` button first.

## Stopping A Scan

The Notebook defaults to `Stop on first ERROR`, so relay errors such as Keithley 350/360-style switch errors stop the remaining pairs instead of continuing through the list.

For immediate abort while a cell is running, use Jupyter `Kernel > Interrupt Kernel`. The scan code attempts to turn the 2400 output off and open all 3706 channels during cleanup.

## Saving Results

The CSV save path can be typed manually or selected with the Notebook Browse widget. If Browse is not visible, install the optional widget dependency:

```powershell
python -m pip install ipyfilechooser
```

## Legacy Flask Prototype

```powershell
python app.py
```

Open `http://127.0.0.1:5000/`.

## Test

```powershell
python -m unittest discover -s tests -v
```

For pytest:

```powershell
python -m pytest -q
```

## AGY MCP Server

This repository includes a small local MCP server that lets Codex call the Antigravity CLI (`agy.exe`) as an implementation worker. Codex remains responsible for reviewing diffs and verifying test results.

Run the MCP tests:

```powershell
python -m pytest tests/test_agy_mcp_core.py tests/test_agy_mcp_server.py -q
```

Example Codex MCP config:

```toml
[mcp_servers.agy]
command = "python"
args = ["C:\\Users\\liy56\\OneDrive - Aalto University\\Aalto University\\Work\\Experiment operation\\Electrical switcher\\agy_mcp\\server.py"]
startup_timeout_sec = 10
tool_timeout_sec = 1800
```

If `agy` is not on PATH, set `AGY_MCP_AGY_PATH` to the full path of `agy.exe`.

## Channel Format

Accepted channel inputs are intentionally narrow:

- `1001`
- `1001,1002`
- `1001:1008`
- `1001,1003:1006`

Raw TSP commands are available in the console. Query mode wraps expressions with `print(...)`; write mode sends the command as-is.
