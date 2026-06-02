#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_agent_docs.py — 에이전트 지침·스킬 단방향 동기화

정본(canonical) → 생성물(generated):
  1. CLAUDE.md            → AGENTS.md            (루트 및 모든 하위 폴더. Codex·Antigravity 가 네이티브로 읽는 지침 파일)
  2. .claude/skills/      → .agents/skills/      (Codex·Antigravity 가 네이티브로 자동 인식하는 스킬 폴더)

설계 결정 (멀티 에이전트 호환성 작업):
- 단방향만 지원. 역방향 동기화는 하지 않는다.
  (Google Drive 동기화 폴더에서 mtime 신뢰 불가 → 변경 감지·병합이 불가능에 가까움.
   따라서 "정본 → 생성물" 한 방향만, 내용(바이트) 비교로 동작한다.)
- 생성물은 "빌드 산출물"로 취급. 직접 수정하지 않는다.
- AGENTS.md 발산 경고(divergence guard): 직전 동기화 이후 손으로 수정됐으면 mtime 이 아니라
  "내용 해시"로 감지해 경고하고 중단한다(--force 로 강행). 상태는 .agent-docs-sync.json 에 저장.
- 스킬 폴더는 정본을 그대로 미러링한다: 새/변경 파일은 복사, 정본에서 사라진 파일은 생성본에서도 정리.
  단 자격증명·캐시·OS 잡파일은 보안·청결을 위해 제외한다(아래 SKILL_EXCLUDE_*).
  스킬 트리는 파일 수가 많아 개별 발산 경고는 두지 않는다(정본 기준 무조건 미러링).

사용법 (프로젝트 폴더 어디서 실행하든 스크립트 위치 기준으로 동작):
    python sync_agent_docs.py            # 동기화 (AGENTS.md 발산 시 경고 후 중단)
    python sync_agent_docs.py --check    # 드라이런: 무엇이 바뀔지만 출력
    python sync_agent_docs.py --force    # AGENTS.md 발산 경고를 무시하고 강제 덮어쓰기

종료 코드: 0 정상(동기화/최신) · 2 발산 감지로 중단 · 1 기타 오류
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from fnmatch import fnmatch
from pathlib import Path

# Windows 콘솔(cp949 등)에서 한글 출력이 깨지지 않도록 UTF-8 로 재설정.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# ── 설정: 지침 파일 ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
CANONICAL = ROOT / "CLAUDE.md"   # 루트 정본
STATE_FILE = ROOT / ".agent-docs-sync.json"

# 재귀 문서 동기화에서 제외할 디렉터리(스킬 트리·VCS·캐시).
# 루트뿐 아니라 모든 하위 폴더의 CLAUDE.md 마다 형제 AGENTS.md 를 생성하되,
# 아래 폴더 안쪽은 walk 에서 가지치기해 건드리지 않는다.
# (.claude/.agents 안의 CLAUDE.md 는 스킬 트리 소속 → 스킬 동기화가 따로 미러링.)
DOC_EXCLUDE_DIRS = {".claude", ".agents", ".git", "__pycache__", "node_modules", ".venv", ".idea"}

BODY_MARKER = "<!-- SYNC-BODY-START — 이 줄 아래 본문은 CLAUDE.md 와 100% 동일하게 자동 생성됨 -->"

BANNER = (
    "> 🤖 **이 파일은 자동 생성됩니다 — 직접 수정하지 마세요.**\n"
    "> 정본은 `CLAUDE.md` 입니다. 내용을 바꾸려면 `CLAUDE.md` 를 수정한 뒤\n"
    "> 프로젝트 루트에서 `python sync_agent_docs.py` 를 실행하세요.\n"
    "> 이 파일을 직접 고치면 다음 동기화 때 경고와 함께 덮어쓰기 대상이 됩니다.\n"
    "\n"
    f"{BODY_MARKER}\n"
)

# ── 설정: 스킬 폴더 ──────────────────────────────────────────────────────
SKILLS_SRC = ROOT / ".claude" / "skills"
SKILLS_DST = ROOT / ".agents" / "skills"

# 보안: 자격증명 디렉터리/파일은 생성본으로 복제하지 않는다(노출면·회전 부담 2배 방지).
# 청결: 캐시·OS 잡파일도 제외.
SKILL_EXCLUDE_DIRS = {"credentials", "__pycache__", ".git", ".idea", "node_modules", ".venv"}
SKILL_EXCLUDE_FILES = {"desktop.ini", ".DS_Store", "accounts.json"}
SKILL_EXCLUDE_GLOBS = (
    "*.pyc", "*.pyo",
    "*token*.json", "client_secret*.json", "*.token", "*.key", "*.pem",
)
# 고아 정리에서 "무시"할 OS/캐시 잡파일. Google Drive 는 폴더마다 desktop.ini 를 자동
# 생성하므로, 이를 고아로 보고 지우면 Drive 가 다시 만들어 매 실행이 churn 된다 → 그냥 둔다.
# (자격증명은 여기 넣지 않는다. 생성본에 남아 있으면 보안상 지우는 게 맞으므로 고아로 처리.)
SKILL_IGNORE_IN_TARGET_DIRS = {"__pycache__"}
SKILL_IGNORE_IN_TARGET_FILES = {"desktop.ini", ".DS_Store"}
SKILL_IGNORE_IN_TARGET_GLOBS = ("*.pyc", "*.pyo")

# 동기화 스크립트가 생성본 루트에 남기는 안내 파일(고아 정리 대상에서 보호).
SKILLS_README_NAME = "_GENERATED.md"
SKILLS_README = (
    "# (자동 생성) `.agents/skills/`\n"
    "\n"
    "이 폴더는 `.claude/skills/`(Claude Code 정본)에서 `python sync_agent_docs.py` 로 "
    "미러링된 **생성물**입니다. 직접 수정하지 마세요 — 다음 동기화에서 정본 기준으로 덮어쓰입니다.\n"
    "\n"
    "- Codex·Antigravity 가 이 경로(`<repo-root>/.agents/skills/`)를 **네이티브로 자동 인식**합니다.\n"
    "  (둘 다 `agentskills.io` 오픈 표준 = `SKILL.md` + `name`·`description` 프런트매터)\n"
    "- **자격증명**(`credentials/`·`accounts.json` 등)은 보안상 동기화에서 **제외**됩니다.\n"
    "  필요한 스킬은 정본 `.claude/skills/<스킬명>/` 의 자격증명을 참조하세요"
    "(스크립트는 대개 환경변수 override 지원).\n"
    "- 호출 문법: Claude `/스킬`, Codex `$스킬`, Antigravity `@스킬` (자동 활성화는 공통).\n"
)


# ── 공통 유틸 ────────────────────────────────────────────────────────────
def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_text(path: Path) -> str:
    # 개행을 LF 로 정규화해 해시 비교가 OS·드라이브 차이에 흔들리지 않게 한다.
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def extract_body(generated_text: str) -> str:
    """생성물에서 배너를 떼고 본문만 돌려준다. 마커가 없으면 전체를 본문으로 본다."""
    idx = generated_text.find(BODY_MARKER)
    if idx == -1:
        return generated_text
    return generated_text[idx + len(BODY_MARKER):].lstrip("\n")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# ── 지침 파일 동기화 (CLAUDE.md → AGENTS.md, 루트 + 모든 하위 폴더) ─────────
def iter_nested_canonicals() -> list[Path]:
    """루트 CLAUDE.md 를 제외한 하위 폴더의 CLAUDE.md 상대경로 목록.
    스킬 트리(.claude/.agents)·VCS·캐시 폴더는 walk 에서 가지치기한다."""
    found: list[Path] = []
    for dirpath, dirnames, _filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in DOC_EXCLUDE_DIRS]
        if "CLAUDE.md" in _filenames:
            rel = (Path(dirpath) / "CLAUDE.md").relative_to(ROOT)
            if rel.parent == Path("."):
                continue  # 루트는 아래에서 별도 처리
            found.append(rel)
    return sorted(found, key=lambda p: str(p).lower())


def _sync_doc_pair(canonical: Path, target: Path, state_key: str, state: dict, args) -> tuple[bool, bool]:
    """CLAUDE.md 한 개 → 형제 AGENTS.md 한 개 동기화. 반환: (diverged, written)."""
    source = read_text(canonical)
    source_hash = sha256(source)
    generated = BANNER + source
    prev_hash = state.get(state_key)  # 직전 동기화 시 정본 본문 해시

    if not target.exists():
        print(f"[생성] {state_key} 신규 생성")
        if not args.check:
            target.parent.mkdir(parents=True, exist_ok=True)
            write_text(target, generated)
            state[state_key] = source_hash
            return False, True
        return False, False

    existing = read_text(target)
    existing_body_hash = sha256(extract_body(existing))

    # 이미 최신이면 건너뜀.
    if existing_body_hash == source_hash and prev_hash == source_hash:
        print(f"[최신] {state_key} 변경 없음")
        return False, False

    # 발산 감지: 본문이 "직전 동기화 시 정본"과 다르면 = 손으로 수정됨(또는 관리 밖에서 생성).
    untouched = (prev_hash is not None and existing_body_hash == prev_hash)
    # 상태 파일이 없을 때의 보수적 판단: 현재 정본과 같으면 손댄 적 없는 것으로 간주.
    if prev_hash is None and existing_body_hash == source_hash:
        untouched = True

    if not untouched and not args.force:
        rel_src = canonical.relative_to(ROOT)
        print(
            f"[발산 경고] {state_key} 이(가) 직전 동기화 이후 직접 수정됐거나, "
            f"동기화 관리 밖에서 만들어진 것으로 보입니다.\n"
            f"            정본({rel_src})에서 생성한 내용과 본문이 다릅니다.\n"
            f"            이 파일은 생성물이므로 수정 내용을 정본으로 옮긴 뒤 다시 실행하거나,\n"
            f"            수정을 버려도 된다면 --force 로 강제 덮어쓰기 하세요.",
            file=sys.stderr,
        )
        return True, False

    action = "강제 덮어쓰기" if (not untouched and args.force) else "갱신"
    print(f"[{action}] {state_key} ← {canonical.relative_to(ROOT)}")
    if not args.check:
        write_text(target, generated)
        state[state_key] = source_hash
        return False, True
    return False, False


def sync_docs(args, state) -> tuple[bool, bool]:
    """루트 + 모든 하위 폴더의 CLAUDE.md → 형제 AGENTS.md. 반환: (any_diverged, any_written).

    루트 상태키는 하위 호환을 위해 그대로 "AGENTS.md", 하위는 POSIX 상대경로를 쓴다."""
    any_diverged = False
    any_written = False

    # 동기화 대상 쌍: (정본 CLAUDE.md, 생성 AGENTS.md, 상태키).
    pairs: list[tuple[Path, Path, str]] = [(CANONICAL, ROOT / "AGENTS.md", "AGENTS.md")]
    for rel in iter_nested_canonicals():
        target_rel = rel.parent / "AGENTS.md"
        pairs.append((ROOT / rel, ROOT / target_rel, target_rel.as_posix()))

    managed = {key for _, _, key in pairs}

    for canonical, target, key in pairs:
        diverged, written = _sync_doc_pair(canonical, target, key, state, args)
        any_diverged = any_diverged or diverged
        any_written = any_written or written

    # 고아 정리: 직전에 우리가 생성·관리하던 AGENTS.md 중 대응 CLAUDE.md 가 사라진 것.
    # 우리가 만든 생성물(배너 마커 포함)일 때만 안전하게 삭제한다(수동 파일은 건드리지 않음).
    for key in [k for k in state if k == "AGENTS.md" or k.endswith("/AGENTS.md")]:
        if key in managed:
            continue
        orphan = ROOT / key
        if orphan.exists() and BODY_MARKER in read_text(orphan):
            print(f"[정리] {key} (대응 CLAUDE.md 없음 → 생성물 삭제)")
            if not args.check:
                orphan.unlink()
                any_written = True
        if not args.check:
            del state[key]

    return any_diverged, any_written


# ── 스킬 폴더 동기화 (.claude/skills/ → .agents/skills/) ──────────────────
def iter_source_skill_files() -> list[Path]:
    """제외 규칙을 적용해 동기화 대상 파일의 상대경로 목록을 돌려준다."""
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(SKILLS_SRC):
        # 제외 디렉터리는 walk 자체에서 가지치기.
        dirnames[:] = [d for d in dirnames if d not in SKILL_EXCLUDE_DIRS]
        for fn in filenames:
            if fn in SKILL_EXCLUDE_FILES:
                continue
            if any(fnmatch(fn, g) for g in SKILL_EXCLUDE_GLOBS):
                continue
            rel = (Path(dirpath) / fn).relative_to(SKILLS_SRC)
            files.append(rel)
    return files


def prune_empty_dirs(root: Path) -> None:
    for dirpath, _dirnames, _filenames in os.walk(root, topdown=False):
        p = Path(dirpath)
        if p == root:
            continue
        try:
            if not any(p.iterdir()):
                p.rmdir()
        except OSError:
            pass


def sync_skills(args) -> bool:
    """반환: any_written. 정본을 .agents/skills/ 로 미러링(자격증명 제외)."""
    if not SKILLS_SRC.exists():
        print(f"[건너뜀] 스킬 정본 폴더 없음: {SKILLS_SRC}")
        return False

    src_files = iter_source_skill_files()
    src_set = set(src_files)
    created = updated = removed = 0

    # 1) 새/변경 파일 복사.
    for rel in src_files:
        s = SKILLS_SRC / rel
        d = SKILLS_DST / rel
        if not d.exists():
            created += 1
            if not args.check:
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(s, d)
        elif file_sha(s) != file_sha(d):
            updated += 1
            if not args.check:
                shutil.copyfile(s, d)

    # 2) 고아 정리: 정본에 없는 생성본 파일 삭제(생성 안내 파일은 보호).
    protected = {Path(SKILLS_README_NAME)}
    if SKILLS_DST.exists():
        for dirpath, dirnames, filenames in os.walk(SKILLS_DST):
            # OS/캐시 잡파일은 정리 대상에서 제외(Drive 가 재생성하는 desktop.ini 등).
            dirnames[:] = [d for d in dirnames if d not in SKILL_IGNORE_IN_TARGET_DIRS]
            for fn in filenames:
                if fn in SKILL_IGNORE_IN_TARGET_FILES:
                    continue
                if any(fnmatch(fn, g) for g in SKILL_IGNORE_IN_TARGET_GLOBS):
                    continue
                rel = (Path(dirpath) / fn).relative_to(SKILLS_DST)
                if rel in protected or rel in src_set:
                    continue
                removed += 1
                if not args.check:
                    (Path(dirpath) / fn).unlink()
        if not args.check:
            prune_empty_dirs(SKILLS_DST)

    # 3) 생성 안내 파일 기록.
    if not args.check:
        SKILLS_DST.mkdir(parents=True, exist_ok=True)
        write_text(SKILLS_DST / SKILLS_README_NAME, SKILLS_README)

    if created or updated or removed:
        verb = "(예정)" if args.check else ""
        print(
            f"[미러링{verb}] .agents/skills/ ← .claude/skills/ "
            f"(신규 {created} · 갱신 {updated} · 삭제 {removed} · 대상 {len(src_files)})"
        )
        return not args.check
    print(f"[최신] .agents/skills/ 변경 없음 (대상 {len(src_files)})")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="CLAUDE.md → AGENTS.md · .claude/skills → .agents/skills 단방향 동기화")
    parser.add_argument("--check", action="store_true", help="드라이런: 변경 사항만 출력하고 쓰지 않음")
    parser.add_argument("--force", action="store_true", help="AGENTS.md 발산 경고를 무시하고 강제 덮어쓰기")
    args = parser.parse_args()

    if not CANONICAL.exists():
        print(f"[오류] 정본을 찾을 수 없음: {CANONICAL}", file=sys.stderr)
        return 1

    state = load_state()
    any_diverged, docs_written = sync_docs(args, state)
    skills_written = sync_skills(args)

    if (docs_written or skills_written) and not args.check:
        save_state(state)

    if any_diverged:
        return 2
    if args.check:
        print("\n(--check 모드: 실제로 쓰지 않았습니다.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
