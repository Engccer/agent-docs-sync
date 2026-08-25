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

## 사용자 레벨: Antigravity CLI 글로벌 스킬

위가 프로젝트 레벨이라면, `scripts/sync_agy_skills.py`는 홈 디렉터리의 개인 스킬을 Antigravity CLI(`agy`)에 노출한다.

```bash
python scripts/sync_agy_skills.py --init      # allowlist 템플릿 생성 (~/.gemini/agy-skills.txt)
python scripts/sync_agy_skills.py --check     # 드라이런
python scripts/sync_agy_skills.py             # 반영
python scripts/sync_agy_skills.py --force [스킬 ...]   # 드리프트 복사본을 정본으로 덮어씀(이름 없으면 전부)
```

`~/.claude/skills/<name>` 을 realpath 로 해석해 `~/.gemini/config/skills/<name>` 으로 반영한다. 실측으로 확정된 두 가지 때문에 별도 스크립트가 필요하다.

- **agy 의 글로벌 스킬 루트는 `~/.gemini/config/skills` 다.** `~/.agents/skills` 가 아니다. 후자는 agy 에게 워크스페이스 루트일 뿐이라, 거기에 스킬을 넣어도 agy 는 보지 못한다(그쪽은 Codex 의 루트다).
- **링크 추종이 OS 마다 다르다.** Windows 의 agy 는 junction 을 따라가지 않아 물리 복사가 필요하고, macOS 의 agy 는 symlink 를 따라가므로 링크로 충분하다. 스크립트가 알아서 갈라 처리한다. Windows 에서는 정본을 고칠 때마다 다시 실행해야 한다.

Windows 의 물리 복사에는 **드리프트 가드**가 붙어 있다: 마지막 동기화 해시를 `~/.gemini/agy-sync-manifest.json` 에 기록해 두고, agy 쪽 복사본이 그 이후 수정됐으면 덮어쓰지도 삭제하지도 않고 건너뛰며 경고한다(종료 2). 수정을 정본에 반영해 양쪽을 같게 만들면 다음 실행이 자동 재베이스라인하고, 폐기해도 되면 `--force <스킬명>` 으로 그 스킬만 덮어쓴다(이름 없으면 전부). 복사본은 빌드 산출물이며 수정은 정본에서만 하는 것이 원칙이고, 가드는 그 원칙이 깨졌을 때의 안전망이다.

노출할 스킬은 `~/.gemini/agy-skills.txt` 에 한 줄씩 적는다. 목록에서 빠진 항목은 agy 루트에서 정리되며 정본은 건드리지 않는다. 자세한 배경과 카나리 진단법은 [`SKILL.md`](SKILL.md) 의 "사용자 레벨" 절 참조.

## 보안

스킬 미러링은 자격증명·캐시·OS 잡파일을 의도적으로 제외한다(`credentials/`·`accounts.json`·`*token*.json`·`client_secret*.json`·`*.key`·`*.pem`·`__pycache__` 등). 단 `CLAUDE.md` 본문에 비밀을 인라인으로 적으면 전문 복제물인 `AGENTS.md`에도 그대로 들어가므로, 키는 환경변수/별도 설정 파일로 분리할 것을 권한다.

## 라이선스

[MIT](LICENSE)
