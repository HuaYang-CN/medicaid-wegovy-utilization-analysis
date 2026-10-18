"""New bounded source dictionary/footnote checks, without model/outcome recalculation."""
from pathlib import Path
import csv, json, hashlib
from collections import Counter
ROOT = Path(__file__).resolve().parents[2]
SRC = Path('external_data')
OUT = ROOT / '03_audit_outputs/Stage02'
WORK = OUT / '_working'

def read(p):
    with p.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def write(p, rs):
    with p.open('x', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rs[0]))
        w.writeheader()
        w.writerows(rs)
enrollment = read(SRC / 'raw/enrollment/cms_monthly_enrollment_2019_2025.csv')
notes = []
counts = Counter()
primary = Counter()
changers = {'MO', 'NC', 'SC', 'TN', 'UT'}
for i, r in enumerate(enrollment, 2):
    if r['preliminary_or_updated'] != 'U' or r['final_report'] != 'Y':
        continue
    note = r['total_medicaid_enrollment__footnotes']
    counts[note] += 1
    if note:
        main = r['reporting_period'] >= '202304' and r['state_abbreviation'] not in changers
        if main:
            primary[note] += 1
        notes.append({'State': r['state_abbreviation'], 'Month': r['reporting_period'], 'Footnote': note, 'Within_Primary_Window_Stable_State': main, 'Raw_Enrollment_Value': r['total_medicaid_enrollment'], 'Evidence_File': 'raw/enrollment/cms_monthly_enrollment_2019_2025.csv', 'Evidence_Location': f'CSV record {i} including header'})
write(OUT / '02_Enrollment_Source_Footnote_QA.csv', notes)
checks = Counter()
bad = []
for y in range(2019, 2026):
    for i, r in enumerate(read(SRC / f'raw/sdud/sdud_glp1_{y}.csv'), 2):
        checks['Rows_Checked'] += 1
        if len(r['ndc']) != 11 or not r['ndc'].isdigit():
            checks['Invalid_NDC_Format'] += 1
        if r['ndc'] != r['labeler_code'] + r['product_code'] + r['package_size']:
            checks['NDC_Segment_Mismatch'] += 1
manifest = json.loads((SRC / 'raw/source_manifest.json').read_text(encoding='utf-8'))
e = next((r for r in manifest if r['analytic_extract'].startswith('raw/enrollment')))
h = hashlib.sha256((SRC / e['analytic_extract']).read_bytes()).hexdigest()
res = {'Enrollment_Footnotes_Selected': dict(counts), 'Enrollment_Footnotes_Main_Stable_Window': dict(primary), 'NDC_Format_Segments': dict(checks), 'Enrollment_Manifest_Rows_Match': e['rows'] == len(enrollment), 'Enrollment_Manifest_SHA_Match': e['sha256'] == h, 'Rhode_Island_Source_Location': [r for r in notes if r['State'] == 'RI' and r['Month'] == '202412']}
with (WORK / 'final_field_checks.json').open('x', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print(json.dumps(res, ensure_ascii=False))
