"""Export portable SKILL.md folders as individual ZIPs + a bundle.

White-list only checked-in instructional resources. No runtime user data or
secrets are ever read or included.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'exports'
SKILLS = ROOT / 'skills'


def export():
    OUT.mkdir(exist_ok=True)
    skill_names = sorted(d.name for d in SKILLS.iterdir() if d.is_dir() and (d/'SKILL.md').is_file())
    if len(skill_names) != 6:
        raise RuntimeError('Expected six skills, got ' + str(skill_names))
    for name in skill_names:
        filepath = OUT / f'{name}.zip'
        with ZipFile(filepath, 'w', ZIP_DEFLATED) as bundle:
            bundle.write(SKILLS / name / 'SKILL.md', f'{name}/SKILL.md')
        print('Created', filepath)
    with ZipFile(OUT / 'jobfinder-all-skills.zip', 'w', ZIP_DEFLATED) as bundle:
        for name in skill_names:
            bundle.write(SKILLS/name/'SKILL.md', f'{name}/SKILL.md')
        for folder in ('prompts', 'schemas'):
            for file in sorted((ROOT/folder).glob('*')):
                if file.is_file() and file.suffix in ('.md','.json'):
                    bundle.write(file, f'{folder}/{file.name}')
        for name in ('AGENTS.md','CHALLENGE_BRIEF.md','config.example.json'):
            bundle.write(ROOT/name,name)
    print('Created', OUT / 'jobfinder-all-skills.zip')


if __name__ == '__main__':
    export()
