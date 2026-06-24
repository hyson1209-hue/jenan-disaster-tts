# 재난 방송 TTS 대시보드 실행
# 사용: 우클릭 > PowerShell로 실행, 또는  powershell -ExecutionPolicy Bypass -File run.ps1
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# 이미 떠 있으면 중복 실행 방지
$running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*web\app.py*' }
if (-not $running) {
    Start-Process python -ArgumentList (Join-Path $here 'app.py') -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $here '_server.log') `
        -RedirectStandardError  (Join-Path $here '_server.err')
}

# 서버 응답 대기 후 브라우저 열기
for ($i=0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 1
    try { if ((Invoke-WebRequest 'http://127.0.0.1:5000/api/voices' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200) { break } } catch {}
}
Start-Process 'http://127.0.0.1:5000/'
Write-Host "대시보드: http://127.0.0.1:5000/  (종료: Stop-Process로 python 종료)"
