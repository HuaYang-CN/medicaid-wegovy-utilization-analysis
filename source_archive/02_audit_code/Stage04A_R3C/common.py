import csv, hashlib, json, os, stat, sys
from pathlib import Path
ROOT = Path(__file__).absolute().parents[2]
SRC = Path('external_data')
OUT = ROOT / '03_audit_outputs' / 'Stage04A_R3C'
WORK = OUT / '_working'
CODE = ROOT / '02_audit_code' / 'Stage04A_R3C'
WH = ROOT / '01_analysis_source' / 'offline_wheels_py313'
VENV = ROOT / '.venv_stage04a'
PY = VENV / 'Scripts' / 'python.exe'
REG = ROOT / '03_audit_outputs' / 'Issue_Register.csv'
DATE = '2026-10-13 Asia/Shanghai'

def safe(p):
    p = Path(p).absolute()
    assert '..' not in p.parts
    for q in [p, *p.parents]:
        if os.path.lexists(q):
            s = q.lstat()
            if stat.S_ISLNK(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 1024:
                raise RuntimeError('reparse blocked')
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

def jw(p, d):
    target(p).write_text(json.dumps(d, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

def jr(p):
    return json.loads(safe(p).read_text(encoding='utf-8'))

def rc(p):
    with safe(p).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def cw(p, r, fields=None):
    with target(p).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields or list(r[0]))
        w.writeheader()
        w.writerows(r)

def md(n, t):
    target(OUT / n).write_text(t.strip() + '\n', encoding='utf-8')

def th(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()

def kh(keys):
    return th(''.join((k + '\n' for k in keys)))

def record(stage):
    p = WORK / f'code_at_{stage}.json'
    assert not p.exists()
    jw(p, {'stage': stage, 'date': DATE, 'interpreter': sys.executable, 'code': [{'path': str(p), 'sha256': sha(p)} for p in sorted(CODE.glob('*.py'))]})

def init():
    record('init')
    assert not (WORK / 'key_protection_before.json').exists()
    paths = [ROOT / 'AGENTS.md', ROOT / 'PROJECT_CHARTER.md', REG]
    groups = {'Stage03': ['03_Independent_Replication_Spec.md', '03_PPML_Separation_Convergence_Protocol.md', '03_DDD_Mathematical_Audit.md', '03_Cluster_Inference_Plan.md', '03_Model_Failure_Stop_Rules.md', '03_Stage04_Protocol_Lock.csv', '03_Stage04_Decision_Gates.md', '03_Independent_Reviewer_Challenges.md'], 'Stage04A': ['04A_Executive_Replication_Report.md', '04A_Checkpoint_Status.md'], 'Stage04A_R3': ['04A_R3_Executive_Report.md', '04A_R3_Wheel_Integrity.md', '04A_R3_Wheel_Inventory.csv', 'Dependency_Closure.csv', 'Offline_Dry_Run_Candidates.csv', '04A_R3_Environment_Report.md', '04A_R3_Model_Gates.csv', '04A_R3_Checkpoint_Status.md', '04A_R3_Independent_Code_Review.md']}
    for stage, names in groups.items():
        paths += [ROOT / '03_audit_outputs' / stage / n for n in names]
    jw(WORK / 'mandatory_intake.json', [{'path': str(p), 'sha256': sha(p), 'characters_read': len(safe(p).read_text(encoding='utf-8-sig'))} for p in paths])
    protected = [p for p in paths if p != REG]
    source_rel = ['processed/state_quarter_brand.csv', 'processed/state_quarter_brand_utilization.csv', 'processed/ndc_brand_crosswalk.csv', 'scripts/02_build_analysis.py', 'analysis/ddd_model_results.csv', 'analysis/event_study_results.csv', 'analysis/analysis_summary.json', 'raw/enrollment/cms_monthly_enrollment_2019_2025.csv'] + [f'raw/sdud/sdud_glp1_{y}.csv' for y in range(2019, 2026)]
    protected += [SRC / n for n in source_rel]
    protected += [ROOT / '03_audit_outputs' / 'Stage02' / n for n in ['02_NDC_Product_Mapping.csv', '02_Source_File_Register.csv', '02_State_Policy_Adjudication.csv']]
    protected += [ROOT / 'feedback' / n for n in ['Medicaid_Wegovy_Stage04A_Feedback.zip', 'Medicaid_Wegovy_Stage04A_R1_Feedback.zip', 'Medicaid_Wegovy_Stage04A_R2_Feedback.zip', 'Medicaid_Wegovy_Stage04A_R3_Feedback.zip']]
    jw(WORK / 'key_protection_before.json', [{'path': str(p), 'sha256': sha(p)} for p in protected])
    jw(WORK / 'issue_baseline.json', rc(REG))
    print('key hashes/intake frozen; no history rescan')
if __name__ == '__main__':
    init()
