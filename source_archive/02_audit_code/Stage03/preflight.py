"""Stage03 metadata/integrity only. No analysis modules or model execution."""
from pathlib import Path
import csv, hashlib, importlib.metadata as md, json, os, stat, sys
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '03_audit_outputs/Stage03'
WORK = OUT / '_working'
WORK.mkdir(parents=True, exist_ok=True)
SOURCE = Path('external_data')

def safe(p, root):
    p.relative_to(root)
    for q in [p, *p.parents]:
        if getattr(q.lstat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise RuntimeError('reparse point rejected')
        if q == root:
            break
    return p

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()

def local_files(root):
    for parent, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not getattr((Path(parent) / d).lstat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT]
        for name in files:
            p = Path(parent) / name
            if not getattr(p.lstat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                yield p
if __name__ == '__main__':
    protected = {}
    for name in ['00_original', '03_audit_outputs/Stage00', '03_audit_outputs/Stage01', '03_audit_outputs/Stage02']:
        for p in local_files(ROOT / name):
            protected[str(p.relative_to(ROOT))] = digest(p)
    index = json.loads((ROOT / '03_audit_outputs/Stage02/_working/source_integrity_before.json').read_text(encoding='utf-8'))
    src = {rel: digest(safe(SOURCE / rel, SOURCE)) for rel in index}
    baseline = {'protected_project': protected, 'indexed_source': src, 'source_matches_stage02': src == index}
    (WORK / 'integrity_before.json').write_text(json.dumps(baseline, indent=2), encoding='utf-8')
    (WORK / 'Issue_Register_Stage02_Baseline.csv').write_bytes((ROOT / '03_audit_outputs/Issue_Register.csv').read_bytes())
    packages = {}
    for package in ['numpy', 'pandas', 'scipy', 'statsmodels', 'matplotlib', 'patsy']:
        try:
            packages[package] = md.version(package)
        except md.PackageNotFoundError:
            packages[package] = 'NOT_INSTALLED'
    env = {'python': sys.version, 'executable': sys.executable, 'prefix': sys.prefix, 'original_environment': 'NOT_VERIFIABLE', 'packages': packages, 'fit_executed': False}
    (WORK / 'environment_preflight.json').write_text(json.dumps(env, indent=2), encoding='utf-8')
    print(json.dumps({'protected_files': len(protected), 'indexed_source_files': len(src), 'source_matches_stage02': src == index, 'environment': env}))
