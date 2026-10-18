"""Stage04E-A only: independent Wegovy-only descriptive Figure2 lineage.
Primary path frozen NDC ledger -> channel -> state-quarter -> group-quarter.
Explicit phases. No model fitting, historical-module import, or IO on import.
"""
import csv, hashlib, json, os, stat, sys, math, platform, traceback
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).absolute().parents[2]
CODE = ROOT / '02_audit_code/Stage04E_A'
OUT = ROOT / '03_audit_outputs/Stage04E_A'
WORK = OUT / '_working'
FIG = OUT / 'figures'
SRC = Path('external_data')
BW = ROOT / '03_audit_outputs/Stage04B/_working/R1'
DA = ROOT / '03_audit_outputs/Stage04D_A'
DW = DA / '_working'
REQUEST = Path('external_resources/已粘贴的文本.txt')
Q11 = [f'{y}Q{q}' for y in range(2023, 2026) for q in range(1, 5) if (y, q) >= (2023, 2)]
Q10 = [q for q in Q11 if q != '2024Q1']
SCENARIOS = [0.0, 5.5, 10.0]
VARIANTS = [('F2_L11_LEGACY', 'F2-L11', 'R3_LEGACY', 'LEGACY_MISSING0', SCENARIOS), ('R11_STRICT46_REQUESTED', 'F2-R11', 'R1', 'STRICT_TRUE', ['NONE_TRUE_RATE']), ('R11_STRICT46_SCENARIO', 'F2-R11', 'R1', 'STRICT_SCENARIO', SCENARIOS), ('R11_SOURCE_PRESENT_SUPPORT', 'F2-R11', 'R1', 'W_ONLY_SOURCE', SCENARIOS), ('R11_FULLY_OBSERVED_SUPPORT', 'F2-R11', 'R1', 'FULLY_OBSERVED', ['OBSERVED_ONLY']), ('F2_M10_SAME_MODEL_SUPPORT', 'F2-M10', 'R1', 'MODEL_SUPPORT', SCENARIOS)]

def safe(p):
    p = Path(p).absolute()
    for q in [p, *p.parents]:
        if os.path.lexists(q):
            s = q.lstat()
            assert not (stat.S_ISLNK(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 1024), f'Reparse blocked {q}'
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

def kh(v):
    return th(''.join((str(x) + '\n' for x in v)))

def f17(v):
    return format(float(v), '.17g')

def rc(p):
    with safe(p).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def cw(p, rows, fields=None):
    fields = fields or list(dict.fromkeys((k for r in rows for k in r)))
    assert fields
    with target(p).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def jr(p):
    return json.loads(safe(p).read_text(encoding='utf-8-sig'))

def jw(p, x):
    target(p).write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

def md(n, t):
    target(OUT / n).write_text(t.strip() + '\n', encoding='utf-8')

def files(d):
    for p in sorted(safe(d).iterdir()):
        if p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 1024:
            continue
        if p.is_dir():
            yield from files(p)
        elif p.is_file():
            yield p

def checkpoint(phase, d):
    jw(WORK / (phase + '_complete.json'), {'phase': phase, 'status': 'COMPLETE_VERIFIED', 'details': d, 'code_sha': sha(CODE / 'audit.py')})

def protect_check():
    rows = jr(WORK / 'protected_before.json')
    diff = []
    for r in rows:
        if not safe(r['path']).is_file() or sha(r['path']) != r['sha256']:
            diff.append(r['path'])
    jw(WORK / 'protected_after.json', {'status': 'PASS' if not diff else 'FAIL', 'checked_files': len(rows), 'differences': diff})
    assert not diff, 'Protected source drift'
    return len(rows)

def source_key(r):
    return '|'.join((str(r[c]) for c in ['source_file', 'source_row', 'state', 'calendar_quarter', 'product', 'channel', 'ndc']))

def pkey(s, q):
    return s + '|' + q

def validn(v):
    return v is not None and math.isfinite(v) and (v > 0)

def number(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (ValueError, TypeError):
        return None

def footnote_class(note):
    c = 'NONE_OR_OTHER_DOCUMENTED'
    if note == 'Unable to Provide Data due to System Limitations':
        c = 'UNAVAILABLE_SYSTEM'
    if 'Does Not Include All Full-Benefit' in note:
        c = 'PARTIAL_POPULATION'
    if note == 'Includes Limited-Benefit Enrollees':
        c = 'LIMITED_BENEFIT_SCOPE'
    if 'Any Time in Month' in note:
        c = 'ANYTIME_TIME_SCOPE'
    if note == 'Includes Retroactive Enrollments':
        c = 'RETROACTIVE_RETAINED'
    return c

def intake():
    assert not (WORK / 'intake_complete.json').exists(), 'Do not overwrite completed intake'
    authorities = [ROOT / 'AGENTS.md', ROOT / 'PROJECT_CHARTER.md', ROOT / '03_audit_outputs/Issue_Register.csv', REQUEST]
    names = {'Stage03': ('03_', ['Stage04_Protocol_Lock.csv', 'Figure2_Reconstruction_Spec.md', 'Stage04_Execution_Plan.md', 'Stage04_Decision_Gates.md', 'Missingness_Suppression_Protocol.md', 'RI_Enrollment_Correction_Plan.md', 'Policy_Exposure_Strategy.md']), 'Stage02': ('02_', ['Current_Figure2_Source_Audit.md', 'Original_Result_Lineage.md', 'Missing_Zero_Suppression_Audit.md', 'Enrollment_Definition_Audit.md', 'State_Policy_Adjudication.csv']), 'Stage04B': ('04B_', ['Source_Suppression_Scenarios.csv', 'Population_Affected_Quarters.csv', 'M0_M1_Pair_Support.csv', 'R1_Quality_Assurance.md']), 'Stage04C_A': ('04C_A_', ['Model_Sample.csv', 'Group_Quarter_Support.csv', 'Quality_Assurance.md']), 'Stage04D_A': ('04D_A_', ['Channel_Source_Status.csv', 'Channel_Count_Decomposition.csv', 'Source_Manifest.csv']), 'Stage04D_B': ('04D_B_', ['Executive_Results.md', 'Stage04E_Readiness.md', 'Quality_Assurance.md'])}
    for stage, (prefix, ns) in names.items():
        authorities += [ROOT / '03_audit_outputs' / stage / (prefix + n) for n in ns]
    for p in authorities:
        assert safe(p).is_file(), f'Missing authority {p}'
        p.read_text(encoding='utf-8-sig')
    protected = set(authorities)
    for d in ['00_original', '03_audit_outputs/Stage02', '03_audit_outputs/Stage03', '03_audit_outputs/Stage04A_R3C', '03_audit_outputs/Stage04B', '03_audit_outputs/Stage04C_A', '03_audit_outputs/Stage04C_R1', '03_audit_outputs/Stage04D_A', '03_audit_outputs/Stage04D_B', '02_audit_code/Stage04A_R3C', '02_audit_code/Stage04B', '02_audit_code/Stage04C_A', '02_audit_code/Stage04C_R1', '02_audit_code/Stage04D_A', '02_audit_code/Stage04D_B']:
        protected.update(files(ROOT / d))
    gate = jr(BW / 'input_gate.json')
    assert gate['G_DATA'] == 'PASS'
    sources = []
    for r in gate['source_sha']:
        p = safe(r['Path'])
        assert sha(p) == r['SHA256']
        protected.add(p)
        sources.append({'role': 'FROZEN_SOURCE_COMPONENT', 'path': str(p), 'SHA256': r['SHA256'], 'bytes': p.stat().st_size, 'version': 'Frozen Stage04B source register; not newest-download inference'})
    for name, expected in [('raw_NDC_model_ledger.csv', '6a511d9ad3ec79fa7d686dad05c1e59b453aba8bf0d1f402662932081a988d83'), ('quarterly_population_ledger.csv', '665cd86cb436d1e0f4d33556ea3eaea75145ecefb77cd7b62998182fc00e2c0e')]:
        assert sha(BW / name) == expected
    assert jr(ROOT / '03_audit_outputs/Stage04D_B/_working/post_execution_package_check.json')['status'] == 'PASS'
    zp = ROOT / 'feedback/Medicaid_Wegovy_Stage04D_B_Feedback.zip'
    assert sha(zp) == 'c609a5a25ce902c6f0b716f2bf7f1315bc36f20703e9e59f47abad3b55017717'
    protected.add(zp)
    poppath = next((r['Path'] for r in gate['source_sha'] if r['Path'].endswith('cms_monthly_enrollment_2019_2025.csv')))
    rawpaths = {str(y): str(SRC / f'raw/sdud/sdud_glp1_{y}.csv') for y in [2023, 2024, 2025]}
    source_sha = {str(Path(r['Path'])): r['SHA256'] for r in gate['source_sha']}
    policy = jr(DW / 'P1_policy.json')
    assert len(policy) == 46 and sum(policy.values()) == 12
    adj = rc(ROOT / '03_audit_outputs/Stage02/02_State_Policy_Adjudication.csv')
    changers = sorted((r['State'] for r in adj if r['Excluded_By_Code'] == 'True'))
    assert len(changers) == 5 and set(policy).isdisjoint(changers)
    assert set(policy) == {r['State'] for r in adj if r['Excluded_By_Code'] == 'False'}
    snapshot = [{'path': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(protected)]
    jw(WORK / 'protected_before.json', snapshot)
    cw(OUT / '04E_A_Source_and_Population_Manifest.csv', [{'role': 'AUTHORITATIVE_READONLY', 'path': str(p), 'SHA256': sha(p), 'bytes': p.stat().st_size, 'version': 'Stage03 v1.1 / verified preceding stage / direct Stage04E-A authorization'} for p in authorities] + sources + [{'role': 'FROZEN_DERIVED_LEDGER', 'path': str(BW / n), 'SHA256': sha(BW / n), 'bytes': (BW / n).stat().st_size, 'version': 'Stage04B verified ledger'} for n in ['raw_NDC_model_ledger.csv', 'quarterly_population_ledger.csv', 'monthly_population_ledger.csv']])
    jw(WORK / 'frozen_plan.json', {'Analysis_ID': '04E-01', 'forbidden': ['PPML', '04E-02', 'Stage05', 'manuscript/original figure edits', 'network/download/install'], 'request_sha': sha(REQUEST), 'policy': policy, 'excluded5': changers, 'P': 'P1_46_12_34_July_environment', 'Q11': Q11, 'Q10': Q10, 'variants': [{'Variant_ID': v, 'family': fam, 'population': pop, 'support': support, 'scenarios': ss} for v, fam, pop, support, ss in VARIANTS], 'primary_source': 'frozen Stage04B NDC ledger, WEGOVY only', 'second_path': 'independent raw SDUD brand-filtered excerpts2023/24/25 and independent raw monthly population; fallback ledger-only if raw not readable, must label weaker scope', 'raw_paths': rawpaths, 'source_sha': source_sha, 'population_raw_path': poppath, 'population_filter': 'preliminary_or_updated U AND final_report Y; total_medicaid_enrollment; >=2 validmonthlymean; system unavailable NA; all states same frozen footnote rules', 'R0': 'NOT_VERIFIABLE_NO_RELIABLE_EXISTING_SAME_FIELD_REVISION', 'M10_source': str(ROOT / '03_audit_outputs/Stage04C_A/04C_A_Model_Sample.csv'), 'M10_source_sha': sha(ROOT / '03_audit_outputs/Stage04C_A/04C_A_Model_Sample.csv'), 'original_generator': 'NOT_VERIFIABLE; no current original Figure2 generator/run lineage', 'strict_domain': 'Fixed requested groups12/34; include target allstates but rateNA if any numerator component unknown; population may be recorded without defining numerator', 'QA_tolerances': {'counts_abs': 0, 'pop_abs': 1e-06, 'rate_abs': 1e-09, 'relative': 1e-12}, 'historical_numbers': 'NOT_USED_AS_INPUT; comparison only after independent aggregation QA', 'charts': '4 candidate drawings, no CI/stars/interpolation; PDF SVG PNG300; white axes/no grid/group colors fixed; Q1 gap M10', 'runtime': 'validated .venv_stage04a aggregation if available; bundled runtime reportlab/pypdf/Pillow+Poppler for artifacts, no installs', 'review_boundary': 'user twelve-core technical-stage format; bounded independent technical review with evidence/forensic/statistics rules, not journal peer review'})
    checkpoint('intake', {'protected_files': len(snapshot), 'authorities': len(authorities), 'policy46': len(policy), 'excluded5': changers})
    print('INTAKE PASS', len(snapshot), flush=True)

def primary():
    assert jr(WORK / 'intake_complete.json')['status'] == 'COMPLETE_VERIFIED'
    assert not (WORK / 'primary_complete.json').exists()
    plan = jr(WORK / 'frozen_plan.json')
    policy = plan['policy']
    states = sorted(policy)
    rmap = {r['NDC']: r for r in rc(ROOT / '03_audit_outputs/Stage02/02_NDC_Product_Mapping.csv')}
    led = rc(BW / 'raw_NDC_model_ledger.csv')
    rows = []
    seen = set()
    semantic = set()
    for r in led:
        if r['analytic_brand'] != 'WEGOVY':
            continue
        assert r['state'] in policy and r['calendar_quarter'] in Q11 and (r['utilization_type'] in ['FFSU', 'MCOU']) and (len(r['ndc']) == 11) and r['ndc'].isdigit()
        m = rmap[r['ndc']]
        assert m['Conflict'] == 'False' and m['Observed_Brands'] == 'WEGOVY'
        flag = r['suppressed'].lower()
        assert flag in ['true', 'false']
        sup = flag == 'true'
        obs = number(r['observed'])
        assert sup and obs is None or (not sup and obs is not None and (obs >= 0))
        rr = {'source_file': r['source_file'], 'source_row': int(r['source_row']), 'state': r['state'], 'calendar_quarter': r['calendar_quarter'], 'product': 'WEGOVY', 'channel': r['utilization_type'], 'ndc': r['ndc'], 'source_status': 'SUPPRESSED' if sup else 'OBSERVED_ZERO' if obs == 0 else 'OBSERVED_POSITIVE', 'observed_prescriptions': obs, 'suppressed': sup, 'assigned_0': 0.0 if sup else 0.0, 'assigned_5_5': 5.5 if sup else 0.0, 'assigned_10': 10.0 if sup else 0.0, 'source_file_hash': plan['source_sha'][str(SRC / r['source_file'])]}
        rr['source_row_key'] = source_key(rr)
        assert rr['source_row_key'] not in seen
        seen.add(rr['source_row_key'])
        k = (rr['state'], rr['calendar_quarter'], rr['ndc'], rr['channel'])
        assert k not in semantic
        semantic.add(k)
        rows.append(rr)
    cw(WORK / 'Wegovy_Source_Row_Ledger.csv', rows)
    bycell = defaultdict(list)
    for r in rows:
        bycell[r['state'], r['calendar_quarter'], r['channel']].append(r)
    months = []
    bmonth = {(r['state'], r['month']): r for r in rc(BW / 'monthly_population_ledger.csv')}
    seenmonths = set()
    rawpop = rc(plan['population_raw_path'])
    for idx, r in enumerate(rawpop, 1):
        if r['preliminary_or_updated'] != 'U' or r['final_report'] != 'Y' or r['state_abbreviation'] not in policy:
            continue
        mo = r['reporting_period']
        year = int(mo[:4])
        month = int(mo[4:])
        assert 1 <= month <= 12
        q = f'{year}Q{(month - 1) // 3 + 1}'
        if q not in Q11:
            continue
        s = r['state_abbreviation']
        assert (s, mo) not in seenmonths
        seenmonths.add((s, mo))
        raw = number(r['total_medicaid_enrollment'])
        note = r['total_medicaid_enrollment__footnotes'].strip()
        fc = footnote_class(note)
        valid = raw is not None and raw >= 0 and (fc != 'UNAVAILABLE_SYSTEM')
        replacement = raw if valid else None
        bm = bmonth[s, mo]
        assert number(bm['raw_value']) == raw and number(bm['replacement_value']) == replacement and (bm['footnote_class'] == fc)
        months.append({'state': s, 'month': mo, 'calendar_quarter': q, 'raw_value': raw, 'R1_value': replacement, 'valid': valid, 'footnote_class': fc, 'raw_footnote': note, 'source_row': idx, 'source_month_key': s + '|' + mo + '|U|Y', 'source_file_sha': plan['source_sha'][str(Path(plan['population_raw_path']))], 'R0': 'NOT_VERIFIABLE'})
    cw(WORK / 'Population_Month_Validation.csv', months)
    bq = {(r['state'], r['calendar_quarter']): r for r in rc(BW / 'quarterly_population_ledger.csv')}
    pop = []
    byq = defaultdict(list)
    for m in months:
        byq[m['state'], m['calendar_quarter']].append(m)
    for s in states:
        for q in Q11:
            ms = byq[s, q]
            assert len(ms) == 3
            raw = [m['raw_value'] for m in ms if m['raw_value'] is not None]
            valid = [m['R1_value'] for m in ms if m['valid']]
            legacy = sum(raw) / len(raw) if raw else None
            r1 = sum(valid) / len(valid) if len(valid) >= 2 else None
            prior = bq[s, q]
            assert legacy is not None and math.isclose(legacy, float(prior['N_legacy']), abs_tol=1e-06, rel_tol=0)
            assert r1 is None and prior['N_R1'] == '' or math.isclose(r1, float(prior['N_R1']), abs_tol=1e-06, rel_tol=0)
            assert len(valid) == int(prior['valid_months'])
            pop.append({'state': s, 'calendar_quarter': q, 'coverage_group': 'COVERAGE' if policy[s] else 'NONCOVERAGE', 'population_key': pkey(s, q), 'N_legacy': legacy, 'N_R1': r1, 'valid_months': len(valid), 'raw_months': len(ms), 'unavailable_months': ';'.join((m['month'] for m in ms if not m['valid'])), 'footnote_classes': ';'.join(sorted(set((m['footnote_class'] for m in ms)))), 'partial_population_months': sum((m['footnote_class'] == 'PARTIAL_POPULATION' for m in ms)), 'population_source_key_hash': kh(sorted((m['source_month_key'] for m in ms))), 'population_value_hash': kh((m['source_month_key'] + '|' + str(m['raw_value']) + '|' + str(m['R1_value']) + '|' + m['footnote_class'] for m in sorted(ms, key=lambda m: m['month']))), 'source_file_hash': ms[0]['source_file_sha'], 'R1_rule': '>=2validmonthlymean; unavailableNA; totalMedicaid', 'R0_status': 'NOT_VERIFIABLE_NO_OFFICIAL_REPLACEMENT'})
    assert len(pop) == 506 and len({p['population_key'] for p in pop}) == 506
    ri = next((p for p in pop if p['state'] == 'RI' and p['calendar_quarter'] == '2024Q4'))
    assert ri['N_R1'] == 273605.0 and math.isclose(ri['N_legacy'], 182403.33333333334, abs_tol=1e-08) and (ri['valid_months'] == 2)
    cw(WORK / 'Population_State_Quarter_Unique.csv', pop)
    popmap = {(p['state'], p['calendar_quarter']): p for p in pop}
    cells = []
    statecells = {}
    for s in states:
        for q in Q11:
            for ch in ['FFSU', 'MCOU']:
                rs = bycell.get((s, q, ch), [])
                sup = sum((r['suppressed'] for r in rs))
                obs = sum((r['observed_prescriptions'] for r in rs if not r['suppressed']))
                missing = not rs
                ss = ';'.join(sorted(set((r['source_status'] for r in rs)))) if rs else 'MISSING_SOURCE_RECORD'
                row = {'state': s, 'calendar_quarter': q, 'product': 'WEGOVY', 'channel': ch, 'clock': 'PAID_QUARTER' if ch == 'FFSU' else 'DISPENSE_QUARTER', 'coverage_group': 'COVERAGE' if policy[s] else 'NONCOVERAGE', 'source_status': ss, 'source_present': not missing, 'source_NDC_count': len(rs), 'observed_NDC_rows': len(rs) - sup, 'observed_zero_NDC_rows': sum((r['source_status'] == 'OBSERVED_ZERO' for r in rs)), 'suppressed_NDC_rows': sup, 'observed_prescriptions': obs if not missing else None, 'assigned_prescriptions_0': 0.0 if not missing else None, 'assigned_prescriptions_5_5': sup * 5.5 if not missing else None, 'assigned_prescriptions_10': sup * 10.0 if not missing else None, 'scenario_total_0': obs if not missing else None, 'scenario_total_5_5': obs + sup * 5.5 if not missing else None, 'scenario_total_10': obs + sup * 10.0 if not missing else None, 'unexplained_missing_source': missing, 'missing_reason': 'NO_SOURCE_IN_FROZEN_BRAND_EXCERPT; actual zero/completeness UNKNOWN' if missing else 'NONE', 'source_row_key': ';'.join(sorted((r['source_row_key'] for r in rs))), 'source_key_hash': kh(sorted((r['source_row_key'] for r in rs))), 'source_file_hash': ';'.join(sorted(set((r['source_file_hash'] for r in rs)))), 'population_key': pkey(s, q), 'N_legacy': popmap[s, q]['N_legacy'], 'N_R1': popmap[s, q]['N_R1'], 'valid_population_R1': validn(popmap[s, q]['N_R1']), 'quantity_exact': not missing and sup == 0}
                cells.append(row)
                statecells[s, q, ch] = row
    assert len(cells) == 1012
    cw(OUT / '04E_A_State_Quarter_Wegovy_Status.csv', cells)
    oldcells = {(r['state'], r['calendar_quarter'], r['product'], r['channel']): r for r in rc(DA / '04D_A_Channel_Source_Status.csv')}
    for r in cells:
        old = oldcells[r['state'], r['calendar_quarter'], 'WEGOVY', r['channel']]
        assert r['source_NDC_count'] == int(old['source_NDC_rows']) and r['source_present'] == (old['source_present'] == 'True') and (r['suppressed_NDC_rows'] == int(old['SUPPRESSED_NDC_rows']))
        if r['source_present']:
            assert r['observed_prescriptions'] == float(old['observed_rx']) and r['assigned_prescriptions_5_5'] == float(old['assigned_5_5_rx'])
    ca = rc(plan['M10_source'])
    assert sha(plan['M10_source']) == plan['M10_source_sha'] and len(ca) == 348
    cakeys = [r['state'] + '|' + r['calendar_quarter'] + '|' + r['analytic_brand'] for r in ca]
    assert len(cakeys) == len(set(cakeys))
    assert kh(sorted(cakeys)) == '8a3dc6350298d2b3ec661674231eb368541eb15d8f2f832a55a0f06b89085fa3'
    pairs = defaultdict(set)
    for r in ca:
        assert r['calendar_quarter'] in Q10 and r['effective_model_row'] == 'True'
        pairs[r['state'], r['calendar_quarter']].add(r['analytic_brand'])
    assert len(pairs) == 174 and all((v == {'OZEMPIC', 'WEGOVY'} for v in pairs.values()))
    for r in ca:
        if r['analytic_brand'] == 'WEGOVY':
            cc = [statecells[r['state'], r['calendar_quarter'], ch] for ch in ['FFSU', 'MCOU']]
            assert all((c['source_present'] for c in cc))
            assert sum((c['scenario_total_5_5'] for c in cc)) == float(r['y'])
            assert math.isclose(popmap[r['state'], r['calendar_quarter']]['N_R1'], float(r['N']), abs_tol=1e-06, rel_tol=0)
    cw(WORK / 'M10_Actual_Model_Pair_Keys.csv', [{'state': s, 'calendar_quarter': q, 'population_key': pkey(s, q), 'source': 'actualC-Aeffective348W/O rows;174pairs'} for s, q in sorted(pairs)])
    jw(WORK / 'M10_key_proof.json', {'rows': 348, 'pairs': 174, 'states': len({s for s, q in pairs}), 'source_SHA256': plan['M10_source_sha'], 'model_key_hash': kh(sorted(cakeys)), 'pair_key_hash': kh((pkey(s, q) for s, q in sorted(pairs))), 'quantity_and_population_identity': 'PASS_W_ONLY_MATCH_CA_WEGOVY_ROWS'})
    groups = []
    man = []
    for vid, family, pv, rule, ss in VARIANTS:
        for q in Q11:
            for group in ['COVERAGE', 'NONCOVERAGE']:
                requested = [s for s in states if ('COVERAGE' if policy[s] else 'NONCOVERAGE') == group]
                gap = rule == 'MODEL_SUPPORT' and q == '2024Q1'
                present = {s for s in requested if all((statecells[s, q, ch]['source_present'] for ch in ['FFSU', 'MCOU']))}
                pvalid = {s for s in requested if validn(popmap[s, q]['N_legacy' if pv == 'R3_LEGACY' else 'N_R1'])}
                exact = {s for s in present if all((statecells[s, q, ch]['quantity_exact'] for ch in ['FFSU', 'MCOU']))}
                included = [] if gap else requested if rule in ['LEGACY_MISSING0', 'STRICT_TRUE', 'STRICT_SCENARIO'] else [s for s in requested if s in present & pvalid] if rule == 'W_ONLY_SOURCE' else [s for s in requested if s in exact & pvalid] if rule == 'FULLY_OBSERVED' else [s for s in requested if (s, q) in pairs]
                if rule == 'MODEL_SUPPORT' and (not gap):
                    assert set(included).issubset(present & pvalid)
                excluded = [s for s in requested if s not in included]
                in_sources = [r for r in rows if r['state'] in included and r['calendar_quarter'] == q]
                observed = sum((r['observed_prescriptions'] for r in in_sources if not r['suppressed']))
                nsup = sum((r['suppressed'] for r in in_sources))
                den = sum((popmap[s, q]['N_legacy' if pv == 'R3_LEGACY' else 'N_R1'] for s in included)) if set(included).issubset(pvalid) else None
                complete = bool(included) and set(included).issubset(present & pvalid)
                actual = complete and nsup == 0
                ids = sorted((r['source_row_key'] for r in in_sources))
                popids = [popmap[s, q]['population_source_key_hash'] for s in included]
                for scen in ss:
                    assigned = float(scen) * nsup if isinstance(scen, (int, float)) else 0.0
                    allowed = not gap and bool(included) and validn(den) and (complete if rule != 'LEGACY_MISSING0' else True)
                    if rule == 'STRICT_TRUE':
                        allowed = actual
                    total = observed + assigned if allowed else None
                    rate = 100000 * total / den if allowed else None
                    reason = 'Q1_EXCLUDED_GAP' if gap else 'EMPTY_SUPPORT' if not included else 'INVALID_POPULATION' if not set(included).issubset(pvalid) else 'UNKNOWN_CHANNEL_SOURCE' if not complete and rule != 'LEGACY_MISSING0' else 'SUPPRESSED_TRUE_QUANTITY_UNKNOWN' if rule == 'STRICT_TRUE' and nsup else 'LEGACY_MISSING0_ASSUMPTION; NOT_TRUE_OBSERVED' if rule == 'LEGACY_MISSING0' and set(included) - present else 'NONE'
                    ident = 'EXACT_ON_INCLUDED_OBSERVED_SUPPORT' if allowed and actual else 'LEGACY_ASSUMPTION_ONLY' if allowed and rule == 'LEGACY_MISSING0' else 'SCENARIO_ON_SOURCE_PRESENT_SUPPORT' if allowed else 'NOT_IDENTIFIABLE'
                    obj = {'Variant_ID': vid, 'Family': family, 'Suppression_Scenario': str(scen), 'coverage_group': group, 'quarter': q, 'product': 'WEGOVY_ONLY', 'requested_state_n': len(requested), 'analytic_quarter_requested': not gap, 'included_state_n': len(included), 'included_state_list': ';'.join(included), 'excluded_state_list': ';'.join(excluded), 'requested_state_list': ';'.join(requested), 'source_present_state_n': len(present), 'missing_source_state_n': len(set(requested) - present), 'missing_source_state_list': ';'.join(sorted(set(requested) - present)), 'invalid_population_state_n': len(set(requested) - pvalid), 'invalid_population_state_list': ';'.join(sorted(set(requested) - pvalid)), 'fully_observed_source_state_n': len(exact), 'numerator_observed': observed, 'numerator_observed_is_complete': complete, 'suppressed_NDC_rows': nsup, 'source_NDC_count': len(in_sources), 'numerator_assigned': assigned if allowed else None, 'numerator_total_scenario': total, 'denominator_unique': den, 'rate_per_100000': rate, 'actual_numeric_identifiability': actual, 'scenario_identifiability': ident, 'missingness_reason': reason, 'population_version': pv, 'rule': rule, 'clock': 'FFSU_PAID_PLUS_MCOU_DISPENSE_MIXED', 'Q1_display_gap': gap, 'source_key_hash': kh(ids), 'population_key_hash': kh((pkey(s, q) for s in included)), 'population_source_key_hash': kh(popids), 'result_identity': 'LEGACY_RECONSTRUCTION_ASSUMPTION' if vid == 'F2_L11_LEGACY' and scen == 5.5 else 'HISTORICAL_ASSUMPTION_SENSITIVITY' if family == 'F2-L11' else 'MODEL_SAME_SUPPORT_DESCRIPTIVE_SENSITIVITY' if family == 'F2-M10' else 'STRICT_TRUE_RATE_UNKNOWN' if rule == 'STRICT_TRUE' and (not allowed) else 'CORRECTED_SOURCE_SUPPORT_SCENARIO' if rule == 'W_ONLY_SOURCE' else 'FULLY_OBSERVED_SUPPORT_COMPLETENESS_AUDIT' if rule == 'FULLY_OBSERVED' else 'CORRECTED_STRICT_REQUEST_SCENARIO'}
                    obj['data_version_hash'] = th(json.dumps({'rule': rule, 'source_sha': sha(BW / 'raw_NDC_model_ledger.csv'), 'source_keys': obj['source_key_hash'], 'population_raw_sha': plan['source_sha'][str(Path(plan['population_raw_path']))], 'population_keys': obj['population_key_hash'], 'pop_source': obj['population_source_key_hash'], 'included': included, 'scenario': scen, 'observed': observed, 'assigned': obj['numerator_assigned'], 'denominator': den, 'quarter': q, 'group': group}, sort_keys=True, separators=(',', ':')))
                    groups.append(obj)
        subset = [r for r in groups if r['Variant_ID'] == vid]
        man.append({'Analysis_ID': '04E-01', 'Variant_ID': vid, 'Family': family, 'product': 'WEGOVY_ONLY', 'P': 'P1_46_12_34', 'population_version': pv, 'support_rule': rule, 'scenarios': ';'.join(map(str, ss)), 'analytic_quarter_count': 10 if family == 'F2-M10' else 11, 'analytic_quarters': ';'.join(Q10 if family == 'F2-M10' else Q11), 'display_quarters': ';'.join(Q11), 'Q1': 'EXPLICIT_GAP' if family == 'F2-M10' else 'DESCRIPTIVE_POINT', 'requested_policy_state_n': 46, 'coverage_requested': 12, 'noncoverage_requested': 34, 'group_rows_including_gap': len(subset), 'included_pair_keys_hash': kh(sorted({r['coverage_group'] + '|' + r['quarter'] + '|' + r['included_state_list'] for r in subset})), 'scenario_not_bound': True, 'result_identity': subset[0]['result_identity'], 'source_ledger_SHA256': sha(BW / 'raw_NDC_model_ledger.csv'), 'population_RAW_SHA256': plan['source_sha'][str(Path(plan['population_raw_path']))], 'sample_origin': 'CA_actual_effectivekeys' if family == 'F2-M10' else 'requestedP1 or explicitly W-only source availability'})
    assert len(groups) == 308
    cw(OUT / '04E_A_Group_Quarter_Numerators_Denominators.csv', groups)
    cw(OUT / '04E_A_Figure2_Variant_Manifest.csv', man)
    rep = []
    for q in Q11:
        for group in ['COVERAGE', 'NONCOVERAGE']:
            r = next((r for r in groups if r['Variant_ID'] == 'R11_SOURCE_PRESENT_SUPPORT' and r['Suppression_Scenario'] == '5.5' and (r['quarter'] == q) and (r['coverage_group'] == group)))
            full = next((x for x in groups if x['Variant_ID'] == 'R11_FULLY_OBSERVED_SUPPORT' and x['quarter'] == q and (x['coverage_group'] == group)))
            model = next((x for x in groups if x['Variant_ID'] == 'F2_M10_SAME_MODEL_SUPPORT' and x['Suppression_Scenario'] == '5.5' and (x['quarter'] == q) and (x['coverage_group'] == group)))
            rep.append({k: r[k] for k in ['quarter', 'coverage_group', 'requested_state_n', 'included_state_n', 'included_state_list', 'excluded_state_list', 'missing_source_state_n', 'missing_source_state_list', 'invalid_population_state_n', 'source_NDC_count', 'suppressed_NDC_rows', 'numerator_observed', 'numerator_assigned', 'numerator_total_scenario', 'denominator_unique']} | {'fully_observed_included_state_n': full['included_state_n'], 'fully_observed_state_list': full['included_state_list'], 'M10_pair_included_state_n': model['included_state_n'], 'M10_pair_state_list': model['included_state_list'], 'Wonly_not_M10_states': ';'.join(sorted(set(r['included_state_list'].split(';')) - set(model['included_state_list'].split(';')))), 'selection_mechanism': 'SOURCE_PRESENCE_NOT_CMS_COMPLETE_REPORTING; changes not proof of missing-at-random'})
    cw(OUT / '04E_A_Reportability_and_Missingness.csv', rep)
    source_manifest = rc(OUT / '04E_A_Source_and_Population_Manifest.csv')
    for n, role, fields in [('Wegovy_Source_Row_Ledger.csv', 'CURRENT_INDEPENDENT_WEGOVY_ROW_LEDGER', 'source_file,row,state,quarter,WEGOVY,channel,NDC,status,observed/assigned'), ('Population_Month_Validation.csv', 'CURRENT_RAW_MONTH_POPULATION_VALIDATION', 'U/Y totalMedicaid,raw/R1 values,notes,source month keys'), ('Population_State_Quarter_Unique.csv', 'CURRENT_UNIQUE_POPULATION', '506unique state-quarter,legacy/R1,valid_months,note classes/hashes'), ('M10_Actual_Model_Pair_Keys.csv', 'CURRENT_ACTUAL_C_A_EFFECTIVE_PAIR_KEYS', '174pairs from348actual effective W/O rows')]:
        p = WORK / n
        source_manifest.append({'role': role, 'path': str(p), 'SHA256': sha(p), 'bytes': p.stat().st_size, 'version': 'Stage04E-A derived only; source frozen; no previous file changed', 'quarter_coverage': ';'.join(Q10 if n.startswith('M10') else Q11), 'fields': fields})
    cw(OUT / '04E_A_Source_and_Population_Manifest.csv', source_manifest)
    jw(WORK / 'primary_summary.json', {'source_wegovy_rows': len(rows), 'suppressed_rows': sum((r['suppressed'] for r in rows)), 'observed_zero_rows': sum((r['source_status'] == 'OBSERVED_ZERO' for r in rows)), 'cells': len(cells), 'missing_channel_cells': sum((not r['source_present'] for r in cells)), 'population_unique_keys': len(pop), 'RI_Q4': ri, 'group_rows': len(groups), 'no_historical_printed_value_used': True, 'legacy_mid_results_calculated_before_comparison': [r for r in groups if r['Variant_ID'] == 'F2_L11_LEGACY' and r['Suppression_Scenario'] == '5.5' and (r['quarter'] == '2025Q4')]})
    checkpoint('primary', {'source_rows': len(rows), 'group_rows': len(groups), 'population_unique': len(pop), 'M10_actual_pairs': 174})
    print('PRIMARY PASS', len(rows), len(groups), flush=True)
if __name__ == '__main__':
    assert len(sys.argv) == 2 and sys.argv[1] in ['intake', 'primary']
    try:
        globals()[sys.argv[1]]()
    except Exception:
        target(WORK / (sys.argv[1] + '_failure.log')).write_text(traceback.format_exc(), encoding='utf-8')
        raise
