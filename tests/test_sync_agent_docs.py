# -*- coding: utf-8 -*-
"""sync_agent_docs.py 회귀 테스트 — NFC/NFD 고아 오폭 (2026-07-15 실사고).

사고 시나리오: 상태 파일(.agent-docs-sync.json)이 Google Drive 로 머신 간 동기화되는
환경에서, macOS 실행이 남긴 NFD 한글 키와 Windows walk 의 NFC 키가 갈라짐.
고아 정리가 NFD 구키를 "대응 CLAUDE.md 없음"으로 오판했고, Google Drive 파일시스템은
NFD 별형 경로를 NFC 실파일로 해석(resolve)하므로 **살아 있는 AGENTS.md 를 실제 삭제**했다
(NTFS 는 별형을 해석하지 않아 로컬 테스트로는 삭제 자체가 재현되지 않음 — 그래서
이 테스트는 파일 삭제가 아니라 두 방어선을 검증한다):

  T1  load_state 가 상태 키를 NFC 로 정규화한다 (NFD 구키 흡수)
  T2  has_sibling_canonical 가드가 존재하고 대소문자 무관하게 동작한다
  T3  NFD 구키 상태로 sync_docs 를 돌려도 살아 있는 AGENTS.md 가 보존되고
      상태에 NFD 구키가 잔존하지 않는다
  T4  진짜 고아(CLAUDE.md 삭제됨)는 여전히 정리된다

실행: python tests/test_sync_agent_docs.py  (표준 라이브러리만 사용, 종료 코드 0=통과)
"""
import importlib.util
import json
import os
import sys
import tempfile
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sync_agent_docs.py"


def load_module(root: Path):
    spec = importlib.util.spec_from_file_location("sync_agent_docs", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # 테스트 루트로 모듈 상수 재지정
    mod.ROOT = root
    mod.ROOT_REAL = os.path.normcase(str(root))
    mod.CANONICAL = root / "CLAUDE.md"
    mod.STATE_FILE = root / ".agent-docs-sync.json"
    mod.SKILLS_SRC = root / ".claude" / "skills"
    mod.SKILLS_DST = root / ".agents" / "skills"
    return mod


class Args:
    check = False
    force = False


def main() -> int:
    failures = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        sub_nfc = unicodedata.normalize("NFC", "강연폴더")
        sub_nfd = unicodedata.normalize("NFD", "강연폴더")
        (root / "CLAUDE.md").write_text("# 루트 정본\n", encoding="utf-8")
        subdir = root / sub_nfc
        subdir.mkdir()
        (subdir / "CLAUDE.md").write_text("# 하위 정본\n", encoding="utf-8")

        mod = load_module(root)

        # 기존 생성물(배너 포함) 배치 = "직전 동기화가 만들어 둔 파일"
        body = "# 하위 정본\n"
        (subdir / "AGENTS.md").write_text(mod.BANNER + body, encoding="utf-8", newline="\n")
        (root / "AGENTS.md").write_text(mod.BANNER + "# 루트 정본\n", encoding="utf-8", newline="\n")

        # 상태 파일: macOS(NFD) 실행이 남긴 키를 시뮬레이션
        nfd_key = f"{sub_nfd}/AGENTS.md"
        nfc_key = f"{sub_nfc}/AGENTS.md"
        state_json = {
            "AGENTS.md": mod.sha256("# 루트 정본\n"),
            nfd_key: mod.sha256(body),
        }
        mod.STATE_FILE.write_text(json.dumps(state_json, ensure_ascii=False), encoding="utf-8")

        # ── T1: load_state 키 NFC 정규화 ──
        state = mod.load_state()
        if nfc_key not in state:
            failures.append(f"T1 실패: load_state가 NFD 키를 NFC로 정규화하지 않음: {list(state)!r}")

        # ── T2: 형제 CLAUDE.md 실존 가드 존재 + 동작 ──
        if not hasattr(mod, "has_sibling_canonical"):
            failures.append("T2 실패: has_sibling_canonical 가드 없음")
        else:
            if not mod.has_sibling_canonical(subdir):
                failures.append("T2 실패: CLAUDE.md 있는 폴더를 False로 판정")
            empty = root / "빈폴더"
            empty.mkdir()
            if mod.has_sibling_canonical(empty):
                failures.append("T2 실패: 빈 폴더를 True로 판정")
            lower = root / "소문자폴더"
            lower.mkdir()
            (lower / "claude.md").write_text("x", encoding="utf-8")
            if not mod.has_sibling_canonical(lower):
                failures.append("T2 실패: 소문자 claude.md를 인식 못 함")

        # ── T3: NFD 구키 상태로 sync_docs 실행 → 살아 있는 AGENTS.md 보존 ──
        state = mod.load_state()
        mod.sync_docs(Args(), state)
        if not (subdir / "AGENTS.md").exists():
            failures.append("T3 실패: 살아 있는 AGENTS.md가 고아 정리로 삭제됨")
        if nfc_key not in state:
            failures.append(f"T3 실패: NFC 키가 상태에 없음: {list(state)!r}")
        if nfd_key != nfc_key and nfd_key in state:
            failures.append("T3 실패: NFD 구키가 상태에 잔존")

        # ── T4: 진짜 고아(CLAUDE.md 삭제됨)는 여전히 정리되어야 함 ──
        (subdir / "CLAUDE.md").unlink()
        state2 = mod.load_state()
        state2[nfc_key] = mod.sha256(body)  # 관리 이력 존재 시뮬레이션
        mod.sync_docs(Args(), state2)
        if (subdir / "AGENTS.md").exists():
            failures.append("T4 실패: 진짜 고아 AGENTS.md가 정리되지 않음")

    if failures:
        print("\n".join(failures))
        return 1
    print("모든 테스트 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
