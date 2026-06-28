# Keithley 3706A-S Electrical Switcher

Local Flask UI for controlling Keithley 3706A-S switch channels through VISA/GPIB.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

For Windows GPIB adapters, install the vendor VISA runtime first, such as NI-VISA or Keysight IO Libraries. The app uses the default PyVISA backend so it can find that runtime.

## Run

```powershell
python app.py
```

Open `http://127.0.0.1:5000/`.

## Test

```powershell
python -m unittest discover -s tests -v
```

## Channel Format

Accepted channel inputs are intentionally narrow:

- `1001`
- `1001,1002`
- `1001:1008`
- `1001,1003:1006`

Raw TSP commands are available in the console. Query mode wraps expressions with `print(...)`; write mode sends the command as-is.
