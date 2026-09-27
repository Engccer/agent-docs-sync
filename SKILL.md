---
name: agent-docs-sync
description: >-
  프로젝트의 CLAUDE.md 지침과 .claude/skills/ 스킬을 Claude Code 외의 범용 코딩 에이전트(Codex, Antigravity,
  Gemini CLI 등)도 인식하도록 확장한다. CLAUDE.md(정본)에서 형제 AGENTS.md를 자동 생성하고(루트 + 모든 하위 폴더),
  .claude/skills/를 .agents/skills/로 미러링한다. 다음 요청에 사용: "이 프로젝트를 Codex/Antigravity에서도 쓰게 해줘",
  "AGENTS.md 만들어 줘", "멀티 에이전트 호환 셋업", "CLAUDE.md를 범용 에이전트용으로 확장",
  "에이전트 중립 지침 동기화", "agent-docs-sync 실행". 사용자 레벨로는 ~/.claude/skills를 Antigravity
  CLI(agy)의 글로벌 스킬 루트(~/.gemini/config/skills)로 반영한다. "Antigravity에서 내 스킬이 안 보여",
  "agy 스킬 인식 안 됨", "agy 글로벌 스킬 동기화" 요청에도 사용. make this project work with
  Codex/Antigravity, generate AGENTS.md from CLAUDE.md, mirror skills to .agents, agent-neutral docs
  sync, sync user-level skills to Antigravity CLI global skill root.
metadata:
  version: "1.2.0"
---

# agent-docs-sync — 멀티 에이전트 호환 지침·스킬 동기화

## ⚠ 정본 방향 확인 (프로젝트 레벨, 틀리면 정본 파괴)

**`sync_agent_docs.py`의 단 하나의 전제: `CLAUDE.md` + `.claude/skills/`가 정본이고, `AGENTS.md` + `.agents/skills/`는 생성물이다.** 이 방향이 거짓인 환경에서 실행하면 동기화가 진짜 파일을 "고아"로 판단해 **삭제**한다. 방향은 추정하지 말고 스크립트 경고와 아래 확인으로 정한다. 사용자 레벨(`sync_agy_skills.py`)은 `~/.claude/skills`의 symlink를 실체까지 해석하는 것이 정상 동작이라 `references/agy.md`를 따른다. → 사례(`references/cases.md`)

### 스킬 방향: `[스킬 방향 경고]`

`.claude/skills/` 최상위에 symlink 스킬이 하나라도 있으면 스크립트는 스킬 미러링 전체를 건너뛰고 `[스킬 방향 경고]`와 종료 코드 `2`를 낸다(문서 동기화는 그대로 진행). walk가 symlink를 따라가지 않아 그 스킬이 정본 목록에서 빠지고, 미러링하면 고아 정리가 `.agents/skills/`의 같은 이름 파일을 지우기 때문이다. Windows junction 스킬은 walk가 따라가므로 해당하지 않는다. 경고가 뜨면 symlink가 가리키는 곳으로 판정한다.

- **`.agents/skills/`를 가리킨다** → 정본 방향이 역전된 환경이다. `.agents/skills/`가 실제 정본이라 만들 생성물이 없다(Codex·Antigravity는 `.agents/skills/`를 직접 읽는다). 사용자에게 보고하고 스킬 미러링은 그대로 둔다.
- **외부 경로(다른 저장소 등)를 가리킨다** → 그 스킬을 실제 폴더로 두기 전에는 이 프로젝트의 스킬 미러링이 전부 멈춰 있다. 사용자에게 알리고 어떻게 둘지 묻는다.

### 문서 방향 (symlink-trap)

```bash
find <루트> -name AGENTS.md -type l               # AGENTS.md가 symlink면 방향 확인
```

- `AGENTS.md`가 `CLAUDE.md`를 가리키는 symlink이면 스크립트는 링크를 따라 읽은 본문이 정본과 같다고 보고 아무것도 쓰지 않는다. 정본은 오염되지 않지만 symlink가 그대로 남으니, 그 `AGENTS.md`를 지우고 다시 실행한다.

### Red Flags — STOP, 정본 방향부터 확인

- `--check`가 대량 삭제를 예고한다: 스킬은 `[미러링(예정)] … (신규 N · 갱신 N · 삭제 N · 대상 N)`의 **삭제 수가 대상 수보다 크거나 예상 밖으로 많다**, 문서는 `[정리]` 줄이 여러 개다
- 동기화 대상이 프로젝트 워크스페이스가 아니라 `~/.claude` 같은 **에이전트 홈**이다 (정본·플러그인 캐시·외부 symlink가 한 트리에 섞임)
- "내가 만든 스킬이니 환경은 내가 안다"

**위 신호 중 하나라도 있으면 실행하지 말고 무엇이 지워지는지부터 확인하라.**

## 무엇을 하는가

Claude Code는 `CLAUDE.md`와 `.claude/skills/`를 읽지만, Codex·Antigravity·Gemini CLI 같은 다른 코딩 에이전트는 각자 다른 위치를 본다. 이 스킬은 **하나의 정본(`CLAUDE.md` + `.claude/skills/`)**에서 다른 에이전트가 네이티브로 인식하는 생성물을 만들어, 같은 작업 공간을 여러 에이전트가 동일한 컨텍스트로 공유하게 한다.

핵심 기제는 단방향 동기화 스크립트 `scripts/sync_agent_docs.py`다. 정본 → 생성물 한 방향으로만 흐르며, 생성물은 빌드 산출물로 취급해 직접 고치지 않는다.

| 정본 | 생성물 | 인식 주체 |
|---|---|---|
| `CLAUDE.md` (루트 + 모든 하위 폴더) | 형제 `AGENTS.md` | Codex·Antigravity (계층 병합) |
| `.claude/skills/` | `.agents/skills/` | Codex·Antigravity (agentskills.io 오픈 표준) |

**왜 하위 폴더까지?** Codex·Antigravity는 작업 디렉터리에서 위로 올라가며 `AGENTS.md`를 **계층 병합**한다. 하위 폴더에 `CLAUDE.md`만 있고 `AGENTS.md`가 없으면, 그 폴더에서 작업하는 에이전트는 루트 `AGENTS.md`만 보고 하위 scoped 지침을 놓친다. 그래서 모든 `CLAUDE.md` 옆에 형제 `AGENTS.md`를 둔다.

**왜 GEMINI.md는 안 만드나?** Antigravity·Gemini CLI 계열도 `AGENTS.md`를 읽는다. 굳이 세 번째 파일을 늘리지 않는다.

위 표는 **프로젝트 레벨**이다. **사용자 레벨**(홈 디렉터리의 개인 스킬을 Antigravity CLI에 노출하는 것)은 경로도 규칙도 달라서 별도 스크립트 `scripts/sync_agy_skills.py`가 담당한다. 아래 "사용자 레벨" 절 참조.

## 빠른 사용 (이미 셋업된 프로젝트)

정본을 수정한 뒤 생성물을 다시 만들 때. 먼저 루트 사본이 이 스킬의 판과 같은지 본다:

```bash
cd <프로젝트 루트>
diff "<이 스킬 경로>/scripts/sync_agent_docs.py" sync_agent_docs.py   # 다르면 아래 "사본 갱신"
python sync_agent_docs.py --check    # 드라이런: 무엇이 바뀔지만 출력
python sync_agent_docs.py            # 동기화 (발산한 AGENTS.md만 건너뛰고 나머지는 모두 반영)
python sync_agent_docs.py --force    # 발산한 AGENTS.md도 정본 기준으로 덮어쓰기
```

**사본 갱신**: 루트 사본이 구버전이면 이 스킬의 스크립트로 바꾼다(구버전은 고아 정리 방어가 빠져 있을 수 있다). 바꾸기 전에 `diff`에서 사본에 손으로 더한 설정(예: `DOC_EXCLUDE_DIRS`에 더한 폴더)이 보이면 새 사본에 옮겨 넣는다. 차이가 그 설정뿐이면 사본은 최신이다.

종료 코드: `0` 전부 최신/반영(경고 없음) · `2` **발산한 `AGENTS.md`나 접근 불가 경로를 건너뛰었거나, symlink 스킬 때문에 스킬 미러링을 건너뛰었거나, 스킬 frontmatter 검증 경고가 있음(나머지는 정상 동기화, 확인 필요, 실패 아님)** · `1` 기타 오류. 발산이 떠도 건너뛰는 것은 그 파일 하나뿐이라, 무관한 폴더의 묵은 발산 때문에 방금 고친 `CLAUDE.md`의 반영이 막히지 않는다. 끝의 `[요약]` 줄이 건너뛴 파일과 이유를 모아 보여 준다.

스크립트는 자기 위치(`Path(__file__).resolve().parent`)를 프로젝트 루트로 삼으므로, 루트에 **복사한** 사본을 그 자리에서 실행한다. 스킬의 스크립트를 symlink로 걸면 루트가 스킬의 `scripts/`가 되어 `[오류] 정본을 찾을 수 없음`으로 끝난다.

## 신규 프로젝트 셋업 워크플로우

처음 적용하는 프로젝트라면 아래 순서로 진행한다. **1회성 셋업이며, 기존 내용을 덮어쓰지 않도록 가드를 지킨다.**

### 1. 전제 확인

- 프로젝트 루트에 `CLAUDE.md`가 있는가? 없으면 사용자에게 먼저 `/init` 등으로 만들 것을 안내한다(이 스킬은 빈 프로젝트를 채우지 않는다).
- `.claude/skills/`가 있는가? 없어도 된다(있으면 스킬도 미러링, 없으면 문서만 동기화).
- **단일 프로젝트인가, 컨테이너인가?** 루트가 하나의 프로젝트가 아니라 여러 독립 저장소·별개 프로젝트를 담은 컨테이너일 수 있다(`CLAUDE.md`가 루트 외 여러 하위에 흩어져 있고 하위마다 자체 `.git`이 있으면 컨테이너 신호). 컨테이너라면 셋업 전에 **적용 범위를 사용자에게 확인**한다(전체 일괄 vs 특정 하위만). 전체로 가면 하위 저장소마다 `AGENTS.md`가 생기고, 그 저장소가 **Public이면 커밋·푸시 시 공개**된다: 사용자에게 알리고, 특정 repo에서 빼려면 그 repo `.gitignore`에 `AGENTS.md`를 넣는 선택지를 제시한다.
- **하위 폴더 링크 점검**: Windows junction은 스크립트가 따라가므로 ROOT 밖을 가리키면 프로젝트 밖에도 `AGENTS.md`를 쓴다(`[외부]` 경고). symlink 폴더(macOS·Linux)는 따라가지 않아 그 안의 `CLAUDE.md`는 경고 없이 빠진다. [`references/troubleshooting.md`](references/troubleshooting.md)의 "junction·symlink 주의" 참조.

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

- **1차 검증은 멱등성**: `--check` 재실행에서 모두 `[최신]`이면 본문이 형제 `CLAUDE.md`와 일치한다는 가장 강한 증거다. 개수 대조(`find` 등)는 보조로만 쓴다. junction이 있으면 도구마다 개수가 어긋날 수 있으니 junction 여부부터 확인하고, symlink 폴더 안의 `CLAUDE.md`는 멱등성·개수 어느 쪽에도 드러나지 않으므로 1단계의 링크 점검으로만 잡는다.
- 각 `AGENTS.md` 상단에 자동생성 배너와 `SYNC-BODY-START` 마커가 있고, 본문이 형제 `CLAUDE.md`와 일치하는지 확인.

## 문제 신호별 대처

`[외부]`·`[접근 불가]`·`[스킬 검증 경고]`가 뜨거나, 프로젝트 루트가 Google Drive 같은 머신 간 동기화 폴더에 있으면 [`references/troubleshooting.md`](references/troubleshooting.md)를 읽는다.

## 발산(divergence) 처리

`AGENTS.md`가 직전 동기화 이후 손으로 수정됐거나 관리 밖에서 만들어졌으면, 스크립트는 `.agent-docs-sync.json`에 남긴 **정본 본문 해시**로 감지해 `[발산 경고]`를 내고 그 파일만 건너뛴다(`mtime`은 Google Drive에서 못 믿으므로 쓰지 않는다). 흔한 사례: 과거 다른 에이전트(Codex 등)가 그 폴더에서 `AGENTS.md`를 따로 만들어 둔 경우.

판단 기준:
- **`CLAUDE.md`가 최신·정본이 맞다** → `--force`로 정본 기준 덮어쓴다.
- **`AGENTS.md` 쪽에 살릴 내용이 있다** → 먼저 그 내용을 `CLAUDE.md`로 옮긴 뒤 `--force`로 실행한다. 옮긴 결과가 `AGENTS.md` 본문과 글자 하나까지 같지 않으면 `--force` 없이는 발산 경고가 계속된다.

고아 정리는 대응 `CLAUDE.md`가 사라진 `AGENTS.md` 가운데 자동생성 배너 마커가 있는 것만 지운다(`[정리]`). 손으로 만든 `AGENTS.md`는 남긴다. 배너를 남긴 채 본문만 고친(발산 중인) `AGENTS.md`는 짝 `CLAUDE.md`를 지우면 함께 지워지니, 살릴 내용은 `CLAUDE.md`를 지우기 전에 옮긴다.

`--force`는 `AGENTS.md` 발산 판정에만 작용한다. 스킬 미러링은 `--force`와 무관하게 늘 정본 기준이라, `.agents/skills/`에 직접 둔 파일(자격증명 포함)은 매 실행 고아로 지워지고 `_GENERATED.md`는 매번 다시 쓰인다.

## 사용자 레벨: Antigravity CLI 글로벌 스킬

`~/.claude/skills`를 Antigravity CLI(`agy`)의 글로벌 스킬 루트로 반영하거나 agy가 스킬을 못 볼 때는 [`references/agy.md`](references/agy.md)를 읽는다.

## 보안: 무엇이 동기화되지 않는가

스킬 미러링이 제외하는 것은 아래 패턴뿐이다(노출면·회전 부담 2배 방지): 자격증명 `credentials/`·`accounts.json`·`*token*.json`·`client_secret*.json`·`*.token`·`*.key`·`*.pem`·`.env*`·`secrets*`, 폴더 `.git`·`.idea`·`node_modules`·`.venv`·`__pycache__`, 캐시 `*.pyc`·`*.pyo`, OS 잡파일 `desktop.ini`·`.DS_Store`. 이 패턴에 걸리지 않는 이름의 비밀 파일은 `.agents/skills/`로 그대로 복제되니 정본 스킬 폴더에 두지 않는다.

**주의**: `CLAUDE.md` 본문에 API 키 같은 비밀을 인라인으로 적으면, 전문 복제물인 `AGENTS.md`에도 그대로 들어간다. 키는 별도 설정 파일/환경변수로 분리하는 것을 권한다.

세부 구현은 `scripts/sync_agent_docs.py`의 docstring과 주석 참조.
