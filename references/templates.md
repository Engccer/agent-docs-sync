# 셋업 템플릿

신규 프로젝트에 멀티 에이전트 호환을 처음 적용할 때 `CLAUDE.md`·`스킬_요약.md`에 넣는 텍스트 템플릿. `<...>`는 프로젝트에 맞게 채운다. 모두 **이미 있으면 새로 넣지 말 것**.

---

## ① 에이전트 중립 호환 블록 (루트 CLAUDE.md 맨 위, H1 제목 바로 아래)

서브에이전트·MCP 구성은 프로젝트마다 다르므로, `.claude/agents/`·`.mcp.json`을 읽어 해당 항목을 조정한다. 서브에이전트나 MCP가 없으면 그 줄은 빼도 된다.

```markdown
> ## ⚠ 다양한 코딩 에이전트(Claude·Codex·Antigravity 등)를 위한 호환 유의사항
>
> 이 문서의 지침은 어느 도구에서나 그대로 적용된다. **스킬**은 오픈 표준 `SKILL.md` 형식으로, Claude Code는 `.claude/skills/`에서, Codex·Antigravity는 `.agents/skills/`에서 자동 인식한다(두 위치는 동일 내용). 전체 색인은 루트 [`스킬_요약.md`](스킬_요약.md). 자격증명은 보안상 `.agents/skills/`에서 제외되니 필요하면 `.claude/skills/<스킬명>/`을 참조한다. 도구별로 설정 위치·포맷이 다른 항목은 아래 둘뿐이다.
>
> 1. **서브에이전트**: Claude Code는 `.claude/agents/*.md`(예: `<에이전트명>`), Codex는 `~/.codex/agents/`·`.codex/agents/`의 TOML(필수 필드 `name`·`description`·`developer_instructions`), Antigravity는 자체 agent/team 모델을 쓴다. 각 `.claude/agents/*.md`는 역할 명세이므로 어느 도구든 그대로 읽어 컨텍스트로 쓸 수 있다.
> 2. **MCP 서버**: 서버는 이식 가능하나 설정 위치가 다르다 — Claude Code `.mcp.json`, Antigravity `.agents/mcp_config.json`(`serverUrl` 스키마), Codex `config.toml`의 `[mcp_servers.*]`.
>
> **하위 폴더에서 작업할 때**: 특정 작업 폴더에서 작업할 때는 그 폴더와 상위 폴더들에 `CLAUDE.md`(및 동일 내용으로 자동 생성된 형제 `AGENTS.md`)가 있는지 확인하고, 발견하면 해당 범위의 프로젝트 레벨 지침으로 간주해 루트 지침과 함께 따른다. 루트 지침과 하위 지침이 충돌하면 더 구체적인(하위) 지침을 우선한다. 하위 폴더의 `CLAUDE.md`마다 `python sync_agent_docs.py`가 형제 `AGENTS.md`를 자동 생성하므로, `AGENTS.md`를 계층적으로 병합하는 Codex·Antigravity는 별도 조치 없이 인식한다.
```

`스킬_요약.md`를 만들지 않는 프로젝트라면 첫 문단의 색인 문장을 빼거나 실제 색인 파일명으로 바꾼다.

---

## ② 동기화 규칙 (CLAUDE.md의 스킬 섹션 또는 적절한 위치 앞)

```markdown
> **동기화 규칙**: 이 `CLAUDE.md`(정본)나 `.claude/skills/`를 수정하면, 프로젝트 루트에서 `python sync_agent_docs.py`를 실행해 `AGENTS.md`와 `.agents/skills/`를 재생성한다. 생성본은 직접 수정하지 않는다.
```

---

## ③ 스킬 색인 (스킬_요약.md, `.claude/skills/`가 있을 때만)

`.claude/skills/*/SKILL.md`의 프런트매터(`name`·`description`)와 `.claude/agents/*.md`, `.mcp.json`을 읽어 채운다.

```markdown
# <프로젝트명> 스킬 요약 (총 <N>개)

> 최근 갱신: <YYYY-MM-DD>
>
> 이 문서는 <프로젝트명>에서 사용하는 자동화 스킬 <N>종의 색인과 설명이다.
> 범용 코딩 에이전트(Claude Code, Codex, Antigravity 등)가 프로젝트 컨텍스트를
> 파악할 수 있도록 가시성 높은 루트에 배치한다. 정본은 `.claude/skills/`이며, 비-Claude 에이전트가
> 네이티브로 인식하는 `.agents/skills/`에도 동일 내용이 미러링된다(`python sync_agent_docs.py`).
> 슬래시(`/`) 스킬 호출은 Claude Code 전용이므로, 비-Claude 에이전트는 각 스킬이 내부적으로 사용하는
> 스크립트(`.claude/skills/<스킬명>/scripts/`)를 직접 실행한다.

## 목차

1. `/<스킬명>`: <description 한 줄 요약>
2. ...

## 서브에이전트

- `<에이전트명>` (`.claude/agents/<에이전트명>.md`): <역할 요약>

## 프로젝트 MCP

- <MCP 서버명>: <용도>. 자격증명은 생성본 스킬 폴더에 동기화하지 않는다.
```

날짜(`YYYY-MM-DD`)는 추론하지 말고 `date`/`Get-Date`로 확인해 적는다.

---

## 호출 문법 참고 (생성물 안내용)

같은 스킬을 도구별로 부르는 법: Claude `/스킬`, Codex `$스킬`, Antigravity `@스킬` (자동 활성화는 공통). 이 안내는 스크립트가 `.agents/skills/_GENERATED.md`에 자동으로 적어 둔다.
