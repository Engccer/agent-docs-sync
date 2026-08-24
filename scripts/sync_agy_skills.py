#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_agy_skills.py — 사용자 레벨 스킬을 Antigravity CLI(agy) 글로벌 루트로 반영

sync_agent_docs.py 가 "프로젝트 레벨"(CLAUDE.md → AGENTS.md, .claude/skills → .agents/skills)을
담당한다면, 이 스크립트는 "사용자 레벨"을 담당한다. 대상은 Antigravity CLI 하나뿐이다.

    ~/.claude/skills/<name>   (정본. junction/symlink 면 실체까지 해석)
        → ~/.gemini/config/skills/<name>

왜 별도 스크립트인가 (2026-08-24 카나리 실측으로 확정된 사실들):

1. **agy 의 글로벌 스킬 루트는 `~/.gemini/config/skills` 다.** `~/.agents/skills` 가 아니다.
   `~/.agents/skills` 는 agy 에게 "워크스페이스 루트"(`<workspace>/.agents/skills`)일 뿐이라,
   작업 디렉터리가 우연히 홈일 때만 걸린다. 여기를 글로벌 루트로 착각하면 스킬을 몇 개를
   넣든 agy 는 0 개를 본다. (agy 바이너리 문자열 + 카나리 A/B 로 확인)

2. **링크 추종이 OS 마다 다르다.**
   - Windows: agy 는 스킬 루트의 **junction 을 따라가지 않는다.** 같은 이름·같은 내용·같은
     자리에서 junction 은 미로드, 실제 폴더는 로드됨(통제 실험). → **물리 복사**해야 한다.
   - macOS: agy 는 **symlink 를 정상적으로 따라간다.** → **symlink** 로 충분하다(사본 없음,
     드리프트 없음).
   같은 이유로 Windows 에서만 정본이 바뀔 때마다 이 스크립트를 다시 돌려야 한다.
   (참고: Codex 는 Windows junction 도 정상 추종한다. agy 만 예외다.)

3. **정본 경로를 머신별로 하드코딩하지 않는다.** `~/.claude/skills/<name>` 을 realpath 로
   해석하면 Windows(junction→`Windows-Projects/...`)든 macOS(symlink→`Mac-Projects/...`)든
   같은 코드로 실체에 도달한다. 머신별 경로 표를 두면 정본이 이사할 때마다 어긋난다.

대상 목록(allowlist)을 쓰는 이유: `~/.claude/skills` 에는 k-skill 번들 등 수십~수백 개가 섞여
있어 전부 넣으면 agy 컨텍스트가 스킬 설명으로 뒤덮인다. 어떤 스킬을 agy 에 노출할지는 사람이
정할 문제라 파일로 분리했다(`~/.gemini/agy-skills.txt`). 없으면 `--init` 로 템플릿을 만든다.

사용법:
    python sync_agy_skills.py             # 동기화
    python sync_agy_skills.py --check     # 드라이런: 무엇이 바뀔지만 출력
    python sync_agy_skills.py --init      # allowlist 템플릿 생성(현재 스킬 전부를 주석 처리해서)
    python sync_agy_skills.py --list <경로>   # 다른 allowlist 파일 사용

종료 코드 (sync_agent_docs.py 와 동일 규약):
  0  전부 최신이거나 정상 반영됨(경고 없음)
  2  frontmatter 검증 경고 또는 목록에 있으나 정본이 없는 스킬 — 나머지는 정상 반영됨.
     실패가 아니라 "확인 필요" 신호.
  1  기타 오류(allowlist 부재 등)
"""

from __future__ import annotations

import argparse
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

IS_WINDOWS = os.name == "nt"

# sync_agent_docs.py 의 SKILL_EXCLUDE_* 와 같은 정책(자격증명·캐시·OS 잡파일 제외).
EXCLUDE_DIRS = {"credentials", "__pycache__", ".git", ".idea", "node_modules", ".venv", "venv"}
EXCLUDE_FILES = {"desktop.ini", ".DS_Store", "accounts.json"}
EXCLUDE_GLOBS = (
    "*.pyc", "*.pyo",
    "*token*.json", "client_secret*.json", "*.token", "*.key", "*.pem",
)

LIST_HEADER = """\
# Antigravity CLI(agy) 에 노출할 스킬 목록.
#
# 한 줄에 스킬 이름 하나. '#' 이후는 주석. 이름은 ~/.claude/skills/<name> 을 가리킨다.
# 반영: python sync_agy_skills.py
#
# 여기 없는 스킬은 agy 글로벌 루트에서 제거된다(정본은 건드리지 않음).
"""


def is_excluded(name: str, is_dir: bool) -> bool:
    if is_dir:
        return name in EXCLUDE_DIRS
    if name in EXCLUDE_FILES:
        return True
    from fnmatch import fnmatch
    return any(fnmatch(name, g) for g in EXCLUDE_GLOBS)


def copy_filter(src_dir: str, names: list[str]) -> set[str]:
    """shutil.copytree 의 ignore 콜백."""
    ignored = set()
    for n in names:
        full = Path(src_dir) / n
        if is_excluded(n, full.is_dir()):
            ignored.add(n)
    return ignored


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


def materialize(name: str, src: Path, dst: Path, check: bool) -> str:
    """정본을 agy 루트에 반영하고 수행한 동작 문자열을 반환."""
    if IS_WINDOWS:
        # agy 가 junction 을 따라가지 않으므로 물리 복사만 유효하다.
        if check:
            return "복사(예정)" if not dst.exists() else "재복사(예정)"
        if dst.exists() or dst.is_symlink():
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst, ignore=copy_filter, symlinks=False)
        return "복사"

    # POSIX: agy 가 symlink 를 따라가므로 링크로 충분하다(사본 없음 → 드리프트 없음).
    if dst.is_symlink() and Path(os.readlink(dst)) == src:
        return "이미 최신"
    if check:
        return "symlink(예정)"
    if dst.is_symlink() or dst.exists():
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst, ignore_errors=True)
        else:
            dst.unlink()
    dst.symlink_to(src, target_is_directory=True)
    return "symlink"


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
        print("  'python sync_agy_skills.py --init' 로 템플릿을 만들어라.", file=sys.stderr)
        return 1

    names = load_list(args.list)
    if not names:
        print(f"오류: allowlist 가 비어 있다: {args.list}", file=sys.stderr)
        return 1

    if not args.check:
        AGY_ROOT.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
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

        action = materialize(name, src, AGY_ROOT / name, args.check)
        done += 1
        print(f"  {name:30} {action:14} <- {src}")

    # allowlist 에서 빠진 항목은 agy 루트에서 정리한다(정본은 건드리지 않는다).
    wanted = set(names)
    removed = []
    if AGY_ROOT.is_dir():
        for entry in AGY_ROOT.iterdir():
            if entry.name in wanted:
                continue
            removed.append(entry.name)
            if not args.check:
                if entry.is_symlink() or entry.is_file():
                    entry.unlink()
                else:
                    shutil.rmtree(entry, ignore_errors=True)

    mode = "symlink" if not IS_WINDOWS else "물리 복사"
    print()
    print(f"반영: {done} / {len(names)}  (방식: {mode}, 대상: {AGY_ROOT})")
    if removed:
        print(f"정리{'(예정)' if args.check else ''}: {', '.join(sorted(removed))}")
    if warnings:
        print("경고:")
        for w in warnings:
            print(f"  - {w}")
        print("  (frontmatter 가 깨진 스킬은 agy 목록에서 통째로 사라진다.")
        print("   description 값에 ': ' 가 있으면 'description: >-' 블록 스칼라로 감싸라.)")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
