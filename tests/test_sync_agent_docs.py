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
  T7~T21 스킬 미러링 안전 가드, 고아 정리 최종 가드 (test_skill_safety 참조)

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


SKILL_MD = "---\nname: {name}\ndescription: >-\n  시험용 스킬.\n---\n본문\n"


def run_main(mod, *argv: str) -> int:
    saved = sys.argv
    sys.argv = ["sync_agent_docs.py", *argv]
    try:
        return mod.main()
    finally:
        sys.argv = saved


def test_skill_safety() -> list[str]:
    """T7~T21 — 스킬 미러링 안전 가드와 고아 정리 최종 가드.

      T7  .claude/skills/ 최상위에 symlink 가 있으면(정본 방향 역전 의심) 미러링을 멈추고
          .agents/skills/ 의 파일을 지우지 않으며 종료 코드 2 를 낸다
      T8  .env*·secrets* 비밀 파일은 미러링하지 않고, 예전에 복제된 것은 생성물에서 지운다
      T9  키 비교가 빗나가도 형제 CLAUDE.md 가 살아 있으면 고아로 지우지 않는다(has_sibling_canonical)
      T10 스킬 폴더 통째 역전(.claude/skills·.agents/skills·.claude 링크)도 멈추고 원본을 지우지 않는다
      T11 스킬 안쪽 폴더 symlink 도 멈춘다
      T12 secrets/ 폴더·대소문자 변형은 제외하고 secrets_util.py 같은 코드 파일은 미러링한다
      T13 밖을 가리키는 중첩 symlink 도 멈춘다(옛 미러 보존)
      T14 대소문자만 다른 역전 링크도 겹침으로 알아본다(대소문자 무시 파일시스템에서만)
      T15 생성물 쪽 스킬이 원본을 가리키는 링크면 멈춘다(junction 모사 포함)
      T16 생성물 안 파일 symlink 가 있으면 멈춘다(링크를 타고 밖을 덮지 않음)
      T17 생성물이 프로젝트 밖 실체면 멈춘다
      T18 생성물 루트가 원본 안쪽을 가리키면 멈춘다
      T19 .envrc·확장자 없는 secrets 파일도 제외
      T20 원본 루트가 생성물 안쪽을 가리키면 멈춘다
      T21 원본 안 junction 이 생성물 안을 가리키면 멈춘다(junction 모사)
    """
    failures = []
    if os.name == "nt":
        return failures  # symlink 생성 권한이 필요해 POSIX 에서만 돈다
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        (root / "CLAUDE.md").write_text("# 루트\n", encoding="utf-8")
        real = root / ".agents" / "skills" / "s1"
        real.mkdir(parents=True)
        (real / "SKILL.md").write_text(SKILL_MD.format(name="s1"), encoding="utf-8")
        src = root / ".claude" / "skills"
        src.mkdir(parents=True)
        (src / "s1").symlink_to(real, target_is_directory=True)
        (src / "own").mkdir()
        (src / "own" / "SKILL.md").write_text(SKILL_MD.format(name="own"), encoding="utf-8")
        mod = load_module(root)
        code = run_main(mod)
        if not (real / "SKILL.md").exists():
            failures.append("T7 실패: 역전 환경에서 .agents/skills/ 의 실제 스킬 파일이 지워짐")
        if code != 2:
            failures.append(f"T7 실패: 역전 환경인데 종료 코드 {code} (기대 2)")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        (root / "CLAUDE.md").write_text("# 루트\n", encoding="utf-8")
        k = root / ".claude" / "skills" / "k"
        k.mkdir(parents=True)
        (k / "SKILL.md").write_text(SKILL_MD.format(name="k"), encoding="utf-8")
        (k / "config.yaml").write_text("a: 1\n", encoding="utf-8")
        for secret in (".env", ".env.local", "secrets.yaml"):
            (k / secret).write_text("KEY=x\n", encoding="utf-8")
        old = root / ".agents" / "skills" / "k"
        old.mkdir(parents=True)
        (old / ".env").write_text("KEY=old\n", encoding="utf-8")
        mod = load_module(root)
        code = run_main(mod)
        for keep in ("SKILL.md", "config.yaml"):
            if not (old / keep).exists():
                failures.append(f"T8 실패: 일반 파일 {keep} 이 미러링되지 않음")
        for secret in (".env", ".env.local", "secrets.yaml"):
            if (old / secret).exists():
                failures.append(f"T8 실패: 비밀 파일 {secret} 이 생성물에 남음")
        if code != 0:
            failures.append(f"T8 실패: 종료 코드 {code} (기대 0)")

    # T9: 키 비교가 빗나가도(walk 가 못 본 symlink 폴더) 형제 CLAUDE.md 가 살아 있으면 지우지 않는다
    with tempfile.TemporaryDirectory() as td:
        base = Path(td).resolve()
        root = base / "proj"
        root.mkdir()
        (root / "CLAUDE.md").write_text("# 루트\n", encoding="utf-8")
        outside = base / "outside"
        outside.mkdir()
        (outside / "CLAUDE.md").write_text("# 밖\n", encoding="utf-8")
        (root / "linked").symlink_to(outside, target_is_directory=True)
        mod = load_module(root)
        (outside / "AGENTS.md").write_text(mod.BANNER + "# 밖\n", encoding="utf-8")
        mod.STATE_FILE.write_text(json.dumps({"linked/AGENTS.md": mod.sha256("# 밖\n")}), encoding="utf-8")
        run_main(mod)
        if not (outside / "AGENTS.md").exists():
            failures.append("T9 실패: 형제 CLAUDE.md 가 살아 있는 AGENTS.md 가 고아로 지워짐")

    # T10: 스킬 폴더 통째 역전(세 모양)도 멈추고 원본 쪽 파일을 하나도 지우지 않는다
    for shape in ("claude-skills->agents", "agents-skills->claude", "claude->agents"):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            (root / "CLAUDE.md").write_text("# 루트\n", encoding="utf-8")
            if shape == "agents-skills->claude":
                real = root / ".claude" / "skills"
            else:
                real = root / ".agents" / "skills"
            k = real / "k"
            (k / ".git").mkdir(parents=True)
            (k / "credentials").mkdir()
            (k / "SKILL.md").write_text(SKILL_MD.format(name="k"), encoding="utf-8")
            (k / ".env").write_text("KEY=x\n", encoding="utf-8")
            (k / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")
            (k / "credentials" / "token.json").write_text("{}\n", encoding="utf-8")
            if shape == "claude-skills->agents":
                (root / ".claude").mkdir()
                (root / ".claude" / "skills").symlink_to(real, target_is_directory=True)
            elif shape == "agents-skills->claude":
                (root / ".agents").mkdir()
                (root / ".agents" / "skills").symlink_to(real, target_is_directory=True)
            else:
                (root / ".claude").symlink_to(root / ".agents", target_is_directory=True)
            mod = load_module(root)
            code = run_main(mod)
            for rel in (".env", ".git/HEAD", "credentials/token.json", "SKILL.md"):
                if not (k / rel).exists():
                    failures.append(f"T10 실패({shape}): 원본 {rel} 이 지워짐")
            if (real / "_GENERATED.md").exists():
                failures.append(f"T10 실패({shape}): 원본 쪽에 _GENERATED.md 를 씀")
            if code != 2:
                failures.append(f"T10 실패({shape}): 종료 코드 {code} (기대 2)")

    # T11: 스킬 안쪽(중첩) 폴더 symlink 도 멈춘다
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        (root / "CLAUDE.md").write_text("# 루트\n", encoding="utf-8")
        lib = root / ".agents" / "skills" / "k" / "lib"
        lib.mkdir(parents=True)
        (lib / "real.py").write_text("x = 1\n", encoding="utf-8")
        k = root / ".claude" / "skills" / "k"
        k.mkdir(parents=True)
        (k / "SKILL.md").write_text(SKILL_MD.format(name="k"), encoding="utf-8")
        (k / "lib").symlink_to(lib, target_is_directory=True)
        mod = load_module(root)
        code = run_main(mod)
        if not (lib / "real.py").exists():
            failures.append("T11 실패: 중첩 symlink 너머의 실제 파일이 지워짐")
        if code != 2:
            failures.append(f"T11 실패: 종료 코드 {code} (기대 2)")

    # T12: secrets/ 폴더와 대소문자 변형은 제외, 이름에 secrets 가 든 코드 파일은 미러링
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        (root / "CLAUDE.md").write_text("# 루트\n", encoding="utf-8")
        k = root / ".claude" / "skills" / "k"
        (k / "secrets").mkdir(parents=True)
        (k / "lib").mkdir()
        (k / "SKILL.md").write_text(SKILL_MD.format(name="k"), encoding="utf-8")
        (k / "secrets" / "api.json").write_text("{}\n", encoding="utf-8")
        (k / "lib" / "secrets_util.py").write_text("x = 1\n", encoding="utf-8")
        (k / ".ENV").write_text("KEY=x\n", encoding="utf-8")
        mod = load_module(root)
        run_main(mod)
        out = root / ".agents" / "skills" / "k"
        if (out / "secrets" / "api.json").exists():
            failures.append("T12 실패: secrets/ 폴더가 미러링됨")
        if (out / ".ENV").exists():
            failures.append("T12 실패: 대문자 .ENV 가 미러링됨")
        if not (out / "lib" / "secrets_util.py").exists():
            failures.append("T12 실패: 코드 파일 secrets_util.py 가 제외됨")

    # T13: 밖을 가리키는 중첩 symlink 도 멈춘다(그대로 두면 옛 미러가 고아로 지워진다)
    with tempfile.TemporaryDirectory() as td:
        base = Path(td).resolve()
        root = base / "proj"
        (root / ".claude" / "skills" / "k").mkdir(parents=True)
        (root / "CLAUDE.md").write_text("# 루트\n", encoding="utf-8")
        (root / ".claude" / "skills" / "k" / "SKILL.md").write_text(SKILL_MD.format(name="k"), encoding="utf-8")
        ext = base / "ext-lib"
        ext.mkdir()
        (ext / "a.py").write_text("x = 1\n", encoding="utf-8")
        (root / ".claude" / "skills" / "k" / "lib").symlink_to(ext, target_is_directory=True)
        old = root / ".agents" / "skills" / "k" / "lib"
        old.mkdir(parents=True)
        (old / "a.py").write_text("x = 1\n", encoding="utf-8")
        mod = load_module(root)
        code = run_main(mod)
        if not (old / "a.py").exists():
            failures.append("T13 실패: 밖을 가리키는 중첩 symlink 때문에 옛 미러가 지워짐")
        if code != 2:
            failures.append(f"T13 실패: 종료 코드 {code} (기대 2)")

    # T14: 대소문자만 다른 경로로 건 역전 링크(대소문자 무시 파일시스템)도 겹침으로 알아본다
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        k = root / ".agents" / "skills" / "k"
        (k / ".git").mkdir(parents=True)
        (k / "SKILL.md").write_text(SKILL_MD.format(name="k"), encoding="utf-8")
        (k / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")
        if (root / ".AGENTS").exists():  # 대소문자 무시 파일시스템에서만 의미가 있다
            (root / "CLAUDE.md").write_text("# 루트\n", encoding="utf-8")
            (root / ".claude").mkdir()
            (root / ".claude" / "skills").symlink_to(root / ".AGENTS" / "skills", target_is_directory=True)
            mod = load_module(root)
            code = run_main(mod)
            if not (k / ".git" / "HEAD").exists():
                failures.append("T14 실패: 대소문자 변형 역전 링크에서 원본 .git 이 지워짐")
            if code != 2:
                failures.append(f"T14 실패: 종료 코드 {code} (기대 2)")

    # T15: 생성물 쪽 스킬이 원본을 가리키는 링크면 멈춘다(Windows junction 처럼 walk 가 따라가도 안전)
    for follow in (False, True):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            (root / "CLAUDE.md").write_text("# 루트\n", encoding="utf-8")
            k = root / ".claude" / "skills" / "k"
            (k / ".git").mkdir(parents=True)
            (k / "SKILL.md").write_text(SKILL_MD.format(name="k"), encoding="utf-8")
            (k / ".env").write_text("KEY=x\n", encoding="utf-8")
            (k / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")
            (root / ".agents" / "skills").mkdir(parents=True)
            (root / ".agents" / "skills" / "k").symlink_to(k, target_is_directory=True)
            mod = load_module(root)
            real_walk = os.walk
            if follow:  # junction 모사: walk 가 링크를 따라 들어간다
                mod.os.walk = lambda top, **kw: real_walk(top, **{**kw, "followlinks": True})
            try:
                code = run_main(mod)
            finally:
                mod.os.walk = real_walk
            for rel in (".env", ".git/HEAD", "SKILL.md"):
                if not (k / rel).exists():
                    failures.append(f"T15 실패(follow={follow}): 원본 {rel} 이 지워짐")
            if code != 2:
                failures.append(f"T15 실패(follow={follow}): 종료 코드 {code} (기대 2)")

    # T16: 생성물 안 파일 symlink 는 쓰기가 링크를 타고 밖을 덮으므로 멈춘다
    with tempfile.TemporaryDirectory() as td:
        base = Path(td).resolve()
        root = base / "proj"
        k = root / ".claude" / "skills" / "foo"
        k.mkdir(parents=True)
        (root / "CLAUDE.md").write_text("# 루트\n", encoding="utf-8")
        (k / "SKILL.md").write_text(SKILL_MD.format(name="foo"), encoding="utf-8")
        ext = base / "ext-SKILL.md"
        ext.write_text("외부 정본\n", encoding="utf-8")
        (root / ".agents" / "skills" / "foo").mkdir(parents=True)
        (root / ".agents" / "skills" / "foo" / "SKILL.md").symlink_to(ext)
        mod = load_module(root)
        code = run_main(mod)
        if ext.read_text(encoding="utf-8") != "외부 정본\n":
            failures.append("T16 실패: 생성물의 파일 symlink 를 타고 외부 파일을 덮어씀")
        if code != 2:
            failures.append(f"T16 실패: 종료 코드 {code} (기대 2)")

    # T17: 생성물(.agents)이 프로젝트 밖 실체면 멈춘다
    with tempfile.TemporaryDirectory() as td:
        base = Path(td).resolve()
        root = base / "proj"
        k = root / ".claude" / "skills" / "k"
        k.mkdir(parents=True)
        (root / "CLAUDE.md").write_text("# 루트\n", encoding="utf-8")
        (k / "SKILL.md").write_text(SKILL_MD.format(name="k"), encoding="utf-8")
        outside = base / "home-agents"
        (outside / "skills" / "other").mkdir(parents=True)
        (outside / "skills" / "other" / "SKILL.md").write_text(SKILL_MD.format(name="other"), encoding="utf-8")
        (root / ".agents").symlink_to(outside, target_is_directory=True)
        mod = load_module(root)
        code = run_main(mod)
        if not (outside / "skills" / "other" / "SKILL.md").exists():
            failures.append("T17 실패: 프로젝트 밖 생성물 자리의 파일이 지워짐")
        if code != 2:
            failures.append(f"T17 실패: 종료 코드 {code} (기대 2)")

    # T18: 생성물 루트가 원본 안쪽을 가리키면(원본 ⊃ 생성물) 멈춘다
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        (root / "CLAUDE.md").write_text("# 루트\n", encoding="utf-8")
        k = root / ".claude" / "skills" / "k"
        (k / "sub").mkdir(parents=True)
        (k / "SKILL.md").write_text(SKILL_MD.format(name="k"), encoding="utf-8")
        (k / ".env").write_text("KEY=x\n", encoding="utf-8")
        (k / "sub" / "a.py").write_text("x = 1\n", encoding="utf-8")
        (root / ".agents").mkdir()
        (root / ".agents" / "skills").symlink_to(k, target_is_directory=True)
        mod = load_module(root)
        code = run_main(mod)
        for rel in (".env", "SKILL.md", "sub/a.py"):
            if not (k / rel).exists():
                failures.append(f"T18 실패: 원본 {rel} 이 지워짐")
        if code != 2:
            failures.append(f"T18 실패: 종료 코드 {code} (기대 2)")

    # T19: .envrc 와 확장자 없는 secrets 파일도 제외
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        (root / "CLAUDE.md").write_text("# 루트\n", encoding="utf-8")
        k = root / ".claude" / "skills" / "k"
        k.mkdir(parents=True)
        (k / "SKILL.md").write_text(SKILL_MD.format(name="k"), encoding="utf-8")
        (k / ".envrc").write_text("export KEY=x\n", encoding="utf-8")
        (k / "secrets").write_text("KEY=x\n", encoding="utf-8")
        mod = load_module(root)
        run_main(mod)
        out = root / ".agents" / "skills" / "k"
        for name in (".envrc", "secrets"):
            if (out / name).exists():
                failures.append(f"T19 실패: {name} 이 미러링됨")

    # T20: 원본 루트가 생성물 안쪽을 가리키면(생성물 ⊃ 원본) 멈춘다
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        (root / "CLAUDE.md").write_text("# 루트\n", encoding="utf-8")
        x = root / ".agents" / "skills" / "x"
        x.mkdir(parents=True)
        (x / "SKILL.md").write_text(SKILL_MD.format(name="x"), encoding="utf-8")
        (x / ".env").write_text("KEY=x\n", encoding="utf-8")
        (root / ".claude").mkdir()
        (root / ".claude" / "skills").symlink_to(x, target_is_directory=True)
        mod = load_module(root)
        code = run_main(mod)
        for rel in ("SKILL.md", ".env"):
            if not (x / rel).exists():
                failures.append(f"T20 실패: 생성물 안의 원본 {rel} 이 지워짐")
        if code != 2:
            failures.append(f"T20 실패: 종료 코드 {code} (기대 2)")

    # T21: 원본 안 junction 이 생성물 안을 가리키면 멈춘다(junction 모사: symlink 로 만들고
    #      is_symlink 는 False·is_junction 은 True 로 보이게, walk 는 따라가게)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        (root / "CLAUDE.md").write_text("# 루트\n", encoding="utf-8")
        lib = root / ".agents" / "skills" / "k" / "lib"
        lib.mkdir(parents=True)
        (lib / "real.py").write_text("x = 1\n", encoding="utf-8")
        (lib / ".env").write_text("KEY=x\n", encoding="utf-8")
        k = root / ".claude" / "skills" / "k"
        k.mkdir(parents=True)
        (k / "SKILL.md").write_text(SKILL_MD.format(name="k"), encoding="utf-8")
        (k / "junc").symlink_to(lib, target_is_directory=True)
        mod = load_module(root)

        class JunctionPath(type(Path())):
            def is_symlink(self):
                return False if self.name == "junc" else super().is_symlink()

            def is_junction(self):
                return self.name == "junc"

        real_walk, real_path = os.walk, mod.Path
        mod.os.walk = lambda top, **kw: real_walk(top, **{**kw, "followlinks": True})
        mod.Path = JunctionPath
        try:
            code = run_main(mod)
        finally:
            mod.os.walk, mod.Path = real_walk, real_path
        if not (lib / ".env").exists():
            failures.append("T21 실패: 생성물을 가리키는 junction 때문에 .env 가 지워짐")
        if code != 2:
            failures.append(f"T21 실패: 종료 코드 {code} (기대 2)")
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
    failures += test_skill_safety()

    if failures:
        print("\n".join(failures))
        return 1
    print("모든 테스트 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
