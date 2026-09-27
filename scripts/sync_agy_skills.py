#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_agy_skills.py — 사용자 레벨 스킬을 Antigravity CLI(agy) 글로벌 루트로 반영

sync_agent_docs.py 가 "프로젝트 레벨"(CLAUDE.md → AGENTS.md, .claude/skills → .agents/skills)을
담당한다면, 이 스크립트는 "사용자 레벨"을 담당한다. 대상은 Antigravity CLI 하나뿐이다.

    ~/.claude/skills/<name>   (정본. junction/symlink 면 실체까지 해석)
        → ~/.gemini/config/skills/<name>

요지(배경·근거는 스킬의 references/agy.md):
- agy 의 글로벌 스킬 루트는 ~/.gemini/config/skills 다(~/.agents/skills 는 agy 에게 워크스페이스 루트).
- Windows 의 agy 는 junction 을 따라가지 않아 물리 복사하고, macOS 는 symlink 를 건다.
- 정본 경로는 ~/.claude/skills/<name> 을 realpath 로 해석해 머신별 하드코딩을 피한다.
- 노출할 스킬은 allowlist(~/.gemini/agy-skills.txt)로 고른다. 없으면 --init 로 템플릿을 만든다.
- 드리프트 가드(Windows): 마지막 동기화 해시(~/.gemini/agy-sync-manifest.json)와 3자 비교해
  agy 쪽 복사본이 수정됐으면 덮어쓰지도 삭제하지도 않고 건너뛴다(--force 로 무시).
- 실제 폴더 보호(macOS): agy 루트의 실제 폴더는 정본과 같을 때만 링크로 바꾸고, 다르거나
  allowlist 밖이면 지우지 않고 건너뛴다(--force 로 무시).
- 정본 실체 보호: 지우거나 바꾸려는 agy 루트 안 실제 폴더가 ~/.claude/skills 의 어느 항목의
  실체와 같거나 그 조상·자손이면(파일 동일성으로 판정) --force 여도 건드리지 않는다.
- agy 루트나 그 상위 경로(~/.gemini, ~/.gemini/config)가 링크이거나 정본 루트와 겹치면 아무것도 하지 않고 종료 1.

사용법:
    python <agent-docs-sync 스킬>/scripts/sync_agy_skills.py             # 동기화
    python <agent-docs-sync 스킬>/scripts/sync_agy_skills.py --check     # 드라이런: 무엇이 바뀔지만 출력
    python <agent-docs-sync 스킬>/scripts/sync_agy_skills.py --force [스킬 ...]   # 드리프트 복사본을 정본으로 덮어씀(이름 없으면 전부)
    python <agent-docs-sync 스킬>/scripts/sync_agy_skills.py --init      # allowlist 템플릿 생성(현재 스킬 전부를 주석 처리해서)
    python <agent-docs-sync 스킬>/scripts/sync_agy_skills.py --list <경로>   # 다른 allowlist 파일 사용

종료 코드 (sync_agent_docs.py 와 같은 규약):
  0  전부 최신이거나 정상 반영됨(경고 없음)
  2  frontmatter 검증 경고, 목록에 있으나 정본이 없는 스킬, 또는 드리프트·실제 폴더로 건너뛴
     스킬 — 나머지는 정상 반영됨. 실패가 아니라 "확인 필요" 신호.
  1  기타 오류(allowlist 부재, agy 루트 경로에 링크가 있거나 정본 루트와 겹침 등)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

# Windows 콘솔(cp949 등)에서 한글 출력이 깨지지 않도록 UTF-8 로 재설정.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HOME = Path.home()
CANONICAL_ROOT = HOME / ".claude" / "skills"
AGY_ROOT = HOME / ".gemini" / "config" / "skills"
DEFAULT_LIST = HOME / ".gemini" / "agy-skills.txt"
MANIFEST_PATH = HOME / ".gemini" / "agy-sync-manifest.json"

IS_WINDOWS = os.name == "nt"

# sync_agent_docs.py 의 SKILL_EXCLUDE_* 와 같은 취지의 정책(자격증명·캐시·OS 잡파일 제외, 여기는 venv 도 제외).
EXCLUDE_DIRS = {"credentials", "secrets", "__pycache__", ".git", ".idea", "node_modules", ".venv", "venv"}
EXCLUDE_FILES = {"desktop.ini", ".DS_Store", "accounts.json", ".envrc", "secrets"}
EXCLUDE_GLOBS = (
    "*.pyc", "*.pyo",
    "*token*.json", "client_secret*.json", "*.token", "*.key", "*.pem",
    ".env", ".env.*", "secrets.*",
)

LIST_HEADER = """\
# Antigravity CLI(agy) 에 노출할 스킬 목록.
#
# 한 줄에 스킬 이름 하나. '#' 이후는 주석. 이름은 ~/.claude/skills/<name> 을 가리킨다.
# 반영: python <agent-docs-sync 스킬>/scripts/sync_agy_skills.py
#
# 여기 없는 스킬은 agy 글로벌 루트에서 제거된다(실제 폴더·정본 실체는 건너뛴다. 정본은 건드리지 않음).
"""


def is_excluded(name: str, is_dir: bool) -> bool:
    if is_dir:
        return name in EXCLUDE_DIRS
    if name in EXCLUDE_FILES:
        return True
    from fnmatch import fnmatch
    low = name.lower()  # .ENV·Secrets.yaml 도 제외
    return any(fnmatch(low, g) for g in EXCLUDE_GLOBS)


def copy_filter(src_dir: str, names: list[str]) -> set[str]:
    """shutil.copytree 의 ignore 콜백."""
    ignored = set()
    for n in names:
        full = Path(src_dir) / n
        if is_excluded(n, full.is_dir()):
            ignored.add(n)
    return ignored


def is_link_dir(p: Path) -> bool:
    """symlink 또는 Windows junction 인가. junction 판정(is_junction)은 3.12+.

    junction 을 물리 폴더로 오인하면 hash_tree 가 타깃(정본)을 뚫고 해시해
    "이미 최신"으로 오판하고, agy 는 여전히 스킬을 못 보는 침묵 실패가 된다.
    """
    return p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())


def same_or_inside(path: Path, base: Path) -> bool:
    """path 의 실체가 base 의 실체와 같거나 그 안에 있는가. 경로 문자열이 아니라 파일 동일성
    (st_dev·st_ino)으로 비교해 대소문자만 다른 링크(대소문자 무시 파일시스템)도 잡는다."""
    try:
        b = os.stat(base)
    except OSError:
        return False
    real = Path(os.path.realpath(path))
    if b.st_ino == 0:  # 파일 식별자를 주지 않는 파일시스템: 경로 문자열로 대신한다
        base_real = os.path.normcase(os.path.realpath(base))
        try:
            return os.path.commonpath([os.path.normcase(str(real)), base_real]) == base_real
        except ValueError:
            return False
    for q in (real, *real.parents):
        try:
            s = os.stat(q)
        except OSError:
            continue
        if (s.st_dev, s.st_ino) == (b.st_dev, b.st_ino):
            return True
    return False


def _file_id(p: Path) -> tuple[int, int] | None:
    try:
        s = os.stat(p)
    except OSError:
        return None
    return (s.st_dev, s.st_ino)


def canonical_entities() -> tuple[set, set]:
    """지우기 전 보호 대상: ~/.claude/skills 루트와 모든 항목(allowlist 와 무관)의 실체.
    (실체들의 파일 식별자 집합, 그 조상들의 식별자 집합) 을 한 번만 계산해 돌려준다."""
    exact: set = set()
    ancestors: set = set()
    for c in [CANONICAL_ROOT, *CANONICAL_ROOT.iterdir()]:
        real = Path(os.path.realpath(c))
        fid = _file_id(real)
        if fid is None:
            continue
        exact.add(fid)
        for q in real.parents:
            qid = _file_id(q)
            if qid is not None:
                ancestors.add(qid)
    return exact, ancestors


def touches_canonical(p: Path, protected: tuple[set, set]) -> bool:
    """p(agy 루트 안 실제 폴더)를 지우면 정본이 사라지는가: 정본 실체와 같거나 그 조상·자손.
    식별자를 주지 않는 파일시스템(st_ino 0)이면 판정할 수 없으므로 보호 쪽으로 본다."""
    exact, ancestors = protected
    real = Path(os.path.realpath(p))
    fid = _file_id(real)
    if fid is None or fid[1] == 0 or fid in ancestors:
        return True
    return any(_file_id(q) in exact for q in (real, *real.parents))


def hash_tree(root: Path, apply_excludes: bool = True) -> dict[str, str]:
    """{상대경로: sha256} 를 만든다. 기본은 제외 규칙 적용(복사되는 파일 집합과 동일).
    apply_excludes=False 면 .git·.env 등 제외 대상까지 전부 센다(지워도 되는지 판정할 때)."""
    hashes: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        if apply_excludes:
            dirnames[:] = [d for d in dirnames if not is_excluded(d, True)]
        else:
            # 전부 셀 때 링크는 따라가지 않고 가리키는 곳을 센다(끊어진 링크에서 죽지 않게).
            for name in dirnames + filenames:
                full = Path(dirpath) / name
                if full.is_symlink():
                    hashes[full.relative_to(root).as_posix()] = "link:" + os.readlink(full)
            dirnames[:] = [d for d in dirnames if not (Path(dirpath) / d).is_symlink()]
        for fn in sorted(filenames):
            if apply_excludes and is_excluded(fn, False):
                continue
            full = Path(dirpath) / fn
            if not apply_excludes and full.is_symlink():
                continue
            digest = hashlib.sha256()
            with open(full, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    digest.update(chunk)
            hashes[full.relative_to(root).as_posix()] = digest.hexdigest()
    return hashes


def describe_diff(baseline: dict[str, str], current: dict[str, str], limit: int = 5) -> str:
    """두 해시 맵의 차이를 사람이 읽을 파일 목록으로 요약한다."""
    changed = sorted(
        k for k in baseline.keys() | current.keys()
        if baseline.get(k) != current.get(k)
    )
    head = ", ".join(changed[:limit])
    return head + (f" 외 {len(changed) - limit}개" if len(changed) > limit else "")


def load_manifest() -> dict[str, dict[str, str]]:
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    # 손상·수동 편집된 항목은 "기록 없음"(판정 불가) 취급이 안전하다.
    return {k: v for k, v in data.items() if isinstance(v, dict)}


def save_manifest(manifest: dict[str, dict[str, str]]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=1),
        encoding="utf-8",
    )


def read_frontmatter(skill_md: Path) -> tuple[dict | None, str | None]:
    """SKILL.md frontmatter 를 파싱해 (dict, 오류메시지) 를 반환."""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return None, f"읽기 실패: {exc}"

    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, "frontmatter 구분자(---)가 없음"

    try:
        import yaml
    except ImportError:
        # PyYAML 이 없으면 가장 흔한 함정만 휴리스틱으로 잡는다.
        for line in parts[1].splitlines():
            if line.startswith("description:"):
                value = line[len("description:"):].strip()
                if value and value[0] not in "\"'>|" and ": " in value:
                    return None, "description plain scalar 에 ': '(콜론+공백) — 엄격한 파서에서 파싱 실패"
        return {}, None

    try:
        data = yaml.safe_load(parts[1])
    except Exception as exc:  # yaml.YAMLError 포함
        first = str(exc).splitlines()[0]
        return None, f"YAML 파싱 실패: {first}"

    if not isinstance(data, dict):
        return None, "frontmatter 가 매핑이 아님"
    return data, None


def validate(name: str, src: Path) -> str | None:
    """정본 스킬 하나를 검증해 경고 문자열(없으면 None)을 반환."""
    skill_md = src / "SKILL.md"
    if not skill_md.is_file():
        return "SKILL.md 없음"

    data, err = read_frontmatter(skill_md)
    if err:
        # 이게 걸리면 agy 는 스킬을 통째로 드롭한다.
        # Claude Code 는 폴백해서 description 자리에 이름만 노출하므로 조용히 깨진다.
        return err
    if data and not data.get("description"):
        return "description 이 비어 있음"
    if data and data.get("name") and str(data["name"]).strip().strip('"\'') != name:
        return f"frontmatter name({data['name']}) 이 폴더명과 다름"
    return None


def materialize_windows(
    name: str,
    src: Path,
    dst: Path,
    manifest: dict[str, dict[str, str]],
    check: bool,
    force: bool,
    protected: list[Path],
) -> tuple[str, str | None]:
    """정본을 물리 복사로 반영한다. (동작 문자열, 드리프트 사유|None) 를 반환.

    agy 가 junction 을 따라가지 않으므로 복사만 유효한데, 복사는 rmtree 로 시작해
    agy 쪽 복사본에 가해진 수정을 지운다. manifest(마지막 동기화 해시)와 3자 비교해
    복사본이 수정됐으면 덮어쓰지 않고 건너뛴다(--force 로 무시).
    """
    dst_is_link = is_link_dir(dst)
    if dst.is_dir() and not dst_is_link and touches_canonical(dst, protected):
        return ("정본 실체(건너뜀)", f"agy 루트의 {dst.name} 이(가) 정본 실체라 건드리지 않음")
    src_hashes = hash_tree(src)
    baseline = manifest.get(name)
    dst_hashes = hash_tree(dst) if dst.is_dir() and not dst_is_link else None

    if dst_hashes is not None and dst_hashes == src_hashes:
        # 복사본 == 정본이면 잃을 것이 없다 — 드리프트 검사보다 먼저 재베이스라인한다.
        # (드리프트를 정본에 반영한 뒤의 재실행이 이 분기로 조용히 해소된다.
        #  check 모드에선 manifest 를 저장하지 않으므로 이 대입은 무해하다.)
        manifest[name] = src_hashes
        return ("이미 최신", None)

    if dst_hashes is not None and not force:
        if baseline is not None and dst_hashes != baseline:
            return (
                "드리프트(건너뜀)",
                f"agy 복사본이 마지막 동기화 이후 수정됨: {describe_diff(baseline, dst_hashes)}",
            )
        if baseline is None:
            return (
                "드리프트?(건너뜀)",
                f"동기화 기록이 없고 복사본이 정본과 다름: {describe_diff(src_hashes, dst_hashes)}",
            )

    if check:
        return ("복사(예정)" if dst_hashes is None else "재복사(예정)", None)

    if dst.is_symlink():
        dst.unlink()
    elif dst_is_link:
        os.rmdir(dst)  # junction: 링크 엔트리만 제거(타깃 무손상)
    elif dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst, ignore=copy_filter, symlinks=False)
    manifest[name] = hash_tree(dst)
    return ("복사", None)


def materialize_posix(
    src: Path, dst: Path, check: bool, force: bool, protected: list[Path],
) -> tuple[str, str | None]:
    """POSIX: agy 가 symlink 를 따라가므로 링크로 충분하다. (동작 문자열, 건너뛴 사유|None) 를 반환.

    agy 루트에 이미 실제 폴더(agy 에 직접 설치했거나 손으로 만든 스킬)가 있으면, 정본과
    내용이 같을 때만(.git·.env 등 제외 대상까지 전부 비교) 링크로 바꾸고 다르면 지우지 않고
    건너뛴다(--force 로 무시). 그 폴더가 정본 실체면 --force 여도 건드리지 않는다.
    """
    if dst.is_symlink() and Path(os.readlink(dst)) == src:
        return ("이미 최신", None)
    real_dir = dst.is_dir() and not dst.is_symlink()
    if real_dir and touches_canonical(dst, protected):
        return ("정본 실체(건너뜀)", f"agy 루트의 {dst.name} 이(가) 정본 실체라 건드리지 않음")
    if real_dir and not force:
        try:
            src_all, dst_all = hash_tree(src, False), hash_tree(dst, False)
        except OSError as exc:
            return ("실제 폴더(건너뜀)", f"agy 루트의 실제 폴더를 비교하지 못함({exc})")
        if src_all != dst_all:
            return (
                "실제 폴더(건너뜀)",
                f"agy 루트에 정본과 다른 실제 폴더가 있음: {describe_diff(src_all, dst_all)}",
            )
    if check:
        return ("symlink(예정)", None)
    if real_dir:
        shutil.rmtree(dst, ignore_errors=True)
    elif dst.is_symlink() or dst.exists():
        dst.unlink()
    dst.symlink_to(src, target_is_directory=True)
    return ("symlink", None)


def load_list(path: Path) -> list[str]:
    names: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            names.append(line)
    return names


def write_template(path: Path) -> None:
    entries = sorted(
        d.name for d in CANONICAL_ROOT.iterdir()
        if d.is_dir() and (d / "SKILL.md").is_file()
    )
    body = LIST_HEADER + "\n" + "\n".join(f"# {n}" for n in entries) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    print(f"allowlist 템플릿 생성: {path}")
    print(f"  스킬 {len(entries)}개를 주석 처리해 넣었다. 노출할 것만 '#' 을 지우고 다시 실행하라.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="~/.claude/skills → Antigravity CLI(agy) 글로벌 스킬 루트 반영"
    )
    parser.add_argument("--check", action="store_true", help="드라이런: 변경 사항만 출력하고 쓰지 않음")
    parser.add_argument(
        "--force", nargs="*", metavar="스킬",
        help="드리프트가 감지된 복사본도 정본으로 덮어씀. 스킬 이름을 주면 그 스킬만, 이름 없이 쓰면 전부",
    )
    parser.add_argument("--init", action="store_true", help="allowlist 템플릿을 만들고 종료")
    parser.add_argument("--list", type=Path, default=DEFAULT_LIST, help=f"allowlist 파일 (기본: {DEFAULT_LIST})")
    args = parser.parse_args()

    if not CANONICAL_ROOT.is_dir():
        print(f"오류: 정본 스킬 폴더가 없다: {CANONICAL_ROOT}", file=sys.stderr)
        return 1

    if args.init:
        write_template(args.list)
        return 0

    if not args.list.is_file():
        print(f"오류: allowlist 가 없다: {args.list}", file=sys.stderr)
        print(f"  'python {Path(__file__).resolve()} --init' 로 템플릿을 만들어라.", file=sys.stderr)
        return 1

    names = load_list(args.list)
    if not names:
        print(f"오류: allowlist 가 비어 있다: {args.list}", file=sys.stderr)
        return 1

    # agy 루트나 그 상위 경로(~/.gemini, ~/.gemini/config)가 링크면 가리키는 곳(정본이나
    # 다른 도구의 스킬 자리일 수 있다)을 정리·교체 대상으로 보게 된다.
    for q in (AGY_ROOT.parent.parent, AGY_ROOT.parent, AGY_ROOT):
        if is_link_dir(q):
            print(f"오류: agy 루트 경로의 {q} 가 링크다 → {os.path.realpath(q)}", file=sys.stderr)
            print("  링크 자체만 지우고(대상은 건드리지 말 것) 실제 폴더로 다시 만든 뒤 실행하라:", file=sys.stderr)
            print(f"    macOS: rm \"{q}\"   (끝 슬래시·-r 없이)", file=sys.stderr)
            print(f"    Windows: rmdir \"{q}\"   (/s 없이)", file=sys.stderr)
            return 1

    # agy 루트와 정본 루트가 겹치면(한쪽이 다른 쪽을 가리키는 링크 등) 정리·교체가 정본을 지운다.
    if AGY_ROOT.exists() and (
        same_or_inside(AGY_ROOT, CANONICAL_ROOT) or same_or_inside(CANONICAL_ROOT, AGY_ROOT)
    ):
        print(
            f"오류: agy 루트({AGY_ROOT} → {os.path.realpath(AGY_ROOT)})와 정본 루트"
            f"({CANONICAL_ROOT} → {os.path.realpath(CANONICAL_ROOT)})가 겹친다.",
            file=sys.stderr,
        )
        print("  둘 중 링크인 쪽을 찾아 그 링크 자체만 지우고, 두 폴더를 따로 둔 뒤 실행하라.", file=sys.stderr)
        return 1

    protected = canonical_entities()

    if not args.check:
        AGY_ROOT.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest() if IS_WINDOWS else {}
    force_all = args.force is not None and not args.force
    force_names = set(args.force or [])
    warnings: list[str] = []
    skipped: list[str] = []
    done = 0

    for name in names:
        link = CANONICAL_ROOT / name
        if not link.exists():
            warnings.append(f"{name}: 정본 없음 ({link})")
            continue

        # junction(Windows)·symlink(macOS) 어느 쪽이든 실체까지 해석한다.
        src = link.resolve()
        warn = validate(name, src)
        if warn:
            warnings.append(f"{name}: {warn}")

        if IS_WINDOWS:
            try:
                action, drift = materialize_windows(
                    name, src, AGY_ROOT / name, manifest,
                    args.check, force_all or name in force_names, protected,
                )
            except OSError as exc:
                # 잠긴 파일·부분 삭제 등으로 한 스킬이 실패해도 나머지 반영과
                # manifest 저장은 계속한다. 실패 스킬은 다음 실행에서 드리프트로
                # 잡히며 --force <이름> 으로 복구한다.
                skipped.append(f"{name}: 반영 실패({exc})")
                print(f"  {name:30} {'오류(건너뜀)':14} <- {src}")
                continue
            if drift:
                skipped.append(f"{name}: {drift}")
            else:
                done += 1
        else:
            action, drift = materialize_posix(
                src, AGY_ROOT / name, args.check, force_all or name in force_names, protected,
            )
            if drift:
                skipped.append(f"{name}: {drift}")
            else:
                done += 1
        print(f"  {name:30} {action:14} <- {src}")

    # allowlist 에서 빠진 항목은 agy 루트에서 정리한다(정본은 건드리지 않는다).
    wanted = set(names)
    removed = []
    if AGY_ROOT.is_dir():
        for entry in AGY_ROOT.iterdir():
            if entry.name in wanted:
                continue
            if entry.is_dir() and not is_link_dir(entry) and touches_canonical(entry, protected):
                skipped.append(f"{entry.name}: allowlist 밖이지만 정본 실체라 지우지 않음")
                continue
            # 삭제도 덮어쓰기와 같은 데이터 손실 경로다: Windows 물리 폴더는
            # 삭제 전에 드리프트 검사를 거친다(링크·파일 엔트리는 데이터가 없다).
            if (
                IS_WINDOWS
                and entry.is_dir()
                and not is_link_dir(entry)
                and not (force_all or entry.name in force_names)
            ):
                baseline = manifest.get(entry.name)
                try:
                    current = hash_tree(entry)
                except OSError as exc:
                    skipped.append(f"{entry.name}: 정리 전 해시 실패({exc}) — 삭제하지 않음")
                    continue
                if baseline is None or current != baseline:
                    reason = (
                        "동기화 기록과 다름" if baseline is not None
                        else "기록이 없어 수정 여부 판정 불가"
                    )
                    skipped.append(
                        f"{entry.name}: allowlist 에서 빠졌지만 복사본이 {reason} — 삭제하지 않음"
                    )
                    continue
            if (
                not IS_WINDOWS
                and entry.is_dir()
                and not entry.is_symlink()
                and not (force_all or entry.name in force_names)
            ):
                skipped.append(
                    f"{entry.name}: allowlist 에서 빠진 실제 폴더(직접 설치·수정한 스킬일 수 있음) — 삭제하지 않음"
                )
                continue
            removed.append(entry.name)
            if not args.check:
                if entry.is_symlink() or entry.is_file():
                    entry.unlink()
                elif is_link_dir(entry):
                    os.rmdir(entry)
                else:
                    shutil.rmtree(entry, ignore_errors=True)

    if IS_WINDOWS and not args.check:
        # allowlist 에서 빠졌고 복사본도 이미 없는 항목의 기록은 정리한다.
        # (드리프트로 삭제를 보류한 항목은 복사본이 남아 있으므로 기록도 유지된다.)
        for stale in [k for k in manifest if k not in wanted and not (AGY_ROOT / k).exists()]:
            del manifest[stale]
        save_manifest(manifest)

    mode = "symlink" if not IS_WINDOWS else "물리 복사"
    print()
    print(f"반영: {done} / {len(names)}  (방식: {mode}, 대상: {AGY_ROOT})")
    if removed:
        print(f"정리{'(예정)' if args.check else ''}: {', '.join(sorted(removed))}")
    if skipped:
        print("건너뜀(반영·삭제 안 됨):")
        for s in skipped:
            print(f"  - {s}")
        print("  (agy 쪽 수정을 정본에 반영한 뒤 재실행하면 자동 해소되고,")
        print("   폐기해도 되면 --force <스킬명> 으로 그 스킬만 덮어써라.)")
        if any("정본 실체" in s for s in skipped):
            print("  ('정본 실체' 항목은 --force 로도 풀리지 않는다. 정본을 agy 루트 밖으로 옮겨라.)")
    if warnings:
        print("경고:")
        for w in warnings:
            print(f"  - {w}")
        print("  (frontmatter 가 깨진 스킬은 agy 목록에서 통째로 사라진다.")
        print("   description 값에 ': ' 가 있으면 'description: >-' 블록 스칼라로 감싸라.)")
    return 2 if (warnings or skipped) else 0


if __name__ == "__main__":
    sys.exit(main())
