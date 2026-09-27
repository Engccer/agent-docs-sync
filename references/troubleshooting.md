# 문제 신호별 대처

`sync_agent_docs.py` 실행 중 특정 경고가 뜨거나 특정 환경일 때만 읽는다.

## junction·symlink 주의 (ROOT 밖 외부 쓰기)

스크립트는 하위 폴더를 `os.walk` 기본값으로 돈다. 그래서 링크 종류에 따라 결과가 다르다.

- **Windows junction**: 따라간다. junction이 **ROOT(프로젝트 루트) 밖**(다른 드라이브·Google Drive 동기화 폴더 등)을 가리키면, 그 안의 `CLAUDE.md`를 정본으로 보고 **프로젝트 트리 밖에 `AGENTS.md`를 생성/갱신**한다.
- **symlink 폴더**(macOS·Linux, Windows 디렉터리 symlink): 따라가지 않는다. 그 안의 `CLAUDE.md`는 경고 없이 동기화 대상에서 빠지고 종료 코드도 `0`이다. 그 폴더도 동기화하려면 링크 너머 실제 폴더를 프로젝트로 보고 거기에 따로 셋업한다.

junction 외부 쓰기는 막지 않는다(외부 폴더를 일부러 link 해 함께 동기화하려는 경우가 있으므로). 대신 **가시화**한다: 실행 시 해당 경로에 `[외부] … 는 junction/symlink 로 ROOT 밖을 가리킵니다 → <실제 경로>` 경고를 출력한다(종료 코드는 바꾸지 않으므로 매번 동기화해도 노이즈가 되지 않는다). 이 경고가 보이면 판단한다:
- **의도한 동기화면** 그대로 둔다.
- **그 link 너머가 자체 `sync_agent_docs.py`를 갖는 별도 프로젝트면**, 두 동기화가 같은 파일을 건드려 충돌·중복이 난다 → 그 폴더명을 루트 사본의 `DOC_EXCLUDE_DIRS`에 추가하거나 link를 정리해 제외한다. `DOC_EXCLUDE_DIRS`는 이름으로만 비교하므로 트리 어디에 있든 같은 이름의 폴더가 모두 빠진다. 사본을 새 판으로 바꿀 때 이 추가분을 옮겨 넣는다(SKILL.md "빠른 사용"의 사본 갱신).

신규 셋업인데 외부 junction 너머에 이미 `AGENTS.md`가 있으면(과거 동기화 흔적) 본문이 정본과 같을 때 `[최신] … 상태 해시만 갱신`으로 나온다. 본문이 다르면 `[발산 경고]`가 뜬다. 이것은 진짜 발산이니 SKILL.md "발산 처리"대로 판단한다.

### 접근 불가 경로

walk 가 열지 못한 폴더(예: SSH 세션에서 RedirectionGuard 가 클라우드 드라이브로 가는 junction 통과를 막는 `WinError 448`)는 `[접근 불가]` 경고와 함께 건너뛴다. 그 안의 `AGENTS.md` 는 고아로 판정하지 않고 상태 기록도 지우지 않으며, 고아 후보 판정 중 `OSError` 가 난 경로도 같은 방식으로 건너뛰고 나머지 정리는 계속한다. 끝에 `[요약]` 으로 모아 보여주고 종료 코드 `2` 를 낸다. junction 너머까지 동기화하려면 로컬 세션에서 다시 실행한다.

## 머신 간 동기화 폴더(NFC/NFD) 주의

프로젝트 루트가 Google Drive 같은 **머신 간 동기화 폴더**면 `.agent-docs-sync.json`도 함께 동기화된다. macOS 는 파일명을 NFD 로, Windows 는 NFC 로 돌려주므로, 같은 한글 경로가 머신마다 다른 상태 키로 저장된다. 게다가 Google Drive 파일시스템은 NFD 별형 경로도 NFC 실파일로 해석하기 때문에, 구버전 스크립트에서는 고아 정리가 NFD 구키를 "대응 CLAUDE.md 없음"으로 오판하고 **살아 있는 `AGENTS.md` 를 별형 경로 경유로 실제 삭제**했다(증상 시그니처: ASCII 경로만 `[최신]`, 한글 경로는 전부 `[갱신]` 직후 `[정리]`). → 사례

현재 스크립트는 두 겹으로 방어한다: ① 상태 키를 읽고 쓸 때 항상 NFC 정규화(`norm_key`), ② 고아 삭제 전 형제 `CLAUDE.md` 실존을 직접 확인(`has_sibling_canonical`). **배포본이 이 방어를 갖췄는지가 중요하다** — Drive 류 동기화 폴더에 구버전 사본이 남아 있으면 같은 사고가 재발하므로, 그런 프로젝트를 만나면 사본을 정본 스크립트로 갱신한다. 회귀 테스트: `python "<이 스킬 경로>/tests/test_sync_agent_docs.py"`.

## 스킬 frontmatter 검증 (validate_skills)

미러링과 별개로, 스크립트는 정본 각 `.claude/skills/<스킬>/SKILL.md`의 frontmatter가 **Codex·Antigravity가 쓰는 엄격한 `agentskills.io` YAML 파서에서 깨지지 않는지** 매 실행마다 점검한다. 동기화 자체는 차단하지 않고, 문제가 있으면 stderr에 `[스킬 검증 경고]`를 띄운 뒤 종료 코드 `2`(확인 필요)를 낸다.

**왜 필요한가.** Claude Code의 frontmatter 파서는 관대해서 약간 깨진 YAML도 그냥 로드한다. 그래서 정본만 보면 멀쩡해 보이지만, 같은 파일을 미러링한 `.agents/skills/`를 Codex가 읽을 때만 조용히 스킬이 누락되거나 warning이 난다. 이 검증은 그 **"한쪽에서만 깨지는"** 상황을 정본 단계에서 미리 잡는다.

**무엇을 잡나** (PyYAML이 있으면 정식 파싱):
- frontmatter(`---` 블록) 부재 또는 닫는 `---` 누락
- **YAML 파싱 실패** — 가장 흔한 함정은 `description`이 plain scalar인데 값 안에 `… 사용: 키워드`처럼 **`: `(콜론+공백)**이 있는 경우. 엄격한 파서는 이를 중첩 매핑으로 오인해 `mapping values are not allowed here`로 실패한다.
- `name`이 폴더명과 불일치 (표준은 일치 요구)
- `description` 비어 있음 또는 1024자 초과

PyYAML이 없으면 휴리스틱 폴백이 frontmatter 부재·닫는 `---` 누락·최상위 plain scalar 값의 `: `·`name` 불일치만 잡는다. block scalar `description`의 빈 값·길이 초과와 그 밖의 YAML 오류는 폴백에서 걸리지 않는다.

**해법(=작성 규칙).** `description`에 콜론·따옴표 등이 들어갈 수 있으므로 **항상 block scalar(`>-`)로 감싼다**:

```yaml
---
name: 내-스킬            # 폴더명과 정확히 일치
description: >-
  한 줄 요약. 다음 키워드가 포함된 요청에 사용: A, B, C.
---
```

값 안에 콜론이 있어도 block scalar라 안전하다. block scalar 안의 `#`는 주석이 아니라 값의 일부이니 설명을 덧붙이지 않는다.

> **한글 `name`은 의도적으로 허용한다.** 표준은 `name`을 lowercase ASCII로 쓰고 폴더명과 일치시키라고 요구하지만, 한글 호출명(`/스킬`)을 유지하는 프로젝트에서는 한글 폴더명=한글 name으로 두고, Antigravity는 name 미준수 시 폴더명으로 폴백한다. 그래서 검증은 ASCII 여부를 **문제로 보지 않고**, 실제로 깨지는 것(파싱 실패·frontmatter 부재·name↔폴더명 불일치)만 잡는다. 영문 slug로 컴파일하는 방식도 가능하나, 정본↔생성물 폴더명 불일치·매핑 유지보수 비용 때문에 기본값은 단순 미러링이다.
