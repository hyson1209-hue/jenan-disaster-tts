# 재난 방송 TTS (Disaster Broadcast TTS)

방송국 재난 방송을 위한 **오프라인 한국어 TTS 시스템**입니다.
재난 상황 발생 시 특정 폴더에 떨어지는 텍스트(`.txt`)를 한국어 음성으로 변환해 라디오 송출에 사용합니다.

재난 시 네트워크 장애를 가정해 **인터넷·API 키 없이 완전 오프라인**으로 동작하는 것을 목표로 합니다.

## 구성

| 구성요소 | 설명 |
|---|---|
| **웹 대시보드** (`web/`) | 운영자용. 재난 문서 확인 → 앵커(화자) 선택 → 옵션 설정 → 합성/미리듣기 → 파형 재생 → 송출. Flask + 자체 캔버스 파형(외부 JS 의존 0) |
| **폴더 감시 변환기** (`tts-watch.ps1`) | 무인용. `input/` 폴더를 감시해 새 `.txt`를 자동으로 음성(WAV)으로 변환. Windows SAPI(Heami) 기반 폴백 엔진 |
| **TTS 엔진** | [Supertonic v3](https://github.com/supertone-inc/supertonic) (Supertone Inc., **MIT 라이선스**) — 온디바이스 신경망 TTS, 화자 10명, 44.1kHz. [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)로 구동 |

## 요구 사항

- Windows 10/11, PowerShell
- Python 3.9+ (3.14 검증됨)
- Node.js (선택 — Playwright E2E 테스트용)

## 설치

```powershell
# 1) Python 의존성
python -m pip install -r requirements.txt

# 2) Supertonic 한국어 모델 다운로드 (약 123MB)
powershell -ExecutionPolicy Bypass -File scripts/download_model.ps1

# 3) 앵커 미리듣기 샘플 생성 (output/voices/)
python scripts/gen_previews.py
```

## 실행

```powershell
# 웹 대시보드 (http://127.0.0.1:5000)
powershell -ExecutionPolicy Bypass -File web/run.ps1

# 또는 무인 폴더 감시 변환기 (SAPI)
powershell -ExecutionPolicy Bypass -File tts-watch.ps1
```

> 대시보드와 폴더 감시기는 같은 `input/`을 사용하므로 **동시에 켜지 마세요**.

`samples/` 에 예시 재난 문구가 있습니다. `input/` 에 복사해 테스트하세요.

## 폴더 구조

```
web/            웹 대시보드 (Flask 백엔드 + 정적 프론트엔드)
tts-watch.ps1   무인 폴더 감시 변환기 (SAPI)
scripts/        모델 다운로드 · 앵커 프리뷰 생성
samples/        예시 재난 문구
tests/          Playwright E2E (스캐폴드)
models/         TTS 모델 (gitignore — 위 스크립트로 다운로드)
input/ output/  런타임 데이터 (gitignore)
```

## 라이선스

코드는 자유롭게 사용하세요. TTS 모델은 Supertonic(MIT) / sherpa-onnx 각각의 라이선스를 따릅니다.
