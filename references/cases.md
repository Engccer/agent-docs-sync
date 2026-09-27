# 사례

규칙의 근거가 된 사고와 실측. 절 제목은 규칙이 있는 절(SKILL.md, `references/troubleshooting.md`, `references/agy.md`)과 짝이다.

## 정본 방향 확인 (프로젝트 레벨, 틀리면 정본 파괴)

2026-06-05, 작성자 본인의 환경(`~/.claude`)에서 스킬 48개 중 **45개가 `.agents/skills/`로의 symlink**였다(`k-skill-setup`이 agentskills.io 표준 위치에 실파일을 두고 `.claude/skills/`에서 역방향 링크). 게이트가 없던 탓에 에이전트가 미러링 실행 직전까지 갔고, 수동 진단으로만 "고아 정리가 실제 스킬 45개를 삭제"하는 결과를 사전에 막았다. **스킬을 만든 사람조차 자기 환경을 오인했다.** 그래서 문서에 방향 확인 게이트를 두었고, 1.2.0부터는 스크립트가 `.claude/skills/`의 symlink 스킬을 감지해 미러링을 멈춘다.

## 머신 간 동기화 폴더(NFC/NFD) 주의

2026-07-15 실사고: 한 드라이브에서 `AGENTS.md` 18개 오삭제. 상태 키 NFC 정규화(`norm_key`)와 형제 `CLAUDE.md` 실존 확인(`has_sibling_canonical`)이 이 사고의 재발 방지책이며, `tests/test_sync_agent_docs.py`의 T1~T4가 이 시나리오이고, T9가 형제 `CLAUDE.md` 가드를 따로 확인한다(2026-09-27 감사 리뷰에서 그 가드를 지워도 T1~T4가 통과함을 찾았다).

## 정본을 지우지 않는 가드

2026-09-27 스킬 감사에서 가짜 HOME으로 재현했다: macOS에서 agy 루트의 실제 폴더가 확인 없이 지워졌고(allowlist 밖이면 정리, 안이면 symlink로 교체, 종료 코드 0), `~/.gemini/config/skills`를 `~/.claude/skills`에 링크하자 allowlist 밖 정본 스킬이 통째로 지워졌다(리뷰 2라운드: agy 루트를 `~/.agents/skills`에 링크해도 그 너머 정본이 지워졌다). 같은 감사에서 `.claude/skills/`의 symlink 스킬이 `.agents/skills/`를 가리키는 역전 환경은 실제 파일을 지우고도 종료 코드 0이었고, `.env`·`secrets.yaml`이 생성물로 복제됐다. 1.2.0에서 네 경우 모두 코드 가드와 시험(`tests/test_sync_agent_docs.py` T7·T8, `tests/test_sync_agy_skills.py` A1~A10)으로 막았다.

## 드리프트 가드 (Windows 전용)

2026-08-25 도입. 물리 복사본을 agy 쪽에서 고친 수정이 다음 동기화의 rmtree+copytree로 경고 없이 사라질 수 있음을 보고 넣었다.

## 왜 별도 스크립트인가

2026-08-24 카나리 실측으로 확정했다. agy 글로벌 루트는 agy 바이너리 문자열과 카나리 A/B로, Windows junction 미추종은 같은 이름·같은 내용·같은 자리에서 junction과 실제 폴더를 바꿔 넣은 통제 실험으로 확인했다.

## 진단: 모델에게 묻지 말 것

agy 로그에 "컨텍스트 예산 초과" 같은 배제 기제는 존재하지 않았고, 로드된 스킬과 안 된 스킬 사이에 파일 크기·줄바꿈·설명 길이 어떤 차이도 없었다.
