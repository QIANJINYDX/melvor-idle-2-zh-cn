$ErrorActionPreference = 'Stop'
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'venv failed' }
& .\.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple pyinstaller==6.22.3
if ($LASTEXITCODE -ne 0) { throw 'dependency installation failed' }
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'tests failed' }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name Melvor2-Chinese-Enabler patcher.py
if ($LASTEXITCODE -ne 0) { throw 'build failed' }
