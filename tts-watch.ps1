# 재난 텍스트 -> TTS 오디오 자동 변환 (Windows SAPI)
# 특정 폴더에 생기는 .txt 재난 문구를 한국어 음성 WAV로 변환한다.

# ===== 설정 (실제 방송 시스템 폴더로 교체) =====
$InputDir     = 'E:\jenan\input'            # 재난 텍스트가 떨어지는 폴더
$OutputDir    = 'E:\jenan\output'           # 변환된 오디오 저장 폴더
$ProcessedDir = Join-Path $InputDir 'processed'  # 처리 완료된 원본 보관
$VoiceName    = 'Microsoft Heami Desktop'   # 한국어 음성 (ko-KR)
$Rate          = 0                          # 기본 말속도 -10 ~ 10
$Volume        = 100                        # 볼륨 0 ~ 100
$PollSeconds   = 2                          # 폴더 확인 주기(초)
$ProsodyRate   = '-10%'                     # SSML 낭독 속도. 느릴수록 명료. 예: '-15%','0%'
$SentencePause = 400                        # 문장 사이 쉼(ms). 0이면 쉼 없음
# ===============================================

# 폴더 준비
foreach ($d in @($InputDir, $OutputDir, $ProcessedDir)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}

# SAPI 음성 합성기 준비
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try { $synth.SelectVoice($VoiceName) }
catch { Write-Warning "음성 '$VoiceName' 선택 실패 - 기본 음성 사용. ($_)" }
$synth.Rate   = $Rate
$synth.Volume = $Volume

# 파일이 완전히 쓰여질 때까지 대기 (감시 이벤트가 쓰기 완료 전 발생할 수 있음)
function Wait-FileReady {
    param([string]$Path, [int]$Retries = 20, [int]$DelayMs = 200)
    for ($i = 0; $i -lt $Retries; $i++) {
        try {
            $fs = [System.IO.File]::Open($Path, 'Open', 'Read', 'None')
            $fs.Close(); $fs.Dispose()
            return $true
        } catch { Start-Sleep -Milliseconds $DelayMs }
    }
    return $false
}

# 평문을 SSML로 변환: XML 이스케이프 + 문장 끝마다 쉼 삽입 (명료도 향상)
function Build-Ssml {
    param([string]$Text)
    $esc = [System.Security.SecurityElement]::Escape($Text)
    if ($SentencePause -gt 0) {
        $breakTag = '<break time="' + $SentencePause + 'ms"/>'
        $esc = [regex]::Replace($esc, '([\.!\?。！？]+)', ('$1' + $breakTag))
    }
    '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="ko-KR">' +
    '<prosody rate="' + $ProsodyRate + '">' + $esc + '</prosody></speak>'
}

# 단일 .txt -> .wav 변환
function Convert-File {
    param([string]$Path)

    $name = [System.IO.Path]::GetFileNameWithoutExtension($Path)

    if (-not (Wait-FileReady -Path $Path)) {
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 건너뜀(잠김): $name" -ForegroundColor Yellow
        return
    }

    # 한글 텍스트 UTF-8로 읽기 (BOM 자동 처리)
    $text = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
    if ([string]::IsNullOrWhiteSpace($text)) {
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 건너뜀(빈 파일): $name" -ForegroundColor Yellow
        return
    }

    $stamp   = Get-Date -Format 'yyyyMMdd_HHmmss'
    $wavPath = Join-Path $OutputDir ("{0}_{1}.wav" -f $stamp, $name)

    try {
        $synth.SetOutputToWaveFile($wavPath)
        $synth.SpeakSsml((Build-Ssml -Text $text))
    } finally {
        $synth.SetOutputToDefaultAudioDevice()
    }

    # 원본을 처리완료 폴더로 이동 (재처리 방지)
    $dest = Join-Path $ProcessedDir ("{0}_{1}.txt" -f $stamp, $name)
    Move-Item -LiteralPath $Path -Destination $dest -Force

    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 변환완료: $name -> $(Split-Path $wavPath -Leaf)" -ForegroundColor Green
}

Write-Host "재난 TTS 감시 시작" -ForegroundColor Cyan
Write-Host "  입력: $InputDir"
Write-Host "  출력: $OutputDir"
Write-Host "  음성: $VoiceName"
Write-Host "  주기: ${PollSeconds}초  (종료: Ctrl+C)`n"

# 폴링 방식 감시: 주기적으로 폴더를 스캔해 새 .txt를 변환한다.
# (FileSystemWatcher의 이벤트 스코프 문제를 피하고, 네트워크 공유에서도 안정적)
try {
    while ($true) {
        Get-ChildItem -Path $InputDir -Filter '*.txt' -File | ForEach-Object {
            $f = $_.FullName
            try { Convert-File -Path $f }
            catch { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 오류: $f - $_" -ForegroundColor Red }
        }
        Start-Sleep -Seconds $PollSeconds
    }
} finally {
    $synth.Dispose()
    Write-Host "`n감시 종료" -ForegroundColor Cyan
}
