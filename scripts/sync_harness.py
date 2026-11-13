"""Sync canonical skills/SKILL.md folders into .agents/skills/ for Codex discovery.

Avoids symlinks so archives and checkouts remain portable across macOS, Linux,
and Windows. Run with --check in CI or pre-handoff checks.
"""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / 'skills'
MIRROR = ROOT / '.agents' / 'skills'
REQUIRED_SKILLS = (
    'application-preparer',
    'company-research',
    'job-finder',
    'networking-outreach',
    'response-tracker',
    'resume-optimizer',
)


def sync(check_only: bool = False) -> int:
    mismatches = []
    if not check_only:
        MIRROR.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_SKILLS:
        src = CANONICAL / name / 'SKILL.md'
        if not src.is_file():
            raise FileNotFoundError(f'Missing canonical skill: {src}')
        dst = MIRROR / name / 'SKILL.md'
        src_text = src.read_text(encoding='utf8')
        dst_text = dst.read_text(encoding='utf8') if dst.is_file() else None
        if src_text != dst_text:
            mismatches.append(name)
            if not check_only:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
    if check_only:
        if mismatches:
            print('Out-of-sync .agents/skills:', ', '.join(mismatches))
            print('Run: python3 scripts/sync_harness.py')
            return 1
        print('All 6 skills in .agents/skills/ match skills/.')
        return 0
    print(f'Synced {len(REQUIRED_SKILLS)} skills into .agents/skills/ (updated: {len(mismatches)}).')
    return 0


def main():
    parser = argparse.ArgumentParser(description='Mirror skills/*/SKILL.md into .agents/skills/.')
    parser.add_argument('--check', action='store_true', help='Verify parity without writing files.')
    args = parser.parse_args()
    raise SystemExit(sync(check_only=args.check))


if __name__ == '__main__':
    main()
