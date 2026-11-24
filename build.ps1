$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Khong tao duoc moi truong Python 3.12.' }
$buildPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
& $buildPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Khong cai duoc thu vien.' }
& $buildPython -m PyInstaller --noconfirm --onefile --windowed --name Douyin-Downloader --collect-all playwright --collect-all imageio_ffmpeg --distpath dist --workpath build --specpath build app.py
if ($LASTEXITCODE -ne 0) { throw 'Dong goi that bai.' }
Write-Host 'Da tao dist/Douyin-Downloader.exe'
