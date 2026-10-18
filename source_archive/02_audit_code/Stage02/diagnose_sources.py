"""Stage02 authorized read-only field diagnostics. No historical imports or models.
Writes only inside PROJECT_ROOT; all source paths checked for reparse ancestors.
Existing audit outputs are protected against overwrite.
"""
from pathlib import Path
import ast, csv, json, hashlib, os, stat, sys
from collections import Counter, defaultdict
ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path('external_data')
OUT = ROOT / '03_audit_outputs/Stage02'
WORK = OUT / '_working'
WORK.mkdir(parents=True, exist_ok=True)

def safe(p, base):
    p = Path(p).absolute()
    if not p.is_relative_to(base.absolute()):
        raise ValueError('outside authorized root')
    for q in [p, *p.parents]:
        if q.exists() and (q.is_symlink() or getattr(q.lstat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError('reparse path skipped')
        if q == base:
            break
    return p

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def readcsv(rel):
    p = safe(SOURCE / rel, SOURCE)
    with p.open(encoding='utf-8-sig', newline='') as f:
        sample = f.read(4096)
        f.seek(0)
        header = sample.splitlines()[0]
        delimiter = max([',', '\t', '|'], key=header.count)
        yield from csv.DictReader(f, delimiter=delimiter)

def writecsv(name, rows, fields=None):
    rows = list(rows)
    p = safe(OUT / name, ROOT)
    fields = fields or list(rows[0])
    if p.exists():
        with p.open(encoding='utf-8-sig', newline='') as f:
            existing = list(csv.DictReader(f))
        if existing == [{k: str(row.get(k, '')) for k in fields} for row in rows]:
            return
        raise FileExistsError(p)
    with p.open('x', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def writejson(name, obj):
    p = safe(WORK / name, ROOT)
    if p.exists():
        if json.loads(p.read_text(encoding='utf-8')) == obj:
            return
        raise FileExistsError(p)
    with p.open('x', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def number(s):
    try:
        return float(s) if s.strip() else None
    except (ValueError, AttributeError):
        return None

def checkpoint(letter, completed, pending):
    writejson(f'checkpoint_{letter}.json', {'Status': 'COMPLETE_DIAGNOSTICS', 'Date': '2026-10-12 Asia/Shanghai', 'Completed': completed, 'Pending': pending, 'Next_Stage': 'NOT_AUTHORIZED'})
baseline = {}
for base in [ROOT / '00_original', ROOT / '03_audit_outputs/Stage00', ROOT / '03_audit_outputs/Stage01']:
    for parent, dirs, files in os.walk(base, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(parent) / d).is_symlink() and (not getattr((Path(parent) / d).lstat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)]
        for n in files:
            p = safe(Path(parent) / n, ROOT)
            baseline[str(p.relative_to(ROOT))] = digest(p)
baseline['03_audit_outputs/Issue_Register.csv'] = digest(ROOT / '03_audit_outputs/Issue_Register.csv')
writejson('integrity_before.json', baseline)
if not (WORK / 'Issue_Register_Stage01_Baseline.csv').exists():
    (WORK / 'Issue_Register_Stage01_Baseline.csv').write_bytes((ROOT / '03_audit_outputs/Issue_Register.csv').read_bytes())
required = ['01_Executive_Scientific_Audit.md', '01_Reviewer_A_Statistics.md', '01_Reviewer_B_Health_Policy.md', '01_Reviewer_C_Editorial.md', '01_P0_P1_Risk_Register.csv', '01_Claim_Evidence_Matrix.csv', '01_Figure_Table_Consistency.md', '01_Required_Reanalysis_Matrix.csv', '01_Stage02_Recommendations.md', '01_Stage01_Quality_Assurance.md']
intake = []
for p in [ROOT / 'AGENTS.md', ROOT / 'PROJECT_CHARTER.md', ROOT / '03_audit_outputs/Issue_Register.csv', *[ROOT / '03_audit_outputs/Stage01' / n for n in required], *[ROOT / '03_audit_outputs/Stage00' / n for n in ['00_Key_File_Catalog.csv', '00_Analysis_Pipeline_Map.md', '00_Script_Input_Output_Map.csv', '00_Manuscript_Result_Traceability.csv']]]:
    txt = p.read_text(encoding='utf-8-sig')
    intake.append({'Path': str(p), 'SHA256': digest(p), 'Characters_Read': len(txt)})
writejson('required_intake.json', intake)
with (ROOT / '03_audit_outputs/Stage00/00_Full_File_Inventory.csv').open(encoding='utf-8-sig', newline='') as f:
    inventory = list(csv.DictReader(f))
print('inventory_fields', list(inventory[0]), flush=True)
source_register = []
for row in inventory:
    rel = row['Relative_Path']
    p = safe(SOURCE / rel, SOURCE)
    if not p.is_file():
        continue
    source_register.append({'Relative_Path': rel, 'Absolute_Path': str(p), 'Bytes': p.stat().st_size, 'SHA256': digest(p), 'Prior_SHA256': row.get('SHA256_if_Computed', ''), 'Evidence_Level': 'SOURCE_VERIFIED (file bytes only)', 'Role': rel.split('\\')[0]})
writecsv('02_Source_File_Register.csv', source_register)
writejson('source_integrity_before.json', {r['Relative_Path']: r['SHA256'] for r in source_register})
code = safe(SOURCE / 'scripts/02_build_analysis.py', SOURCE).read_text(encoding='utf-8')
tree = ast.parse(code)
constants = {}
functions = []
for node in tree.body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id in ['STATES', 'COVERAGE_2024', 'POLICY_CHANGERS']:
                constants[t.id] = ast.literal_eval(node.value)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        functions.append({'Function': node.name, 'Start': node.lineno, 'End': node.end_lineno})
states = {x[0]: x[1] for x in constants['STATES'].values()}
coverage = constants['COVERAGE_2024']
changers = constants['POLICY_CHANGERS']
writejson('function_locations.json', functions)
if not (WORK / 'checkpoint_A.json').exists():
    manifest = json.loads(safe(SOURCE / 'raw/source_manifest.json', SOURCE).read_text(encoding='utf-8'))
    brand_first = {}
    ndc = defaultdict(lambda: {'names': set(), 'brands': set(), 'quarters': set(), 'rows': 0, 'zero': 0, 'positive': 0, 'suppressed': 0, 'missing': 0})
    source_keys = Counter()
    source_grid = defaultdict(Counter)
    summary = defaultdict(Counter)
    qa = []
    annual = []
    all_states = Counter()
    util = Counter()
    name_mismatch = []
    field_missing = Counter()
    supp_values = Counter()
    true_bad = Counter()
    for year in range(2019, 2026):
        rel = f'raw/sdud/sdud_glp1_{year}.csv'
        p = safe(SOURCE / rel, SOURCE)
        n = 0
        quarters = Counter()
        st = Counter()
        ns = 0
        for r in readcsv(rel):
            n += 1
            b = r['analytic_brand']
            s = r['state']
            q = int(r['quarter'])
            y = int(r['year'])
            quarters[f'{y}Q{q}'] += 1
            st[s] += 1
            all_states[s] += 1
            util[r['utilization_type']] += 1
            if s not in states:
                ns += 1
                continue
            key = (s, y, q, b, r['utilization_type'])
            source_grid[key]['rows'] += 1
            source_keys[s, y, q, r['ndc'], r['utilization_type']] += 1
            flag = r['suppression_used'].strip().lower()
            v = number(r['number_of_prescriptions'])
            kind = 'SUPPRESSED' if flag == 'true' else 'UNKNOWN' if flag != 'false' else 'UNKNOWN' if v is None or v < 0 else 'OBSERVED_ZERO' if v == 0 else 'OBSERVED_POSITIVE'
            source_grid[key][kind] += 1
            for grouping in [('PRODUCT_YEAR', b, str(y), 'ALL', 'ALL'), ('PRODUCT_QUARTER', b, f'{y}Q{q}', 'ALL', 'ALL'), ('UTILIZATION', 'ALL', 'ALL', 'ALL', r['utilization_type']), ('POLICY_PRODUCT_QUARTER', b, f'{y}Q{q}', 'EXCLUDED' if s in changers else 'COVERAGE' if s in coverage else 'NONCOVERAGE', r['utilization_type'])]:
                summary[grouping][kind] += 1
                summary[grouping]['SOURCE_RECORDS'] += 1
            for field in ['number_of_prescriptions', 'units_reimbursed', 'total_amount_reimbursed', 'medicaid_amount_reimbursed', 'non_medicaid_amount_reimbursed']:
                if number(r[field]) is None:
                    field_missing[field, flag] += 1
            if flag == 'true':
                supp_values[str(v)] += 1
            if flag == 'false' and (v is None or v < 11):
                true_bad[kind, str(v)] += 1
            brand_first[b] = min(brand_first.get(b, 99999), y * 4 + q)
            d = ndc[r['ndc']]
            d['names'].add(r['product_name'].strip())
            d['brands'].add(b)
            d['quarters'].add(f'{y}Q{q}')
            d['rows'] += 1
            d['suppressed'] += flag == 'true'
            d['missing'] += v is None
            d['zero'] += kind == 'OBSERVED_ZERO'
            d['positive'] += kind == 'OBSERVED_POSITIVE'
            if b not in r['product_name'].upper():
                name_mismatch.append({'File': rel, 'Row': n + 1, 'Brand': b, 'NDC': r['ndc'], 'Product_Name': r['product_name']})
        m = next((x for x in manifest if x['analytic_extract'] == rel))
        queries = json.loads(safe(SOURCE / f'raw/metadata/sdud_{year}_queries.json', SOURCE).read_text(encoding='utf-8'))
        annual.append({'File': rel, 'Rows': n, 'Declared_Rows': m['rows'], 'SHA_Matches': digest(p) == m['sha256'], 'Query_Returned_Rows': sum((x['returned_rows'] for x in queries)), 'Quarters': ';'.join(sorted(quarters)), 'Jurisdictions': len(st), 'Excluded_Rows': ns, 'Modified_Metadata': m.get('modified', ''), 'Download_Date': 'NOT_VERIFIABLE; script/manuscript asserts 2026-07-30'})
    qa.extend(({'Check': f"ANNUAL_{r['File']}", 'Value': r['Rows'], 'Result': 'PASS' if r['Rows'] == r['Declared_Rows'] == r['Query_Returned_Rows'] and r['SHA_Matches'] else 'FAIL', 'Evidence_Location': r['File'] + '; raw/source_manifest.json; matching queries.json'} for r in annual))
    for key, v in field_missing.items():
        qa.append({'Check': 'NUMERIC_MISSING_' + key[0] + '_SUPPRESSION_' + key[1], 'Value': v, 'Result': 'SOURCE_VERIFIED', 'Evidence_Location': 'raw/sdud/*.csv'})
    qa.extend([{'Check': 'DUPLICATE_SOURCE_KEY_EXCESS', 'Value': sum((n - 1 for n in source_keys.values() if n > 1)), 'Result': 'SOURCE_VERIFIED', 'Evidence_Location': 'state/year/quarter/NDC/utilization_type'}, {'Check': 'NAME_QUERY_MISMATCH', 'Value': len(name_mismatch), 'Result': 'SOURCE_VERIFIED', 'Evidence_Location': 'analytic_brand vs product_name'}, {'Check': 'NDC_MULTI_BRAND', 'Value': sum((len(d['brands']) > 1 for d in ndc.values())), 'Result': 'SOURCE_VERIFIED', 'Evidence_Location': 'NDC across annual extracts'}])
    writecsv('02_Source_Data_QA.csv', qa)
    writecsv('_working/sdud_annual_structure.csv', annual)
    writecsv('02_NDC_Product_Mapping.csv', [{'NDC': n, 'Observed_Brands': ';'.join(sorted(d['brands'])), 'Observed_Product_Names': ';'.join(sorted(d['names'])), 'First_Observed_Quarter': min(d['quarters']), 'Last_Observed_Quarter': max(d['quarters']), 'Source_Rows': d['rows'], 'Suppressed_Rows': d['suppressed'], 'Observed_Zero': d['zero'], 'Observed_Positive': d['positive'], 'Missing_Numeric': d['missing'], 'Conflict': len(d['brands']) > 1, 'Historical_NDC_Completeness': 'NOT_VERIFIABLE', 'Evidence_File': 'raw/sdud/sdud_glp1_2019.csv through 2025.csv', 'Evidence_Location': f'ndc={n}', 'Verification_Status': 'SOURCE_VERIFIED'} for n, d in sorted(ndc.items())])
    supp_summary = []
    for k, c in sorted(summary.items()):
        supp_summary.append(dict(zip(['Scope', 'Brand', 'Period', 'Policy_Group', 'Utilization_Type'], k)) | {'SOURCE_RECORDS': c['SOURCE_RECORDS'], **{cat: c[cat] for cat in ['OBSERVED_POSITIVE', 'OBSERVED_ZERO', 'SUPPRESSED', 'UNKNOWN']}, 'Suppression_Proportion': c['SUPPRESSED'] / c['SOURCE_RECORDS'], 'MISSING_SOURCE_RECORD': 'NOT_APPLICABLE_SOURCE_ROWS', 'STRUCTURAL_NOT_ON_MARKET': 'NOT_APPLICABLE_SOURCE_ROWS'})
    writecsv('02_Suppression_Structure_Summary.csv', supp_summary)
    panelu = list(readcsv('processed/state_quarter_brand_utilization.csv'))
    panel = list(readcsv('processed/state_quarter_brand.csv'))
    gridrows = []
    mismatches = []
    gridcounts = Counter()
    primary_gridcounts = Counter()
    market_evidence = {'WEGOVY': 2021 * 4 + 2, 'ZEPBOUND': 2023 * 4 + 4, 'MOUNJARO': 2022 * 4 + 2}
    for r in panelu:
        key = (r['state'], int(r['year']), int(r['quarter']), r['analytic_brand'], r['utilization_type'])
        c = source_grid.get(key, Counter())
        saved_count = int(float(r['source_cells']))
        gridcounts['GRID_ROWS'] += 1
        if saved_count != c['rows']:
            mismatches.append({'Key': str(key), 'Check': 'SOURCE_CELL_COUNT', 'Saved': saved_count, 'Source': c['rows']})
        if not c['rows']:
            category = 'STRUCTURAL_NOT_ON_MARKET' if key[3] in market_evidence and key[1] * 4 + key[2] < market_evidence[key[3]] else 'MISSING_SOURCE_RECORD'
            gridcounts[category] += 1
            if r['stable_policy_sample'] == '1' and key[3] in ['WEGOVY', 'OZEMPIC'] and (key[1] * 4 + key[2] >= 2023 * 4 + 2):
                primary_gridcounts[category] += 1
            gridrows.append({'State': key[0], 'Quarter': r['calendar_quarter'], 'Brand': key[3], 'Utilization_Type': key[4], 'Policy_Group': 'EXCLUDED' if key[0] in changers else 'COVERAGE' if key[0] in coverage else 'NONCOVERAGE', 'Audit_Status': category, 'Saved_rx_mid': r['rx_mid'], 'Saved_source_cells': saved_count, 'Evidence_File': 'processed/state_quarter_brand_utilization.csv', 'Evidence_Location': f'{key}', 'Note': 'pre-FDA-approval quarter (commercial launch not assumed)' if category.startswith('STRUCTURAL') else 'absence does not establish true zero'})
        else:
            gridcounts['SOURCE_PRESENT'] += 1
    writecsv('_working/grid_missing_records.csv', gridrows)
    writecsv('_working/source_panel_count_mismatches.csv', mismatches, ['Key', 'Check', 'Saved', 'Source'])
    writejson('checkpoint_A_metrics.json', {'Annual': annual, 'Analytic_Source_Rows': sum((c['rows'] for c in source_grid.values())), 'All_States': dict(all_states), 'Utilization_Types': dict(util), 'Suppressed_Original_Rx': dict(supp_values), 'NonSuppressed_Less11_Or_Missing': {str(k): v for k, v in true_bad.items()}, 'Grid': dict(gridcounts), 'Primary_Window_Missing_Utilization_Grid': dict(primary_gridcounts), 'Count_Mismatches': len(mismatches), 'Brands_First_Observed_Index': brand_first, 'NDCs': len(ndc), 'Panel_Rows': len(panel), 'Panel_Utilization_Rows': len(panelu)})
    checkpoint('A', ['SDUD streaming QA, observed NDC mapping, source-state counts, saved grid comparison'], ['Narrative reports and market-source citation verification'])
else:
    panelu = list(readcsv('processed/state_quarter_brand_utilization.csv'))
    panel = list(readcsv('processed/state_quarter_brand.csv'))
policy_files = [('2024-07-01', 'AuavI_v24_dataset.csv'), ('2025-10-01', 'M3fdl_v12_dataset.csv'), ('2026-01-01', 'GL0OB_v8_dataset.csv')]
pol = defaultdict(dict)
for date, n in policy_files:
    for i, r in enumerate(readcsv('raw/policy/' + n), 2):
        s = r['state2'][:2]
        resp = r['State Coverage of Weight-Loss Drugs']
        pol[s][date] = {'Response': resp, 'GLP1': int('covers glp-1s' in resp.lower()), 'Marker': r['state2'][2:], 'File': 'raw/policy/' + n, 'Row': i}
adjudications = []
for s, name in sorted(states.items()):
    d = pol[s]
    a = d['2024-07-01']
    b = d['2025-10-01']
    c = d['2026-01-01']
    changed = a['GLP1'] != b['GLP1']
    initial = 'EXCLUDED_POLICY_CHANGER' if s in changers else 'COVERAGE' if s in coverage else 'NONCOVERAGE'
    conflict = a['GLP1'] != int(s in coverage)
    adjudications.append({'State': s, 'State_Name': name, 'Initial_Classification': initial, 'Source_Snapshot': '2024-07-01 / 2025-10-01 / 2026-01-01 (code-assigned; CSV itself undated)', 'Original_Response': a['Response'], 'Reported_Effective_Date': 'UNKNOWN', 'Coverage_Indication': 'GLP-1 obesity treatment, class-level; Wegovy-specific status UNKNOWN', 'FFS_or_MCO': 'FFS per cited KFF survey; raw CSV omits channel', 'Restriction': 'UNKNOWN; source marker ' + a['Marker'] + '/' + b['Marker'] + '/' + c['Marker'], 'Change_History': f"{a['GLP1']} -> {b['GLP1']} -> {c['GLP1']}", 'Reason_for_Classification': 'explicit code constants; matches first snapshot' if not conflict else 'CONFLICT_FIRST_SNAPSHOT', 'Evidence_File': ';'.join((d[x]['File'] for x, _ in policy_files)), 'Evidence_Location': ';'.join((f"{x}:CSV row {d[x]['Row']}" for x, _ in policy_files)), 'Verification_Status': 'SOURCE_VERIFIED (responses); NOT_VERIFIABLE (event-time stability)', 'Confidence': 'MEDIUM_CONFIDENCE', 'Original_Survey_Date': 'UNKNOWN (as-of dates not fieldwork dates)', 'FDA_Event_State': 'UNKNOWN', 'July_2024_Status': a['Response'], 'October_2025_Status': b['Response'], '2025Q4_Status': 'UNKNOWN', 'January_2026_Status': c['Response'], 'Snapshot_Conflict': conflict, 'First_Two_Snapshot_Change': changed, 'Excluded_By_Code': s in changers, 'Timing_Uncertainty': 'YES', 'Final_Historical_Adjudication': 'UNKNOWN'})
writecsv('02_State_Policy_Adjudication.csv', adjudications)
saved_pol = list(readcsv('processed/policy_snapshots.csv'))
pol_mismatch = []
for r in saved_pol:
    d = pol[r['state']][r['snapshot_date']]
    if int(r['glp1_obesity_coverage']) != d['GLP1'] or r['coverage_category'] != d['Response']:
        pol_mismatch.append(r['state'] + r['snapshot_date'])
erows = list(readcsv('raw/enrollment/cms_monthly_enrollment_2019_2025.csv'))
kept = [r for r in erows if r['preliminary_or_updated'] == 'U' and r['final_report'] == 'Y' and (r['state_abbreviation'] in states)]
e_key = Counter(((r['state_abbreviation'], r['reporting_period']) for r in kept))
eq = defaultdict(list)
enrollqa = []
identity_bad = 0
adult_missing = 0
for r in kept:
    y = int(r['reporting_period'][:4])
    m = int(r['reporting_period'][4:])
    eq[r['state_abbreviation'], y, (m - 1) // 3 + 1].append(r)
    vals = [number(r[k]) for k in ['total_medicaid_enrollment', 'total_chip_enrollment', 'total_medicaid_and_chip_enrollment']]
    if all((v is not None for v in vals)) and vals[0] + vals[1] != vals[2]:
        identity_bad += 1
    adult_missing += number(r['total_adult_medicaid_enrollment']) is None
epanel = defaultdict(set)
for r in panel:
    epanel[r['state'], int(r['year']), int(r['quarter'])].add(r['medicaid_enrollment'])
e_compare = []
for s in sorted(states):
    for y in range(2019, 2026):
        for q in range(1, 5):
            rs = eq.get((s, y, q), [])
            values = [number(r['total_medicaid_enrollment']) for r in rs]
            valid = [v for v in values if v is not None]
            mean = sum(valid) / len(valid) if valid else None
            saved = epanel.get((s, y, q), set())
            parsed = [number(v) for v in saved]
            match = len(saved) == 1 and mean is not None and (parsed[0] is not None) and (abs(mean - parsed[0]) < 1e-06)
            e_compare.append({'State': s, 'Quarter': f'{y}Q{q}', 'Selected_Rows': len(rs), 'Unique_Months': len(set((r['reporting_period'] for r in rs))), 'Numeric_Missing': sum((v is None for v in values)), 'Nonpositive': sum((v is not None and v <= 0 for v in values)), 'Saved_Panel_Field_Matches_Monthly_Mean': match, 'Evidence_File': 'raw/enrollment/cms_monthly_enrollment_2019_2025.csv; processed/state_quarter_brand.csv', 'Evidence_Location': f'state={s}; year={y}; quarter={q}'})
writecsv('02_Enrollment_QA.csv', e_compare)
writejson('checkpoint_B_metrics.json', {'Policy_States': len(pol), 'Saved_Policy_Rows': len(saved_pol), 'Saved_Policy_Mismatches': pol_mismatch, 'Initial_Coverage_Conflicts': [r['State'] for r in adjudications if r['Snapshot_Conflict']], 'First_Two_Changed_States': [r['State'] for r in adjudications if r['First_Two_Snapshot_Change']], 'Enrollment_Raw_Rows': len(erows), 'Enrollment_Selected_Rows': len(kept), 'Enrollment_Duplicate_Month_Excess': sum((n - 1 for n in e_key.values() if n > 1)), 'Enrollment_Adult_Missing': adult_missing, 'Enrollment_Medicaid_Plus_CHIP_Identity_Mismatch': identity_bad, 'Enrollment_Quarter_Not3': sum((r['Unique_Months'] != 3 for r in e_compare)), 'Enrollment_Saved_Field_Mismatch': sum((not r['Saved_Panel_Field_Matches_Monthly_Mean'] for r in e_compare)), 'Enrollment_Fields': list(erows[0])})
checkpoint('B', ['51 state response table, policy saved-output comparison, enrollment month/quarter QA'], ['Official definitions and historical footnotes, channel mapping, narratives'])
saved = {}
for rel in ['analysis/ddd_model_results.csv', 'analysis/event_study_results.csv', 'analysis/trend_adjusted_results.csv', 'analysis/state_reach_2025Q4.csv', 'analysis/inequality_trends.csv', 'analysis/national_quarterly_trends.csv', 'analysis/delivery_system_trends.csv', 'processed/state_burden_covariates.csv', 'tables/Table_1_state_characteristics.csv', 'tables/Table_2_main_models.csv']:
    rows = list(readcsv(rel))
    saved[rel] = {'Rows': len(rows), 'Fields': list(rows[0]) if rows else [], 'Saved_Content': rows if rel in ['analysis/ddd_model_results.csv', 'analysis/event_study_results.csv', 'analysis/trend_adjusted_results.csv', 'tables/Table_1_state_characteristics.csv'] else None}
saved['analysis/analysis_summary.json'] = json.loads(safe(SOURCE / 'analysis/analysis_summary.json', SOURCE).read_text(encoding='utf-8'))
sampleqa = []
for label, brands, start in [('Wegovy', ['WEGOVY', 'OZEMPIC'], 2023 * 4 + 2), ('Zepbound', ['ZEPBOUND', 'MOUNJARO'], 2024 * 4 + 1), ('Negative_Control', ['SAXENDA', 'VICTOZA'], 2023 * 4 + 2)]:
    rs = [r for r in panel if r['analytic_brand'] in brands and r['stable_policy_sample'] == '1' and (int(r['quarter_index']) >= start) and (number(r['medicaid_enrollment']) is not None)]
    counts = Counter(((r['state'], r['analytic_brand']) for r in rs))
    sampleqa.append({'Pair': label, 'Rows': len(rs), 'States': len(set((r['state'] for r in rs))), 'Quarters': len(set((r['calendar_quarter'] for r in rs))), 'Nonpositive_Enrollment': sum((number(r['medicaid_enrollment']) <= 0 for r in rs)), 'Allzero_StateBrand_Groups_Mid': sum((all((number(r['rx_mid']) == 0 for r in rs if (r['state'], r['analytic_brand']) == k)) for k in counts)), 'Formula_Column_Count': 1 + len(counts) - 1 + len(set((r['calendar_quarter'] for r in rs))) - 1 + 3, 'Actual_Rank': 'NOT_COMPUTED'})
writejson('checkpoint_C_saved.json', saved)
writecsv('_working/model_sample_structure.csv', sampleqa)
burden = list(readcsv('processed/state_burden_covariates.csv'))
burdenqa = {col: sum((number(r[col]) is None for r in burden)) for col in list(burden[0])[1:]}
writejson('burden_QA.json', {'Rows': len(burden), 'Missing': burdenqa, 'Missing_Overall_Obesity_States': [r['state'] for r in burden if number(r['obesity_pct']) is None]})
checkpoint('C', ['Static functions located; saved model outputs and structure read; covariate missingness'], ['PPML risk narrative, full display lineage, reports and issue integration'])
print(json.dumps({'A': json.loads((WORK / 'checkpoint_A_metrics.json').read_text(encoding='utf-8')), 'B': json.loads((WORK / 'checkpoint_B_metrics.json').read_text(encoding='utf-8')), 'Sample': sampleqa, 'Burden': burdenqa}, ensure_ascii=False), flush=True)
