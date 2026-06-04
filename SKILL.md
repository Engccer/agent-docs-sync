---
name: agent-docs-sync
description: >-
  프로젝트의 CLAUDE.md 지침과 .claude/skills/ 스킬을 Claude Code 외의 범용 코딩 에이전트(Codex, Antigravity,
  Gemini CLI 등)도 인식하도록 확장한다. CLAUDE.md(정본)에서 형제 AGENTS.md를 자동 생성하고(루트 + 모든 하위 폴더),
  .claude/skills/를 .agents/skills/로 미러링한다. 다음 요청에 사용: "이 프로젝트를 Codex/Antigravity에서도 쓰게 해줘",
  "AGENTS.md 만들어 줘", "멀티 에이전트 호환 셋업", "CLAUDE.md를 범용 에이전트용으로 확장",
  "에이전트 중립 지침 동기화", "agent-docs-sync 실행". make this project work with Codex/Antigravity,
  generate AGENTS.md from CLAUDE.md, mirror skills to .agents, agent-neutral docs sync.
---

# agent-docs-sync — 멀티 에이전트 호환 지침·스킬 동기화

## 무엇을 하는가

Claude Code는 `CLAUDE.md`와 `.claude/skills/`를 읽지만, Codex·Antigravity·Gemini CLI 같은 다른 코딩 에이전트는 각자 다른 위치를 본다. 이 스킬은 **하나의 정본(`CLAUDE.md` + `.claude/skills/`)**에서 다른 에이전트가 네이티브로 인식하는 생성물을 만들어, 같은 작업 공간을 여러 에이전트가 동일한 컨텍스트로 공유하게 한다.

핵심 기제는 검증된 단방향 동기화 스크립트 `scripts/sync_agent_docs.py`다. 정본 → 생성물 한 방향으로만 흐르며, 생성물은 "빌드 산출물"로 취급한다.

| 정본 (canonical) | 생성물 (generated) | 인식 주체 |
|---|---|---|
| `CLAUDE.md` (루트 + 모든 하위 폴더) | 형제 `AGENTS.md` | Codex·Antigravity (계층 병합) |
| `.claude/skills/` | `.agents/skills/` | Codex·Antigravity (agentskills.io 오픈 표준) |

**왜 하위 폴더까지?** Codex·Antigravity는 작업 디렉터리에서 위로 올라가며 `AGENTS.md`를 **계층 병합**한다. 하위 폴더에 `CLAUDE.md`만 있고 `AGENTS.md`가 없으면, 그 폴더에서 작업하는 에이전트는 루트 `AGENTS.md`만 보고 하위 scoped 지침을 놓친다. 그래서 모든 `CLAUDE.md` 옆에 형제 `AGENTS.md`를 둔다.

**왜 GEMINI.md는 안 만드나?** Antigravity·Gemini CLI 계열도 `AGENTS.md`를 읽는다. 굳이 세 번째 파일을 늘리지 않는다(필요하면 스크립트의 동기화 쌍에 한 줄 추가 가능).

## 빠른 사용 (이미 셋업된 프로젝트)

정본을 수정한 뒤 생성물을 다시 만들 때:

```bash
cd <프로젝트 루트>
python sync_agent_docs.py            # 동기화 (발산한 AGENTS.md만 건너뛰고 나머지는 모두 반영)
python sync_agent_docs.py --check    # 드라이런: 무엇이 바뀔지만 출력
python sync_agent_docs.py --force    # 발산 경고를 무시하고 발산 파일도 정본 기준으로 덮어쓰기
```

종료 코드: `0` 전부 최신/반영(발산·검증 경고 없음) · `2` **발산 파일을 건너뛰었거나 스킬 frontmatter 검증 경고가 있음(나머지는 정상 동기화 — 확인 필요, 실패 아님)** · `1` 기타 오류.

> **발산이 떠도 내 변경은 반영된다.** 한 폴더의 `AGENTS.md`가 발산해도 실행 전체가 멈추지 않는다. 스크립트는 발산한 그 파일 **하나만** 건너뛰고(경고 출력) 나머지 모든 `CLAUDE.md`→`AGENTS.md`와 스킬을 정상 동기화한 뒤, 마지막에 `[요약]` 한 줄로 건너뛴 파일을 모아 보여주고 종료 코드 `2`를 낸다. 즉 **무관한 다른 폴더의 묵은 발산 때문에 방금 고친 `CLAUDE.md`의 미러링이 막히는 일은 없다.** `--force` 없이 그냥 실행하면 된다(`--force`는 그 발산 파일까지 정본으로 덮고 싶을 때만).

스크립트는 자기 위치(`Path(__file__).parent`)를 프로젝트 루트로 삼으므로, 루트에 둔 사본을 그 자리에서 실행하면 된다.

## 신규 프로젝트 셋업 워크플로우

처음 적용하는 프로젝트라면 아래 순서로 진행한다. **1회성 셋업이며, 기존 내용을 덮어쓰지 않도록 가드를 지킨다.**

### 1. 전제 확인

- 프로젝트 루트에 `CLAUDE.md`가 있는가? 없으면 사용자에게 먼저 `/init` 등으로 만들 것을 안내한다(이 스킬은 빈 프로젝트를 채우지 않는다).
- `.claude/skills/`가 있는가? 없어도 된다(있으면 스킬도 미러링, 없으면 문서만 동기화).

### 2. CLAUDE.md 상단에 에이전트 중립 호환 블록 삽입

루트 `CLAUDE.md` 맨 위(H1 제목 바로 아래)에 호환 안내 블록을 넣는다. 템플릿과 채우는 법은 `references/templates.md`의 "① 에이전트 중립 호환 블록" 참조. **이미 비슷한 블록이 있으면 새로 넣지 말고 사용자에게 알린다.**

이 블록은 프로젝트마다 미세하게 다르다(서브에이전트·MCP 구성). 폴더명·`CLAUDE.md` 본문·`.claude/agents/`·`.mcp.json`을 읽어 해당 프로젝트에 맞게 채운다.

### 3. CLAUDE.md에 동기화 규칙 한 줄 추가

스킬 섹션(또는 적절한 위치) 앞에 "정본을 수정하면 `python sync_agent_docs.py`를 실행해 생성물을 재생성한다"는 규칙을 넣는다. 템플릿은 `references/templates.md`의 "② 동기화 규칙" 참조.

### 4. 스킬 색인(스킬_요약.md) 생성 — `.claude/skills/`가 있을 때만

`.claude/skills/`를 스캔해 각 스킬의 `SKILL.md` 프런트매터(`name`·`description`)와 `.claude/agents/`·`.mcp.json`을 읽어, 가시성 높은 루트에 `스킬_요약.md`(또는 `SKILLS.md`) 색인을 만든다. 구조는 `references/templates.md`의 "③ 스킬 색인" 참조. 이 파일은 `.claude/` 밖에 두어 어떤 에이전트든 쉽게 발견하게 한다.

### 5. 스크립트를 루트에 복사하고 실행

```bash
cp "<이 스킬 경로>/scripts/sync_agent_docs.py" "<프로젝트 루트>/sync_agent_docs.py"
cd "<프로젝트 루트>"
python sync_agent_docs.py --check    # 먼저 미리보기
python sync_agent_docs.py            # 실제 실행
```

스크립트를 루트에 두는 이유: 사용자가 이후 정본을 고칠 때마다 Claude 없이도 `python sync_agent_docs.py` 한 줄로 직접 재생성할 수 있게 하기 위함이다(스킬은 셋업·개선 시에만 필요).

### 6. 검증

```bash
python sync_agent_docs.py --check    # 재실행 시 모두 "[최신]"이어야 멱등성 OK
```

- 루트 + 모든 하위 `CLAUDE.md` 개수 == `AGENTS.md` 개수인지 확인(`.claude`/`.agents` 트리 제외).
- 각 `AGENTS.md` 상단에 자동생성 배너 + `<!-- SYNC-BODY-START -->` 마커가 있고, 본문이 형제 `CLAUDE.md`와 일치하는지 확인.

## 발산(divergence) 처리

`AGENTS.md`가 직전 동기화 이후 손으로 수정됐거나 관리 밖에서 만들어졌으면, 스크립트는 **본문 해시**로 감지해 경고하고 그 파일만 건너뛴다(`mtime`은 Google Drive에서 못 믿으므로 쓰지 않는다). 흔한 사례: 과거 다른 에이전트(Codex 등)가 그 폴더에서 `AGENTS.md`를 따로 만들어 둔 경우.

판단 기준:
- **`CLAUDE.md`가 최신·정본이 맞다** → `--force`로 정본 기준 덮어쓴다.
- **`AGENTS.md` 쪽에 살릴 내용이 있다** → 먼저 그 내용을 `CLAUDE.md`로 옮긴 뒤 일반 실행한다(`--force` 없이).

`--force`는 발산 경고만 무시할 뿐, 보호 대상(자격증명·`_GENERATED.md`)은 건드리지 않는다.

## 스킬 frontmatter 검증 (validate_skills)

미러링과 별개로, 스크립트는 정본 각 `.claude/skills/<스킬>/SKILL.md`의 frontmatter가 **Codex·Antigravity가 쓰는 엄격한 `agentskills.io` YAML 파서에서 깨지지 않는지** 매 실행마다 점검한다. 동기화 자체는 차단하지 않고, 문제가 있으면 stderr에 `[스킬 검증 경고]`를 띄운 뒤 종료 코드 `2`(확인 필요)를 낸다.

**왜 필요한가.** Claude Code의 frontmatter 파서는 관대해서 약간 깨진 YAML도 그냥 로드한다. 그래서 정본만 보면 멀쩡해 보이지만, 같은 파일을 미러링한 `.agents/skills/`를 Codex가 읽을 때만 조용히 스킬이 누락되거나 warning이 난다. 이 검증은 그 **"한쪽에서만 깨지는"** 상황을 정본 단계에서 미리 잡는다.

**무엇을 잡나** (PyYAML이 있으면 정식 파싱, 없으면 휴리스틱 폴백 — 어느 쪽이든 아래는 잡는다):
- frontmatter(`---` 블록) 부재 또는 닫는 `---` 누락
- **YAML 파싱 실패** — 가장 흔한 함정은 `description`이 plain scalar인데 값 안에 `… 사용: 키워드`처럼 **`: `(콜론+공백)**이 있는 경우. 엄격한 파서는 이를 중첩 매핑으로 오인해 `mapping values are not allowed here`로 실패한다.
- `name`이 폴더명과 불일치 (표준은 일치 요구)
- `description` 비어 있음 또는 1024자 초과

**해법(=작성 규칙).** `description`에 콜론·따옴표 등이 들어갈 수 있으므로 **항상 block scalar(`>-`)로 감싼다**:

```yaml
---
name: 내-스킬            # 폴더명과 정확히 일치
description: >-
  한 줄 요약. 다음 키워드가 포함된 요청에 사용: A, B, C.   # 콜론이 있어도 block scalar라 안전
---
```

> **한글 `name`은 의도적으로 허용한다.** 표준은 `name`을 lowercase ASCII + 폴더명 일치로 권장하지만, 한글 호출명(`/스킬`)을 유지하는 프로젝트에서는 한글 폴더명=한글 name으로 두고, Antigravity는 name 미준수 시 폴더명으로 폴백한다. 그래서 검증은 한글 여부를 **문제로 보지 않고**, 실제로 깨지는 것(파싱 실패·frontmatter 부재·name↔폴더명 불일치)만 잡는다. 영문 slug로 컴파일하는 방식도 가능하나, 정본↔생성물 폴더명 불일치·매핑 유지보수 비용 때문에 기본값은 단순 미러링이다.

## 보안: 무엇이 동기화되지 않는가

스킬 미러링은 자격증명·캐시·OS 잡파일을 의도적으로 제외한다(노출면·회전 부담 2배 방지): `credentials/`·`accounts.json`·`*token*.json`·`client_secret*.json`·`*.key`·`*.pem`·`__pycache__` 등. 따라서 `.agents/skills/`에는 비밀이 새지 않는다.

**주의**: `CLAUDE.md` 본문에 API 키 같은 비밀을 인라인으로 적으면, 전문 복제물인 `AGENTS.md`에도 그대로 들어간다. 키는 별도 설정 파일/환경변수로 분리하는 것을 권한다.

## 스크립트 동작 원리 (요약)

- `ROOT = Path(__file__).resolve().parent` — 스크립트 위치가 곧 프로젝트 루트. 복사만 하면 어디서든 동작.
- 문서 동기화: `CLAUDE.md` 본문에 배너를 붙여 `AGENTS.md` 생성. 본문 일치/직전 정본 해시로 최신·발산 판정.
- 하위 폴더 walk 시 `DOC_EXCLUDE_DIRS`(`.claude`·`.agents`·`.git`·`__pycache__`·`node_modules`·`.venv`·`.idea`)는 가지치기.
- 고아 정리: 대응 `CLAUDE.md`가 사라지고 배너 마커를 가진(=우리가 만든) `AGENTS.md`만 안전 삭제. 수동 파일은 보존.
- 상태는 `.agent-docs-sync.json`에 정본 본문 해시로 저장. 루트 상태키는 `"AGENTS.md"`, 하위는 POSIX 상대경로.
- 스킬 검증(`validate_skills`)은 미러링과 독립적으로 매 실행 정본 `SKILL.md` frontmatter를 점검한다(위 "스킬 frontmatter 검증" 참조).

세부 구현은 `scripts/sync_agent_docs.py`의 docstring과 주석 참조.
