"""Create a safe, portable complete project ZIP using explicit include rules.

NO secrets / user data / databases / local sessions / venvs / browser cookies.
Update allowlist when students add reusable program files.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from export_skills import export as export_skills

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'exports'
SAFE_FILES = {
    'README.md', 'START_HERE_STUDENTS.md', 'CHALLENGE_BRIEF.md',
    'AGENTS.md','VERSION.txt','LICENSE.txt', 'requirements.txt',
    'config.example.json','.env.example','.gitignore',
}
SAFE_SUFFIXES = {'.md','.py','.html','.css','.js','.json','.txt','.bat','.sh'}
SAFE_FOLDERS = {'app','web','docs','skills','prompts','schemas','sample_data','tests','scripts','deliverables'}
BLOCKED_PARTS = {'__pycache__','.git','.venv','venv','node_modules','private_data','real_resumes','credentials','.auth'}


def export():
    export_skills()
    OUT.mkdir(exist_ok=True)
    dest = OUT / 'jobfinder-complete-portable-handoff.zip'
    members = []
    for folder in sorted(SAFE_FOLDERS):
        for file in sorted((ROOT/folder).rglob('*')):
            if not file.is_file() or file.suffix not in SAFE_SUFFIXES or any(part in BLOCKED_PARTS for part in file.relative_to(ROOT).parts):
                continue
            if file.name.startswith('.env') and file.name != '.env.example':
                continue
            members.append(file)
    members += [ROOT/name for name in sorted(SAFE_FILES)]
    with ZipFile(dest,'w',ZIP_DEFLATED) as archive:
        for file in members:
            archive.write(file, f'JobFinder_Hackathon_4/{file.relative_to(ROOT).as_posix()}')
        for file in sorted(OUT.glob('*.zip')):
            if file == dest:
                continue
            archive.write(file, f'JobFinder_Hackathon_4/exports/{file.name}')
    print('Created:',dest)
    print('Files:',len(members),'plus portable skills archives')


if __name__=='__main__':
    export()
