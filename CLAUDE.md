# CLAUDE.md

이 파일은 이 저장소에서 작업할 때 Claude Code에 대한 가이드를 제공합니다.

> 행동 원칙(Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution)은
> 전역 `~/.claude/CLAUDE.md`를 따릅니다. 이 파일은 프로젝트 고유 정보만 다룹니다.

## 프로젝트 개요

Playwright 기반 End-to-End(E2E) 테스트 프로젝트입니다. TypeScript로 작성하며 Chromium, Firefox, WebKit 세 브라우저를 대상으로 테스트를 실행합니다.

## 명령어

```bash
npx playwright test                      # 전체 테스트 실행 (3개 브라우저)
npx playwright test --project=chromium   # 특정 브라우저만 실행
npx playwright test tests/example.spec.ts # 특정 파일만 실행
npx playwright test -g "has title"       # 이름으로 테스트 필터링
npx playwright test --ui                 # UI 모드 (디버깅에 유용)
npx playwright test --headed             # 브라우저 화면을 보면서 실행
npx playwright test --debug              # 단계별 디버깅
npx playwright show-report               # 마지막 HTML 리포트 열기
npx playwright codegen <url>             # 동작을 녹화해 테스트 코드 생성
```

> 브라우저 바이너리 설치가 필요하면 `npx playwright install` 을 먼저 실행하세요.

## 구조

- `tests/` — 테스트 스펙 파일(`*.spec.ts`)이 위치하는 디렉터리
- `playwright.config.ts` — Playwright 설정 (테스트 디렉터리, 브라우저 프로젝트, 리포터 등)
- `playwright-report/` — 생성된 HTML 리포트 (gitignore, 수정 금지)
- `test-results/` — 실패 시 trace/스크린샷 등 산출물 (gitignore, 수정 금지)

## 설정 참고사항

- `testDir`은 `./tests`로 지정되어 있습니다.
- `fullyParallel: true` — 테스트는 병렬로 실행됩니다.
- 리포터는 `html`로 설정되어 있습니다.
- trace는 `on-first-retry` (CI에서 재시도 시에만 수집).
- CI 환경(`process.env.CI`)에서는 retries 2회, workers 1로 동작합니다.
- `baseURL`, `webServer`는 현재 주석 처리되어 있습니다. 로컬 서버를 대상으로 테스트하려면 `playwright.config.ts`에서 활성화하세요.

## 테스트 작성 규칙

- 테스트 파일은 `tests/` 아래에 `*.spec.ts` 형태로 작성합니다.
- 셀렉터는 가급적 role 기반(`getByRole`) 등 사용자 관점의 접근 가능한 로케이터를 우선 사용합니다.
- 단언은 `await expect(...)` 의 web-first assertion을 사용해 자동 재시도(auto-wait) 이점을 활용합니다.
- `test.only`는 커밋하지 마세요. (CI에서 `forbidOnly`로 빌드가 실패합니다.)
