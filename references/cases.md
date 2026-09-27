# 사례

규칙의 근거가 된 사고와 실측. 절 제목은 규칙이 있는 절(SKILL.md, `references/troubleshooting.md`, `references/agy.md`)과 짝이다.

## 실행 전 필수 게이트

2026-06-05, 작성자 본인의 환경(`~/.claude`)에서 스킬 48개 중 **45개가 `.agents/skills/`로의 symlink**였다(`k-skill-setup`이 agentskills.io 표준 위치에 실파일을 두고 `.claude/skills/`에서 역방향 링크). 게이트가 없던 탓에 에이전트가 미러링 실행 직전까지 갔고, 수동 진단으로만 "고아 정리가 실제 스킬 45개를 삭제"하는 결과를 사전에 막았다. **스킬을 만든 사람조차 자기 환경을 오인했다.** 그래서 추정이 아니라 SKILL.md의 게이트 명령으로 확정한다.

## 머신 간 동기화 폴더(NFC/NFD) 주의

2026-07-15 실사고: 한 드라이브에서 `AGENTS.md` 18개 오삭제. 상태 키 NFC 정규화(`norm_key`)와 형제 `CLAUDE.md` 실존 확인(`has_sibling_canonical`)이 이 사고의 재발 방지책이며, `tests/test_sync_agent_docs.py`의 T1~T4가 이 시나리오다.

## 드리프트 가드 (Windows 전용)

2026-08-25 도입. 물리 복사본을 agy 쪽에서 고친 수정이 다음 동기화의 rmtree+copytree로 경고 없이 사라질 수 있음을 보고 넣었다.

## 왜 별도 스크립트인가

2026-08-24 카나리 실측으로 확정했다. agy 글로벌 루트는 agy 바이너리 문자열과 카나리 A/B로, Windows junction 미추종은 같은 이름·같은 내용·같은 자리에서 junction과 실제 폴더를 바꿔 넣은 통제 실험으로 확인했다.

## 진단: 모델에게 묻지 말 것

agy 로그에 "컨텍스트 예산 초과" 같은 배제 기제는 존재하지 않았고, 로드된 스킬과 안 된 스킬 사이에 파일 크기·줄바꿈·설명 길이 어떤 차이도 없었다.
