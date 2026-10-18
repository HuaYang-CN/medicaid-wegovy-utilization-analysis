"""Stage04B-R1 boundaries and audit serialization, no side effects on import."""
import csv, hashlib, json, os, stat, sys
from pathlib import Path
ROOT = Path(__file__).absolute().parents[3]
SRC = Path('external_data')
CODE = ROOT / '02_audit_code/Stage04B/R1'
OUT = ROOT / '03_audit_outputs/Stage04B'
WORK = OUT / '_working/R1'
A = ROOT / '03_audit_outputs/Stage04A_R3C'
ACODE = ROOT / '02_audit_code/Stage04A_R3C'
VENV = ROOT / '.venv_stage04a'
PY = VENV / 'Scripts/python.exe'
REG = ROOT / '03_audit_outputs/Issue_Register.csv'
DATE = '2026-10-13 Asia/Shanghai'

def safe(p):
    p = Path(p).absolute()
    assert '..' not in p.parts
    for q in [p, *p.parents]:
        if os.path.lexists(q):
            s = q.lstat()
            assert not (stat.S_ISLNK(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 1024), 'reparse blocked'
    return p

def target(p):
    p = safe(p)
    assert p.is_relative_to(OUT) or p.is_relative_to(CODE)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def sha(p):
    h = hashlib.sha256()
    with safe(p).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()

def th(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()

def kh(k):
    return th(''.join((str(v) + '\n' for v in k)))

def f17(v):
    return format(float(v), '.17g')

def jw(p, d):
    target(p).write_text(json.dumps(d, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

def jr(p):
    return json.loads(safe(p).read_text(encoding='utf-8'))

def rc(p):
    with safe(p).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def cw(p, rows, fields=None):
    with target(p).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def md(n, s):
    target(OUT / n).write_text(s.strip() + '\n', encoding='utf-8')

def record(name):
    p = WORK / ('code_at_' + name + '.json')
    assert not p.exists()
    jw(p, {'stage': name, 'date': DATE, 'interpreter': sys.executable, 'files': [{'path': str(p), 'sha256': sha(p)} for p in sorted(CODE.glob('*.py'))]})
