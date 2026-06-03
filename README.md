# agent-docs-sync

하나의 정본(`CLAUDE.md` + `.claude/skills/`)에서 Claude Code 외의 범용 코딩 에이전트(Codex, Antigravity, Gemini CLI 등)가 네이티브로 인식하는 생성물을 만들어, 같은 작업 공간을 여러 에이전트가 동일한 컨텍스트로 공유하게 하는 [Claude Code 스킬](https://docs.claude.com/en/docs/claude-code/skills)이다.

## 무엇을 하는가

Claude Code는 `CLAUDE.md`와 `.claude/skills/`를 읽지만, 다른 코딩 에이전트는 각자 다른 위치를 본다. 이 스킬은 정본에서 단방향으로만 생성물을 빌드한다(생성물은 "빌드 산출물"로 취급).

| 정본 (canonical) | 생성물 (generated) | 인식 주체 |
|---|---|---|
| `CLAUDE.md` (루트 + 모든 하위 폴더) | 형제 `AGENTS.md` | Codex·Antigravity (계층 병합) |
| `.claude/skills/` | `.agents/skills/` | Codex·Antigravity (agentskills.io 오픈 표준) |

하위 폴더의 `CLAUDE.md` 옆에도 형제 `AGENTS.md`를 두는 이유: Codex·Antigravity는 작업 디렉터리에서 위로 올라가며 `AGENTS.md`를 계층 병합한다. 하위 scoped 지침을 놓치지 않게 하기 위함이다.

## 사용법

핵심은 단방향 동기화 스크립트 `scripts/sync_agent_docs.py`다. 프로젝트 루트에 복사한 뒤 실행한다.

```bash
cd <프로젝트 루트>
python sync_agent_docs.py            # 동기화 (발산한 AGENTS.md만 건너뛰고 나머지는 모두 반영)
python sync_agent_docs.py --check    # 드라이런: 무엇이 바뀔지만 출력
python sync_agent_docs.py --force    # 발산 경고를 무시하고 발산 파일도 정본 기준으로 덮어쓰기
```

종료 코드: `0` 전부 최신/반영(발산 없음) · `2` 발산 파일을 건너뜀(나머지는 정상 동기화 — 확인 필요, 실패 아님) · `1` 기타 오류. 발산이 떠도 실행 전체가 멈추지 않으므로, 무관한 폴더의 묵은 발산 때문에 방금 고친 `CLAUDE.md`의 미러링이 막히지 않는다. 스크립트는 자기 위치(`Path(__file__).parent`)를 프로젝트 루트로 삼으므로, 루트에 둔 사본을 그 자리에서 실행하면 된다.

신규 프로젝트 셋업 워크플로우(호환 블록 삽입, 스킬 색인 생성, 검증 등)와 발산 처리·보안 정책은 [`SKILL.md`](SKILL.md)에 정리돼 있다.

## 보안

스킬 미러링은 자격증명·캐시·OS 잡파일을 의도적으로 제외한다(`credentials/`·`accounts.json`·`*token*.json`·`client_secret*.json`·`*.key`·`*.pem`·`__pycache__` 등). 단 `CLAUDE.md` 본문에 비밀을 인라인으로 적으면 전문 복제물인 `AGENTS.md`에도 그대로 들어가므로, 키는 환경변수/별도 설정 파일로 분리할 것을 권한다.

## 라이선스

[MIT](LICENSE)
