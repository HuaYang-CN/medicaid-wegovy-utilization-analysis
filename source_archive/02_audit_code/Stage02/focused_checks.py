"""Bounded Stage02 diagnostics of saved fields and raw covariate structures.
No model, covariance, effect, group rate, inequality or index recalculation.
"""
from pathlib import Path
import csv, json, stat, ast
from collections import Counter, defaultdict
ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path('external_data')
OUT = ROOT / '03_audit_outputs/Stage02'
WORK = OUT / '_working'

def rows(p, sep=','):
    for q in [p, *p.parents]:
        if q.exists() and (q.is_symlink() or getattr(q.lstat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError('reparse')
        if q in [ROOT, SOURCE]:
            break
    with p.open(encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f, delimiter=sep)

def save(n, rs):
    rs = list(rs)
    with (OUT / n).open('x', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rs[0]))
        w.writeheader()
        w.writerows(rs)

def num(s):
    try:
        return float(s) if s.strip() else None
    except:
        return None
p = list(rows(SOURCE / 'processed/state_quarter_brand.csv'))
u = list(rows(SOURCE / 'processed/state_quarter_brand_utilization.csv'))
grid = list(rows(WORK / 'grid_missing_records.csv'))
gridgroup = defaultdict(Counter)
for r in grid:
    for scope, period in [('PRODUCT_YEAR', r['Quarter'][:4]), ('PRODUCT_QUARTER', r['Quarter']), ('POLICY_PRODUCT_QUARTER', r['Quarter'])]:
        k = (scope, r['Brand'], period, r['Policy_Group'] if scope.startswith('POLICY') else 'ALL', r['Utilization_Type'])
        gridgroup[k][r['Audit_Status']] += 1
save('02_Grid_State_Summary.csv', [dict(zip(['Scope', 'Brand', 'Period', 'Policy_Group', 'Utilization_Type'], k)) | {'MISSING_SOURCE_RECORD': v['MISSING_SOURCE_RECORD'], 'STRUCTURAL_NOT_ON_MARKET': v['STRUCTURAL_NOT_ON_MARKET'], 'Evidence': '_working/grid_missing_records.csv; approved product-quarter exclusion ONLY'} for k, v in sorted(gridgroup.items())])
primary = [r for r in p if r['analytic_brand'] in ['WEGOVY', 'OZEMPIC'] and r['stable_policy_sample'] == '1' and (int(r['quarter_index']) >= 2023 * 4 + 2)]
zero_groups = []
for label, bs, start in [('Wegovy', ['WEGOVY', 'OZEMPIC'], 2023 * 4 + 2), ('Zepbound', ['ZEPBOUND', 'MOUNJARO'], 2024 * 4 + 1), ('Negative_Control', ['SAXENDA', 'VICTOZA'], 2023 * 4 + 2)]:
    d = defaultdict(list)
    for r in p:
        if r['analytic_brand'] in bs and r['stable_policy_sample'] == '1' and (int(r['quarter_index']) >= start):
            d[r['state'], r['analytic_brand']].append(r)
    for k, rs in d.items():
        if all((num(r['rx_mid']) == 0 for r in rs)):
            zero_groups.append({'Pair': label, 'State': k[0], 'Brand': k[1], 'Quarters': len(rs), 'All_Source_Cells_Absent': all((num(r['source_cells']) == 0 for r in rs)), 'Evidence_File': 'processed/state_quarter_brand.csv', 'Evidence_Location': str(k), 'Status': 'SOURCE_VERIFIED (saved field zero pattern)'})
save('_working/allzero_state_brand_groups.csv', zero_groups)
e = list(rows(SOURCE / 'raw/enrollment/cms_monthly_enrollment_2019_2025.csv'))
selected = [r for r in e if r['preliminary_or_updated'] == 'U' and r['final_report'] == 'Y']
qa = {'Primary_Combined_Grid_Source_Absent': sum((num(r['source_cells']) == 0 for r in primary)), 'Primary_Combined_Grid_Zero': sum((num(r['rx_mid']) == 0 for r in primary)), 'Primary_Absent_By_Brand': dict(Counter((r['analytic_brand'] for r in primary if num(r['source_cells']) == 0))), 'Primary_Missing_Util_By_Brand': dict(Counter((r['Brand'] for r in grid if r['Brand'] in ['WEGOVY', 'OZEMPIC'] and r['Policy_Group'] != 'EXCLUDED' and (r['Quarter'] >= '2023Q2')))), 'Allzero_Groups': zero_groups, 'Enrollment_Flags': dict(Counter((r['preliminary_or_updated'] + '/' + r['final_report'] for r in e))), 'Selected_Medicaid_Missing': sum((num(r['total_medicaid_enrollment']) is None for r in selected)), 'Selected_CHIP_Missing': sum((num(r['total_chip_enrollment']) is None for r in selected)), 'Selected_Combined_Missing': sum((num(r['total_medicaid_and_chip_enrollment']) is None for r in selected)), 'Selected_Medicaid_Nonpositive': sum((num(r['total_medicaid_enrollment']) <= 0 for r in selected)), 'Selected_Adult_Observed_States': sorted(set((r['state_abbreviation'] for r in selected if num(r['total_adult_medicaid_enrollment']) is not None)))}
burden = []
for n in ['2-Obesity-by-state-in-2024.csv', '2024-obesity-aged-18-39y.csv', '2024-obesity-aged-40-59y.csv', '2024-obesity-aged-60y.csv', '7-Black.csv', '8-White.csv', '6-Hispanic.csv']:
    rs = list(rows(SOURCE / 'raw/burden' / n))
    burden.append({'File': n, 'Rows': len(rs), 'Fields': ';'.join(rs[0]), 'NonNumeric_Prevalence': sum((num(r['Prevalence']) is None for r in rs)), 'Unknown_States': ';'.join((r['State'] for r in rs if num(r['Prevalence']) is None))})
for n in ['b01003', 'b19013', 'b17001', 'b15003', 'b23025', 'b27001']:
    rs = list(rows(SOURCE / f'raw/burden/acsdt1y2024-{n}.dat', '|'))
    st = [r for r in rs if r['GEO_ID'].startswith('0400000US')]
    burden.append({'File': f'acsdt1y2024-{n}.dat', 'Rows': len(rs), 'Fields': f'{len(rs[0])} columns; GEO_ID; {n.upper()}_E/M estimates/margins', 'NonNumeric_Prevalence': 'NOT_APPLICABLE', 'Unknown_States': f"state-geography rows={len(st)}; duplicates={len(st) - len(set((r['GEO_ID'] for r in st)))}"})
save('_working/burden_source_structure.csv', burden)
qa['BRFSS_Age_Source_Prevalence_Identical'] = all(([(r['State'], r['Prevalence'], r['95% CI']) for r in rows(SOURCE / 'raw/burden' / n)] == [(r['State'], r['Prevalence'], r['95% CI']) for r in rows(SOURCE / 'raw/burden/2-Obesity-by-state-in-2024.csv')] for n in ['2024-obesity-aged-18-39y.csv', '2024-obesity-aged-40-59y.csv', '2024-obesity-aged-60y.csv']))
with (WORK / 'focused_QA.json').open('x', encoding='utf-8') as f:
    json.dump(qa, f, ensure_ascii=False, indent=2)
print(json.dumps(qa, ensure_ascii=False))
