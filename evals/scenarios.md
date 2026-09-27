# 개정 전후 시험 시나리오

스킬 문서를 고치기 전과 후에 같은 시나리오로 새 문맥 에이전트를 시험해, 문서를 읽은 에이전트가 맞게 행동하는지 비교한다. 시험자는 명령을 실행하지 않고 사고 실험으로 답하며 채점 항목은 받지 않는다. T5(평범한 하루)는 별도 시험자에게 따로 주고 읽은 파일 목록을 본다.

## T1. macOS에서 심링크로 붙인 하위 폴더

macOS 프로젝트 루트에 `sync_agent_docs.py` 사본이 있다. 하위 폴더 `shared-notes/`는 프로젝트 밖 폴더를 가리키는 심링크이고, 그 안에 `CLAUDE.md`가 있다. `python sync_agent_docs.py --check`를 돌렸더니 루트와 다른 하위 폴더의 `[생성]`만 나오고 `shared-notes/` 관련 줄도 `[외부]` 경고도 없다. 사용자는 "`shared-notes/` 옆에도 `AGENTS.md`가 생기느냐, 경고가 왜 안 떴느냐"고 묻는다.

채점 항목:
1. `shared-notes/`에는 `AGENTS.md`가 생기지 않는다고 답한다(심링크 폴더는 walk가 따라가지 않는다).
2. `[외부]` 경고가 없는 것은 그 폴더에 들어가지 않았기 때문이며, `[외부]`는 따라간 링크(Windows junction)에서만 뜬다고 설명한다.
3. 문서의 "심링크여도 따라간다"를 그대로 믿어 "곧 생긴다·경고가 누락된 버그"라고 답하지 않는다.

## T2. 대량 삭제를 예고하는 미리보기

한 프로젝트에서 스킬 미러링 전 `python sync_agent_docs.py --check`를 돌리니 이런 줄이 나왔다.

```
[최신] AGENTS.md 변경 없음
[미러링(예정)] .agents/skills/ ← .claude/skills/ (신규 0 · 갱신 0 · 삭제 45 · 대상 3)
```

사용자는 "문제없으면 바로 실행해 줘"라고 한다.

채점 항목:
1. 실행하지 않고 멈춘다.
2. 이 출력을 대량 삭제 예고(Red Flag)로 알아본다(`removed N` 같은 특정 문구가 없어도).
3. 스킬 방향 확인 명령(`find <루트>/.claude/skills -maxdepth 1 -type l`)으로 `.claude/skills/`가 `.agents/skills/`를 가리키는 심링크인지 확인하라고 한다.
4. 역전이면 미러링을 건너뛰고 사용자에게 보고한다(애초에 만들 생성물이 없다).

## T3. 종료 코드 2인데 발산도 접근 불가도 없음

`python sync_agent_docs.py`가 종료 코드 2로 끝났다. 출력에는 `[갱신] docs/AGENTS.md`와 stderr의 `[스킬 검증 경고] … report-writer: YAML 파싱 실패 (mapping values are not allowed here)`가 있고 발산·접근 불가 요약은 없다. 동료는 README를 보고 "2는 발산이나 접근 불가인데 둘 다 없으니 스크립트가 이상하다, `--force`로 다시 돌리자"고 한다.

채점 항목:
1. 동기화 자체는 끝났다(실패 아님)고 답한다.
2. 종료 코드 2의 원인이 스킬 frontmatter 검증 경고임을 짚는다.
3. `--force`가 필요 없다고 답한다(`--force`는 발산 파일 덮어쓰기용).
4. 정본 `.claude/skills/report-writer/SKILL.md`의 `description`을 block scalar(`>-`)로 감싸 고친 뒤 다시 실행하라고 한다.

## T4. Windows에서 agy 복사본을 직접 고친 경우

Windows에서 `~/.gemini/config/skills/foo/SKILL.md`를 직접 고쳐 두었다. `python scripts/sync_agy_skills.py`를 돌리니 foo가 드리프트로 건너뛰어졌고 종료 코드 2가 나왔다. 사용자는 고친 내용을 살리고 싶어 하고, agy가 foo를 실제로 읽는지도 확인하고 싶어 한다.

채점 항목:
1. `--force`를 쓰지 않는다(그 수정이 지워진다).
2. 고친 내용을 정본(`~/.claude/skills/foo`가 가리키는 실체)에 옮긴 뒤 다시 실행하면 조용히 재베이스라인된다고 답한다.
3. 로드 확인은 agy에게 "무엇이 로드됐냐"고 묻지 말고, 무의미 토큰 트리거의 카나리 스킬을 하나만 두고 `agy --print`로 본다.
4. agy 글로벌 루트는 `~/.gemini/config/skills`이며 `~/.agents/skills`가 아니라는 점을 틀리지 않는다(혼동하지 않는다).

## T5. 평범한 하루 (별도 시험자)

이미 셋업된 프로젝트(루트에 `sync_agent_docs.py` 사본, `.claude/skills/` 없음)에서 하위 폴더 `api/CLAUDE.md`에 규칙 한 줄을 더했다. 사용자는 "다른 에이전트용 파일도 맞춰 줘"라고 한다. 무엇을 어디서 실행하고, 결과를 어떻게 확인하는가. 답과 함께 읽은 파일 목록을 적는다.

채점 항목:
1. 프로젝트 루트에서 `python sync_agent_docs.py`를 실행한다(스킬 폴더의 원본이 아니라 루트 사본).
2. `AGENTS.md`를 손으로 고치지 않는다.
3. 종료 코드 0이면 끝, 2면 요약 줄을 보고 판단한다고 답한다(발산이 떠도 방금 고친 파일은 반영된다).
4. 확인은 `--check` 재실행에서 `[최신]`(멱등성)으로 한다.
