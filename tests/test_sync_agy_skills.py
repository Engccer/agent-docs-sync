# -*- coding: utf-8 -*-
"""sync_agy_skills.py 회귀 테스트 — POSIX(macOS) agy 루트의 실제 폴더 보호.

POSIX 는 agy 루트에 symlink 만 걸기 때문에 사본이 없다는 전제였지만, agy 루트에 이미
실제 폴더(agy 에 직접 설치했거나 손으로 만든 스킬)가 있으면 확인 없이 지워졌다.

  A1  allowlist 에 있는 스킬 자리에 정본과 다른 실제 폴더가 있으면 지우지 않고 건너뛴다(종료 2)
  A2  allowlist 밖의 실제 폴더는 정리하지 않고 건너뛴다(종료 2)
  A3  실제 폴더 내용이 정본과 같으면 잃을 것이 없으므로 symlink 로 바꾼다(종료 0)
  A4  --force <이름> 이면 실제 폴더도 symlink 로 바꾼다
  A5  allowlist 밖의 symlink 는 지금처럼 정리한다
  A6  agy 루트가 정본 루트를 가리키거나 겹치면 아무것도 하지 않고 종료 1
  A7  정본 실체가 agy 루트 안에 있으면(정본 링크가 agy 쪽 실제 폴더를 가리킴) 건드리지 않고 건너뛴다(종료 2)
  A8  Windows 복사 제외 규칙이 .env*·secrets* 를 거른다
  A9  agy 루트 자체가 링크면 가리키는 곳과 --force 에 상관없이 아무것도 하지 않고 종료 1
  A10 정본 루트가 agy 루트를 가리키는 겹침도 --force 와 상관없이 종료 1
  A11 정본과 같아 보여도 agy 쪽에만 제외 대상 파일(.env·.git 등)이 있으면 교체하지 않는다
  A12 allowlist 밖이어도 정본 실체는 --force 로도 지우지 않는다
  A13 상위 경로 링크로 agy 루트가 정본 실체들 자리여도 --force 로도 지우지 않는다(종료 1)
  A14 대소문자만 다른 경로의 정본 링크도 정본으로 알아본다(대소문자 무시 파일시스템)
  A15 이름 없는 --force 는 정본이 아닌 allowlist 밖 실제 폴더를 정리한다
  A16 Windows 분기(물리 복사)도 정본 실체는 --force 여도 지우지 않는다
  A17 Windows 분기의 물리 복사는 .env·.ENV.*·secrets/ 를 복사하지 않는다
  A18 지우려는 폴더 안쪽에 정본 실체가 있으면(조상 방향) --force 여도 지우지 않는다(POSIX·Windows 분기)
  A19 agy 루트까지의 상위 경로에 링크가 있으면 아무것도 지우지 않고 종료 1
  A20 .envrc·확장자 없는 secrets 도 복사 제외
  A21 agy 쪽 실제 폴더의 끊어진 symlink 에서 죽지 않고 그 스킬만 건너뛴다

실행: python tests/test_sync_agy_skills.py  (표준 라이브러리만 사용, 종료 코드 0=통과. symlink 를 만들므로 Windows 에서는 건너뜀.
      A16·A17 은 IS_WINDOWS 를 켜서 Windows 분기 코드를 POSIX 에서 돌린다)
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sync_agy_skills.py"
SKILL_MD = "---\nname: {name}\ndescription: >-\n  시험용 스킬.\n---\n본문\n"


def load_module(home: Path):
    spec = importlib.util.spec_from_file_location("sync_agy_skills", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # 가짜 HOME 으로 모듈 상수 재지정(실제 홈은 건드리지 않는다)
    mod.HOME = home
    mod.CANONICAL_ROOT = home / ".claude" / "skills"
    mod.AGY_ROOT = home / ".gemini" / "config" / "skills"
    mod.DEFAULT_LIST = home / ".gemini" / "agy-skills.txt"
    mod.MANIFEST_PATH = home / ".gemini" / "agy-sync-manifest.json"
    mod.IS_WINDOWS = False
    return mod


def make_home(td: str, names: list[str]) -> Path:
    home = Path(td).resolve()
    for n in names:
        d = home / ".claude" / "skills" / n
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(SKILL_MD.format(name=n), encoding="utf-8")
    (home / ".gemini" / "config" / "skills").mkdir(parents=True)
    (home / ".gemini" / "agy-skills.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    return home


def run_main(mod, *argv: str) -> int:
    saved = sys.argv
    sys.argv = ["sync_agy_skills.py", *argv]
    try:
        return mod.main()
    finally:
        sys.argv = saved


def main() -> int:
    if os.name == "nt":
        print("Windows: POSIX 전용 시험이라 건너뜀")
        return 0
    failures = []

    # A1: allowlist 안, 정본과 다른 실제 폴더 → 보존·종료 2
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, ["a"])
        mod = load_module(home)
        dst = mod.AGY_ROOT / "a"
        dst.mkdir()
        (dst / "SKILL.md").write_text(SKILL_MD.format(name="a") + "손으로 고친 줄\n", encoding="utf-8")
        code = run_main(mod)
        if dst.is_symlink() or "손으로 고친 줄" not in (dst / "SKILL.md").read_text(encoding="utf-8"):
            failures.append("A1 실패: 정본과 다른 실제 폴더가 symlink 로 교체됨")
        if code != 2:
            failures.append(f"A1 실패: 종료 코드 {code} (기대 2)")

    # A2: allowlist 밖 실제 폴더 → 보존·종료 2
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, ["a"])
        mod = load_module(home)
        native = mod.AGY_ROOT / "native"
        native.mkdir()
        (native / "SKILL.md").write_text(SKILL_MD.format(name="native"), encoding="utf-8")
        code = run_main(mod)
        if not (native / "SKILL.md").exists():
            failures.append("A2 실패: allowlist 밖 실제 폴더가 지워짐")
        if code != 2:
            failures.append(f"A2 실패: 종료 코드 {code} (기대 2)")

    # A3: 내용이 정본과 같은 실제 폴더 → symlink 로 교체·종료 0
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, ["a"])
        mod = load_module(home)
        dst = mod.AGY_ROOT / "a"
        dst.mkdir()
        (dst / "SKILL.md").write_text(SKILL_MD.format(name="a"), encoding="utf-8")
        code = run_main(mod)
        if not dst.is_symlink():
            failures.append("A3 실패: 정본과 같은 실제 폴더가 symlink 로 바뀌지 않음")
        if code != 0:
            failures.append(f"A3 실패: 종료 코드 {code} (기대 0)")

    # A4: --force a → 다른 실제 폴더도 symlink 로
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, ["a"])
        mod = load_module(home)
        dst = mod.AGY_ROOT / "a"
        dst.mkdir()
        (dst / "SKILL.md").write_text("다른 내용\n", encoding="utf-8")
        run_main(mod, "--force", "a")
        if not dst.is_symlink():
            failures.append("A4 실패: --force 인데 실제 폴더가 symlink 로 바뀌지 않음")

    # A5: allowlist 밖 symlink → 정리
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, ["a", "b"])
        mod = load_module(home)
        run_main(mod)
        (home / ".gemini" / "agy-skills.txt").write_text("a\n", encoding="utf-8")
        code = run_main(mod)
        if (mod.AGY_ROOT / "b").is_symlink():
            failures.append("A5 실패: allowlist 밖 symlink 가 정리되지 않음")
        if not (mod.CANONICAL_ROOT / "b" / "SKILL.md").exists():
            failures.append("A5 실패: 정리 중 정본이 지워짐")
        if code != 0:
            failures.append(f"A5 실패: 종료 코드 {code} (기대 0)")

    # A6: agy 루트가 정본 루트를 가리키면(겹침) 아무것도 지우지 않고 종료 1
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, ["a", "b"])
        (home / ".gemini" / "agy-skills.txt").write_text("a\n", encoding="utf-8")
        mod = load_module(home)
        mod.AGY_ROOT.rmdir()
        mod.AGY_ROOT.symlink_to(mod.CANONICAL_ROOT, target_is_directory=True)
        code = run_main(mod)
        for n in ("a", "b"):
            d = mod.CANONICAL_ROOT / n
            if d.is_symlink() or not (d / "SKILL.md").exists():
                failures.append(f"A6 실패: 루트 겹침에서 정본 {n} 이 지워지거나 링크로 바뀜")
        if code != 1:
            failures.append(f"A6 실패: 루트 겹침인데 종료 코드 {code} (기대 1)")

    # A7: 정본 링크가 agy 루트 안의 실제 폴더를 가리키면(사용자 레벨 역전) 건드리지 않고 종료 2
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, [])
        (home / ".gemini" / "agy-skills.txt").write_text("x\n", encoding="utf-8")
        mod = load_module(home)
        real = mod.AGY_ROOT / "x"
        real.mkdir()
        (real / "SKILL.md").write_text(SKILL_MD.format(name="x"), encoding="utf-8")
        mod.CANONICAL_ROOT.mkdir(parents=True, exist_ok=True)
        (mod.CANONICAL_ROOT / "x").symlink_to(real, target_is_directory=True)
        code = run_main(mod)
        if real.is_symlink() or not (real / "SKILL.md").exists():
            failures.append("A7 실패: agy 루트 안의 정본 실체가 지워지거나 링크로 바뀜")
        if code != 2:
            failures.append(f"A7 실패: 종료 코드 {code} (기대 2)")

    # A9: agy 루트 자체가 링크면(정본 루트가 아닌 곳을 가리켜도) --force 여도 아무것도 지우지 않고 종료 1
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, [])
        mod = load_module(home)
        other = home / ".agents" / "skills"
        for n in ("kx", "ky"):
            (other / n).mkdir(parents=True)
            (other / n / "SKILL.md").write_text(SKILL_MD.format(name=n), encoding="utf-8")
            (mod.CANONICAL_ROOT / n).parent.mkdir(parents=True, exist_ok=True)
            (mod.CANONICAL_ROOT / n).symlink_to(other / n, target_is_directory=True)
        (home / ".gemini" / "agy-skills.txt").write_text("kx\n", encoding="utf-8")
        mod.AGY_ROOT.rmdir()
        mod.AGY_ROOT.symlink_to(other, target_is_directory=True)
        code = run_main(mod, "--force")
        for n in ("kx", "ky"):
            if (other / n).is_symlink() or not (other / n / "SKILL.md").exists():
                failures.append(f"A9 실패: 링크된 agy 루트 너머의 정본 {n} 이 지워지거나 링크로 바뀜")
        if code != 1:
            failures.append(f"A9 실패: agy 루트가 링크인데 종료 코드 {code} (기대 1)")

    # A10: 정본 루트가 (실제 폴더인) agy 루트를 가리키면 겹침 → --force 여도 종료 1, 아무것도 지우지 않음
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, [])
        mod = load_module(home)
        for n in ("a", "b"):
            (mod.AGY_ROOT / n).mkdir()
            (mod.AGY_ROOT / n / "SKILL.md").write_text(SKILL_MD.format(name=n), encoding="utf-8")
        mod.CANONICAL_ROOT.parent.mkdir(parents=True, exist_ok=True)
        if mod.CANONICAL_ROOT.exists():
            mod.CANONICAL_ROOT.rmdir()
        mod.CANONICAL_ROOT.symlink_to(mod.AGY_ROOT, target_is_directory=True)
        (home / ".gemini" / "agy-skills.txt").write_text("a\n", encoding="utf-8")
        code = run_main(mod, "--force")
        for n in ("a", "b"):
            d = mod.AGY_ROOT / n
            if d.is_symlink() or not (d / "SKILL.md").exists():
                failures.append(f"A10 실패: 겹친 루트에서 정본 {n} 이 지워지거나 링크로 바뀜")
        if code != 1:
            failures.append(f"A10 실패: 루트 겹침인데 종료 코드 {code} (기대 1)")

    # A8: Windows 물리 복사에 쓰는 제외 규칙이 비밀 파일을 거른다(POSIX 에서도 판정 함수는 같다)
    with tempfile.TemporaryDirectory() as td:
        mod = load_module(make_home(td, []))
        for secret in (".env", ".env.local", "secrets.yaml"):
            if not mod.is_excluded(secret, False):
                failures.append(f"A8 실패: 비밀 파일 {secret} 이 복사 제외 대상이 아님")
        if mod.is_excluded("config.yaml", False):
            failures.append("A8 실패: 일반 파일 config.yaml 이 제외됨")

    # A11: 정본과 같아 보여도 agy 쪽에만 제외 대상 파일(.env·.git·credentials)이 있으면 교체하지 않는다
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, ["a"])
        mod = load_module(home)
        dst = mod.AGY_ROOT / "a"
        (dst / ".git").mkdir(parents=True)
        (dst / "SKILL.md").write_text(SKILL_MD.format(name="a"), encoding="utf-8")
        (dst / ".env").write_text("KEY=x\n", encoding="utf-8")
        (dst / ".git" / "ORIG").write_text("x\n", encoding="utf-8")
        code = run_main(mod)
        if dst.is_symlink() or not (dst / ".env").exists():
            failures.append("A11 실패: agy 쪽에만 있는 .env·.git 이 교체로 지워짐")
        if code != 2:
            failures.append(f"A11 실패: 종료 코드 {code} (기대 2)")

    # A12: 정본 링크가 agy 루트 안 실제 폴더를 가리키고 allowlist 밖이면 --force 여도 지우지 않는다
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, ["a"])
        mod = load_module(home)
        real = mod.AGY_ROOT / "x"
        real.mkdir()
        (real / "SKILL.md").write_text(SKILL_MD.format(name="x"), encoding="utf-8")
        (mod.CANONICAL_ROOT / "x").symlink_to(real, target_is_directory=True)
        code = run_main(mod, "--force")
        if not (real / "SKILL.md").exists():
            failures.append("A12 실패: --force 정리가 agy 루트 안의 정본 실체를 지움")
        if code != 2:
            failures.append(f"A12 실패: 종료 코드 {code} (기대 2)")

    # A13: 상위 경로(~/.gemini/config)가 링크여서 agy 루트가 정본 실체들이 있는 곳이 돼도 --force 여도 지우지 않는다
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, [])
        mod = load_module(home)
        other = home / ".agents" / "skills"
        for n in ("kx", "ky"):
            (other / n).mkdir(parents=True)
            (other / n / "SKILL.md").write_text(SKILL_MD.format(name=n), encoding="utf-8")
            mod.CANONICAL_ROOT.mkdir(parents=True, exist_ok=True)
            (mod.CANONICAL_ROOT / n).symlink_to(other / n, target_is_directory=True)
        (home / ".gemini" / "agy-skills.txt").write_text("kx\n", encoding="utf-8")
        mod.AGY_ROOT.rmdir()
        (home / ".gemini" / "config").rmdir()
        (home / ".gemini" / "config").symlink_to(home / ".agents", target_is_directory=True)
        code = run_main(mod, "--force")
        for n in ("kx", "ky"):
            if (other / n).is_symlink() or not (other / n / "SKILL.md").exists():
                failures.append(f"A13 실패: 상위 경로 링크에서 정본 {n} 이 지워지거나 링크로 바뀜")
        if code != 1:
            failures.append(f"A13 실패: agy 루트 상위 경로가 링크인데 종료 코드 {code} (기대 1)")

    # A14: 대소문자만 다른 경로로 건 정본 링크(대소문자 무시 파일시스템)도 정본으로 알아본다
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, ["x"])
        mod = load_module(home)
        upper = Path(str(mod.AGY_ROOT).replace("/.gemini/", "/.GEMINI/"))
        if upper.exists():  # 대소문자 무시 파일시스템에서만 의미가 있다
            real = mod.AGY_ROOT / "x"
            real.mkdir()
            (real / "SKILL.md").write_text(SKILL_MD.format(name="x"), encoding="utf-8")
            import shutil as _sh
            _sh.rmtree(mod.CANONICAL_ROOT / "x")
            (mod.CANONICAL_ROOT / "x").symlink_to(upper / "x", target_is_directory=True)
            run_main(mod)
            if real.is_symlink() or not (real / "SKILL.md").exists():
                failures.append("A14 실패: 대소문자 변형 링크의 정본 실체가 지워지거나 자기 링크로 바뀜")

    # A15: 이름 없는 --force 는 allowlist 밖 실제 폴더(정본 실체가 아닌 것)를 정리한다(문서화된 동작)
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, ["a"])
        mod = load_module(home)
        native = mod.AGY_ROOT / "native"
        native.mkdir()
        (native / "SKILL.md").write_text(SKILL_MD.format(name="native"), encoding="utf-8")
        code = run_main(mod, "--force")
        if native.exists():
            failures.append("A15 실패: --force 인데 allowlist 밖 실제 폴더가 정리되지 않음")
        if code != 0:
            failures.append(f"A15 실패: 종료 코드 {code} (기대 0)")

    # A16: Windows 분기(물리 복사)도 정본 실체는 --force 여도 지우지 않는다
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, ["a"])
        mod = load_module(home)
        mod.IS_WINDOWS = True
        real = mod.AGY_ROOT / "x"
        real.mkdir()
        (real / "SKILL.md").write_text(SKILL_MD.format(name="x"), encoding="utf-8")
        (mod.CANONICAL_ROOT / "x").symlink_to(real, target_is_directory=True)
        (home / ".gemini" / "agy-skills.txt").write_text("a\nx\n", encoding="utf-8")
        run_main(mod, "--force")
        if real.is_symlink() or not (real / "SKILL.md").exists():
            failures.append("A16 실패: Windows 분기에서 정본 실체가 지워지거나 바뀜")

    # A17: Windows 분기의 물리 복사는 .env·secrets/ 를 복사하지 않는다
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, ["a"])
        mod = load_module(home)
        mod.IS_WINDOWS = True
        src = mod.CANONICAL_ROOT / "a"
        (src / "secrets").mkdir()
        (src / ".env").write_text("KEY=x\n", encoding="utf-8")
        (src / ".ENV.local").write_text("KEY=x\n", encoding="utf-8")
        (src / "secrets" / "k.json").write_text("{}\n", encoding="utf-8")
        code = run_main(mod)
        dst = mod.AGY_ROOT / "a"
        if not (dst / "SKILL.md").exists():
            failures.append("A17 실패: Windows 분기 복사가 되지 않음")
        if (dst / ".env").exists() or (dst / ".ENV.local").exists() or (dst / "secrets").exists():
            failures.append("A17 실패: Windows 분기 복사에 .env·secrets/ 가 들어감")
        if code != 0:
            failures.append(f"A17 실패: 종료 코드 {code} (기대 0)")

    # A18: 지우려는 폴더 "안쪽"에 다른 정본 실체가 있으면(조상 방향) --force 여도 지우지 않는다(두 분기)
    for windows in (False, True):
        with tempfile.TemporaryDirectory() as td:
            home = make_home(td, ["a"])
            mod = load_module(home)
            mod.IS_WINDOWS = windows
            outer = mod.AGY_ROOT / "a"
            inner = outer / "inner"
            inner.mkdir(parents=True)
            (inner / "SKILL.md").write_text(SKILL_MD.format(name="z"), encoding="utf-8")
            (mod.CANONICAL_ROOT / "z").symlink_to(inner, target_is_directory=True)
            run_main(mod, "--force")
            if not (inner / "SKILL.md").exists():
                failures.append(f"A18 실패(windows={windows}): 정본 실체를 품은 폴더가 --force 로 지워짐")

    # A19: 상위 경로 링크로 agy 루트가 다른 도구의 스킬 링크 자리가 돼도 그 링크를 지우지 않고 종료 1
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, ["a"])
        mod = load_module(home)
        projects = home / "Mac-Projects"
        other = home / ".agents" / "skills"
        other.mkdir(parents=True)
        for n in ("b", "c"):
            (projects / n).mkdir(parents=True)
            (projects / n / "SKILL.md").write_text(SKILL_MD.format(name=n), encoding="utf-8")
            (other / n).symlink_to(projects / n, target_is_directory=True)
        mod.AGY_ROOT.rmdir()
        (home / ".gemini" / "config").rmdir()
        (home / ".gemini" / "config").symlink_to(home / ".agents", target_is_directory=True)
        code = run_main(mod)
        for n in ("b", "c"):
            if not (other / n).is_symlink():
                failures.append(f"A19 실패: 다른 도구의 스킬 링크 {n} 가 지워짐")
        if code != 1:
            failures.append(f"A19 실패: 종료 코드 {code} (기대 1)")

    # A20: .envrc·확장자 없는 secrets 도 복사 제외
    with tempfile.TemporaryDirectory() as td:
        mod = load_module(make_home(td, []))
        for name in (".envrc", "secrets"):
            if not mod.is_excluded(name, False):
                failures.append(f"A20 실패: {name} 이 복사 제외 대상이 아님")

    # A21: agy 쪽 실제 폴더에 끊어진 symlink 가 있어도 죽지 않고 건너뛰며 다른 스킬은 반영한다
    with tempfile.TemporaryDirectory() as td:
        home = make_home(td, ["a", "b"])
        mod = load_module(home)
        dst = mod.AGY_ROOT / "a"
        (dst / ".venv" / "bin").mkdir(parents=True)
        (dst / "SKILL.md").write_text(SKILL_MD.format(name="a"), encoding="utf-8")
        (dst / ".venv" / "bin" / "python").symlink_to(home / "없는-파이썬")
        try:
            code = run_main(mod)
        except OSError as e:
            code = None
            failures.append(f"A21 실패: 끊어진 링크에서 예외로 멈춤: {e}")
        if code is not None:
            if not (mod.AGY_ROOT / "b").is_symlink():
                failures.append("A21 실패: 다른 스킬 b 가 반영되지 않음")
            if not (dst / "SKILL.md").exists() or dst.is_symlink():
                failures.append("A21 실패: 끊어진 링크가 든 실제 폴더가 교체됨")
            if code != 2:
                failures.append(f"A21 실패: 종료 코드 {code} (기대 2)")

    if failures:
        print("\n".join(failures))
        return 1
    print("모든 테스트 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
