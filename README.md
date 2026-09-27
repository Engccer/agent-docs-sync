# agent-docs-sync

하나의 정본(`CLAUDE.md` + `.claude/skills/`)에서 Claude Code 외의 범용 코딩 에이전트(Codex, Antigravity, Gemini CLI 등)가 네이티브로 인식하는 생성물(`AGENTS.md`, `.agents/skills/`)을 만드는 [Claude Code 스킬](https://docs.claude.com/en/docs/claude-code/skills)이다. 사용자 레벨로는 `~/.claude/skills`를 Antigravity CLI(`agy`)의 글로벌 스킬 루트로 반영한다.

## 설치

이 저장소를 `~/.claude/skills/agent-docs-sync`에 클론한다.

Python 3, 표준 라이브러리만 쓴다(PyYAML이 있으면 스킬 frontmatter 검증이 더 엄격해진다).

## 실행

프로젝트 레벨: 스크립트를 프로젝트 루트에 복사해 실행한다.

```bash
cp ~/.claude/skills/agent-docs-sync/scripts/sync_agent_docs.py <프로젝트 루트>/
cd <프로젝트 루트>
python sync_agent_docs.py --check    # 미리보기
python sync_agent_docs.py            # 동기화
```

사용자 레벨(Antigravity CLI):

```bash
python ~/.claude/skills/agent-docs-sync/scripts/sync_agy_skills.py --init    # allowlist 템플릿
python ~/.claude/skills/agent-docs-sync/scripts/sync_agy_skills.py           # 반영
```

실행 전 필수 확인(정본 방향), 셋업 절차, 종료 코드, 발산 처리, 보안 정책은 [`SKILL.md`](SKILL.md)에, Antigravity 사용자 레벨과 정본을 지우지 않는 가드는 [`references/agy.md`](references/agy.md)에 있다.

## 라이선스

[MIT](LICENSE)
