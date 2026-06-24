# Supertonic 한국어 TTS 모델 다운로드 + 압축 해제
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$dir  = Join-Path $root 'models'
New-Item -ItemType Directory -Path $dir -Force | Out-Null

$url = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/sherpa-onnx-supertonic-3-tts-int8-2026-05-11.tar.bz2'
$dst = Join-Path $dir 'supertonic-ko.tar.bz2'
$target = Join-Path $dir 'sherpa-onnx-supertonic-3-tts-int8-2026-05-11'

if (Test-Path $target) { Write-Host "이미 존재: $target"; return }

Write-Host "다운로드 중... (약 123MB)"
$ProgressPreference = 'SilentlyContinue'
Invoke-WebRequest -Uri $url -OutFile $dst -UseBasicParsing
Write-Host "압축 해제 중..."
tar -xf $dst -C $dir
Remove-Item $dst -ErrorAction SilentlyContinue
Write-Host "완료: $target"
