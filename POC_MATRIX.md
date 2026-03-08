# PySide6 POC Decision Matrix

Goal: decide whether a PySide6-based UI POC is acceptable for this repo, using
repeatable, command-driven measurements.

Artifacts:
- `pyside_poc.py` (POC UI entrypoint)

## Gates (PASS/FAIL)

| Metric | Gate (PASS) | FAIL rule | Why it matters |
| --- | ---: | --- | --- |
| Disk footprint (PySide6 venv delta) | <= 600 MB | > 600 MB | Impacts CI cache, local dev disk usage, and distribution practicality |
| Startup time (to `window.show()`) | <= 1.50 s | > 1.50 s | Impacts perceived responsiveness and UX viability |
| Idle memory (RSS after 5s) | <= 250 MB | > 250 MB | Impacts background resource cost and multi-app workflows |

Notes:
- These gates are intentionally strict enough to be decision-driving.
- Always record OS, Python version, and PySide6 version with the measurements.

## Measurement Steps (Commands)

All steps below are manual, but command-driven (no subjective judgments).

### 0) Create a clean venv for the POC

Unix/macOS:

```bash
python3 -m venv .venv-pyside6-poc
source .venv-pyside6-poc/bin/activate
python3 -m pip install -U pip
```

Windows PowerShell:

```powershell
python -m venv .venv-pyside6-poc
.\.venv-pyside6-poc\Scripts\Activate.ps1
python -m pip install -U pip
```

### 1) Disk footprint (venv delta)

1) Measure baseline venv size (before PySide6 install):

Unix/macOS:

```bash
du -sk .venv-pyside6-poc
```

Windows PowerShell:

```powershell
(Get-ChildItem -Recurse .\.venv-pyside6-poc | Measure-Object -Sum Length).Sum
```

2) Install PySide6:

```bash
python3 -m pip install PySide6
```

3) Measure venv size again:

Unix/macOS:

```bash
du -sk .venv-pyside6-poc
```

Windows PowerShell:

```powershell
(Get-ChildItem -Recurse .\.venv-pyside6-poc | Measure-Object -Sum Length).Sum
```

4) Record delta:
- Unix/macOS: delta_MB = (after_kb - before_kb) / 1024
- Windows: delta_MB = (after_bytes - before_bytes) / (1024 * 1024)

### 2) Startup time (to `window.show()`)

1) Capture versions:

```bash
python3 -V
python3 -c "import PySide6; print('PySide6', PySide6.__version__)"
```

2) Run the POC with timing enabled (auto-quit so it is scriptable):

```bash
python3 pyside_poc.py --measure-startup --quit-after 0.2
```

Expected output includes a single line like:

```text
startup_seconds import=0.1234 ui=0.0456 show=0.2345
```

Gate uses: `show`.

Optional (repeat 5 times):

```bash
for i in 1 2 3 4 5; do python3 pyside_poc.py --measure-startup --quit-after 0.2; done
```

### 3) Idle memory (RSS after 5 seconds)

1) Start the app and print PID (keep it alive long enough to sample):

```bash
python3 pyside_poc.py --print-pid --quit-after 30
```

2) In a second terminal, wait 5 seconds then sample RSS:

Unix/macOS:

```bash
ps -o rss= -p <PID>
```

Interpretation: output is RSS in KB. Convert to MB: MB = KB / 1024.

Windows PowerShell:

```powershell
Get-Process -Id <PID> | Select-Object Id, WorkingSet64
```

Interpretation: `WorkingSet64` is bytes. Convert to MB: MB = bytes / (1024 * 1024).
