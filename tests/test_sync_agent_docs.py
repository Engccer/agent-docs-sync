# -*- coding: utf-8 -*-
"""sync_agent_docs.py 회귀 테스트 — 고아 정리 오폭 (T1~T4 NFC/NFD, T5·T6 접근 불가).

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
  T5·T6  접근 불가 경로 (test_unreachable_folder 참조)

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


def test_unreachable_folder() -> list[str]:
    """T5·T6 — 접근 불가 경로 (실제로 일어난 사고).

    SSH 세션의 RedirectionGuard 가 클라우드 드라이브로 가는 junction 통과를 막자(WinError 448),
    os.walk 가 그 폴더를 조용히 건너뛰어 살아 있는 쌍이 고아 후보가 됐고, 고아 판정의
    exists() 가 OSError 를 던져 실행 전체가 멈췄다.

      T5  walk 가 못 들어간 폴더의 AGENTS.md 는 고아로 판정하지 않고 상태키를 보존한다
          (폴더 목록만 막히고 파일 stat 은 되는 경우: 접두어 보류가 유일한 방어선)
      T6  고아 후보 판정 중 OSError 가 나도 멈추지 않고 나머지 고아는 계속 정리한다
    """
    failures = []
    real_scandir = os.scandir
    real_listdir = os.listdir
    real_exists = Path.exists
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        (root / "CLAUDE.md").write_text("# 루트\n", encoding="utf-8")
        mod = load_module(root)
        blocked = root / "막힌폴더"
        blocked.mkdir()
        (blocked / "CLAUDE.md").write_text("# 막힌 정본\n", encoding="utf-8")
        (blocked / "AGENTS.md").write_text(mod.BANNER + "# 막힌 정본\n", encoding="utf-8")
        gone = root / "사라진폴더"
        gone.mkdir()
        (gone / "AGENTS.md").write_text(mod.BANNER + "# 옛 정본\n", encoding="utf-8")
        stuck = root / "판정불가"
        stuck.mkdir()
        blocked_key = "막힌폴더/AGENTS.md"
        stuck_key = "판정불가/없는하위/AGENTS.md"
        state = {
            "AGENTS.md": mod.sha256("# 루트\n"),
            blocked_key: mod.sha256("# 막힌 정본\n"),
            stuck_key: mod.sha256("x"),  # 진짜 고아보다 앞에 둬 "막힌 뒤에도 계속"을 검증
            "사라진폴더/AGENTS.md": mod.sha256("# 옛 정본\n"),
        }

        def fake_scandir(path="."):
            if Path(path) == blocked:
                raise OSError(22, "신뢰할 수 없는 탑재 지점", str(path))
            return real_scandir(path)

        def fake_listdir(path="."):
            if Path(path) == blocked:
                raise OSError(22, "신뢰할 수 없는 탑재 지점", str(path))
            return real_listdir(path)

        def fake_exists(self, *a, **kw):
            if stuck in self.parents:
                raise OSError(22, "신뢰할 수 없는 탑재 지점", str(self))
            return real_exists(self, *a, **kw)

        os.scandir = fake_scandir
        os.listdir = fake_listdir
        Path.exists = fake_exists
        try:
            _, _, skipped = mod.sync_docs(Args(), state)
        except OSError as e:
            return [f"T5/T6 실패: 접근 불가 경로에서 sync_docs 가 멈춤: {e!r}"]
        finally:
            os.scandir = real_scandir
            os.listdir = real_listdir
            Path.exists = real_exists

        # T5
        if not (blocked / "AGENTS.md").exists():
            failures.append("T5 실패: 접근 불가 폴더의 AGENTS.md가 삭제됨")
        if blocked_key not in state:
            failures.append("T5 실패: 접근 불가 폴더의 상태키가 지워짐")
        if "막힌폴더/" not in skipped:
            failures.append(f"T5 실패: 접근 불가 폴더가 건너뜀 목록에 없음: {skipped!r}")
        if blocked_key in skipped:
            failures.append("T5 실패: 접근 불가 폴더 안의 키가 폴더 단위 보류 없이 개별 판정됨")
        # T6
        if stuck_key not in state or stuck_key not in skipped:
            failures.append("T6 실패: 판정 불가 고아 후보의 상태키가 보존·보고되지 않음")
        if (gone / "AGENTS.md").exists():
            failures.append("T6 실패: 막힌 경로 뒤의 진짜 고아가 정리되지 않음")
    return failures


def main() -> int:
    failures = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
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

    failures += test_unreachable_folder()

    if failures:
        print("\n".join(failures))
        return 1
    print("모든 테스트 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
