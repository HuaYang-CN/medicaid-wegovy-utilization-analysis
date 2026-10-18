"""Stage04D-A only: source aggregation, reportability and matrix diagnostics.
No regression/statistical inference. Prior sources read only. Explicit phases.
"""
import csv, json, hashlib, os, stat, sys, math, zipfile, importlib.metadata as metadata
from pathlib import Path
ROOT = Path(__file__).absolute().parents[2]
CODE = ROOT / '02_audit_code/Stage04D_A'
OUT = ROOT / '03_audit_outputs/Stage04D_A'
WORK = OUT / '_working'
B = ROOT / '03_audit_outputs/Stage04B'
BW = B / '_working/R1'
CA = ROOT / '03_audit_outputs/Stage04C_A'
CR = ROOT / '03_audit_outputs/Stage04C_R1'
S3 = ROOT / '03_audit_outputs/Stage03'
S2 = ROOT / '03_audit_outputs/Stage02'
REQUEST = Path('external_resources/已粘贴的文本.txt')
C10 = ['2023Q2', '2023Q3', '2023Q4', '2024Q2', '2024Q3', '2024Q4', '2025Q1', '2025Q2', '2025Q3', '2025Q4']
D11 = C10[:3] + ['2024Q1'] + C10[3:]
PRODUCTS = ['OZEMPIC', 'WEGOVY']
CHANNELS = ['FFSU', 'MCOU']
SETS = ['CH-FFSU', 'CH-MCOU', 'CH-BOTH', 'CH-WONLY']

def safe(p):
    p = Path(p).absolute()
    for q in [p, *p.parents]:
        if os.path.lexists(q):
            s = q.lstat()
            assert not (stat.S_ISLNK(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 1024), f'Reparse blocked {q}'
    return p

def target(p):
    p = safe(p)
    assert p.is_relative_to(CODE) or p.is_relative_to(OUT)
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

def jr(p):
    return json.loads(safe(p).read_text(encoding='utf-8-sig'))

def jw(p, x):
    target(p).write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

def cw(p, rows):
    assert rows
    cols = list(dict.fromkeys((k for r in rows for k in r)))
    with target(p).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

def md(name, s):
    target(OUT / name).write_text(s.strip() + '\n', encoding='utf-8')

def files(d):
    for p in sorted(safe(d).iterdir()):
        if p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 1024:
            continue
        if p.is_dir():
            yield from files(p)
        elif p.is_file():
            yield p

def seal(phase, x):
    jw(WORK / (phase + '_complete.json'), {'phase': phase, 'status': 'COMPLETE_VERIFIED', 'details': x, 'executed_audit_code_SHA256': sha(CODE / 'audit.py')})

def key(r):
    return r['state'] + '|' + r['calendar_quarter'] + '|' + r['product']

def sourcekey(r):
    return '|'.join((r[x] for x in ['source_file', 'source_row', 'state', 'calendar_quarter', 'analytic_brand', 'utilization_type', 'ndc']))

def period(q):
    return 'TRANSITION' if q == '2024Q1' else 'PRE' if q < '2024Q2' else 'POST'

def intake():
    assert not (WORK / 'intake_complete.json').exists()
    required = [ROOT / 'AGENTS.md', ROOT / 'PROJECT_CHARTER.md', ROOT / '03_audit_outputs/Issue_Register.csv', REQUEST]
    required += [S3 / ('03_' + n) for n in ['Stage04_Protocol_Lock.csv', 'Stage04_Execution_Plan.md', 'FFS_MCO_Design_Protocol.md', 'Missingness_Suppression_Protocol.md', 'RI_Enrollment_Correction_Plan.md', 'Stage04_Decision_Gates.md', 'Model_Failure_Stop_Rules.md', 'PPML_Separation_Convergence_Protocol.md', 'Cluster_Inference_Plan.md']]
    required += [S2 / ('02_' + n) for n in ['FFS_MCO_Consistency_Audit.md', 'Missing_Zero_Suppression_Audit.md', 'Enrollment_Definition_Audit.md', 'Policy_Source_Audit.md', 'State_Policy_Adjudication.csv', 'Payment_Channel_Mapping.csv']]
    required += [B / ('04B_' + n) for n in ['Model_Results.csv', 'Model_Gates.csv', 'M0_M1_Pair_Support.csv', 'Group_Product_PrePost_Support.csv', 'R1_Quality_Assurance.md', 'R1_File_Inventory.csv', 'Stage04C_Readiness.md']]
    required += [BW / 'raw_NDC_model_ledger.csv', BW / 'quarterly_population_ledger.csv']
    required += [CA / ('04C_A_' + n) for n in ['Model_Sample.csv', 'Group_Quarter_Support.csv', 'Primary_PPML_Results.csv']]
    required += [CR / ('04C_R1_' + n) for n in ['Executive_Decision.md', 'Future_Audit_Support_Feasibility.csv', 'Reportability_and_Suppression_Audit.csv', 'NM_Identifiability_Audit.csv', 'Stage04D_04E_Readiness.md']]
    for p in required:
        assert safe(p).is_file(), f'BLOCKED missing input {p}'
        p.read_text(encoding='utf-8-sig')
    assert '协议修订 v1.1' in (S3 / '03_FFS_MCO_Design_Protocol.md').read_text(encoding='utf-8-sig')
    inventory = {r['Path']: r['SHA256'] for r in rc(B / '04B_R1_File_Inventory.csv')}
    for p in [BW / 'raw_NDC_model_ledger.csv', BW / 'quarterly_population_ledger.csv']:
        assert sha(p) == inventory[str(p)]
    protected = set(required)
    for d in ['03_audit_outputs/Stage04A_R3C', '03_audit_outputs/Stage04B', '03_audit_outputs/Stage04C_A', '03_audit_outputs/Stage04C_R1', '02_audit_code/Stage04A_R3C', '02_audit_code/Stage04B', '02_audit_code/Stage04C_A', '02_audit_code/Stage04C_R1', '00_original']:
        protected.update(files(ROOT / d))
    for r in jr(BW / 'input_gate.json')['source_sha']:
        p = safe(r['Path'])
        assert sha(p) == r['SHA256']
        protected.add(p)
    for stage in [CA, CR]:
        proof = jr(stage / '_working/package_verification.json')
        zp = safe(proof['zip_path'])
        assert sha(zp) == proof['ZIP_SHA256']
        protected.add(zp)
        with zipfile.ZipFile(zp) as z:
            assert z.testzip() is None
            for r in proof['members']:
                digest = r.get('sha256', r.get('SHA256'))
                assert hashlib.sha256(z.read(r['member'])).hexdigest() == digest and sha(ROOT / r['member']) == digest
    before = [{'path': str(p), 'SHA256': sha(p), 'bytes': p.stat().st_size, 'authority': p in required} for p in sorted(protected)]
    jw(WORK / 'protected_before.json', before)
    manifest = [{'role': 'AUTHORITATIVE_READONLY_INPUT', 'path': str(p), 'SHA256': sha(p), 'bytes': p.stat().st_size, 'identity': 'Stage03 v1.1' if p.is_relative_to(S3) else 'Stage04B-R1' if p.is_relative_to(B) else 'Stage04C-A' if p.is_relative_to(CA) else 'Stage04C-R1' if p.is_relative_to(CR) else 'Stage02' if p.is_relative_to(S2) else 'Project authority / direct human authorization', 'status': 'BYTE_VERIFIED'} for p in required]
    manifest += [{'role': 'EXPLICIT_DATA_SOURCE_HASH_ONLY', 'path': r['Path'], 'SHA256': r['SHA256'], 'bytes': safe(r['Path']).stat().st_size, 'identity': 'frozen Stage04B source component; no DATA directory scan', 'status': 'BYTE_VERIFIED'} for r in jr(BW / 'input_gate.json')['source_sha']]
    cw(OUT / '04D_A_Source_Manifest.csv', manifest)
    jw(WORK / 'frozen_plan.json', {'request_SHA256': sha(REQUEST), 'Analysis_IDs': ['04D-01', '04D-02', '04D-04_STRUCTURAL_ONLY'], 'P': 'P1_JULY2024_46_12_34', 'windows': {'DATA-11': D11, 'DATA-C10': C10}, 'products': PRODUCTS, 'channels': CHANNELS, 'population': 'R0_NOT_VERIFIABLE; frozen R1 total Medicaid >=2 valid months', 'suppression': 'source-level5.5; not official mean/strict bound', 'support': {'CH-FFSU': 'W and O source present within FFSU', 'CH-MCOU': 'W and O source present within MCOU', 'CH-BOTH': 'W/O x FFSU/MCOU source present', 'CH-WONLY': 'W x both channels; descriptive only'}, 'Post': '2024Q2 onward', 'EL1': 'early Q2 only; late Q3 onward; all6 interactions', 'LOO': 'all46 requested states per FFSU/MCOU/CH-BOTH; matrix only', 'regression_fits': 0, 'new_effect_or_significance_values': 0})
    seal('intake', {'protected_files': len(before), 'authority_files': len(required)})
    print('INTAKE PASS', len(before), flush=True)

def info(rows):
    ss = {r['state'] for r in rows}
    cg = {r['state'] for r in rows if int(r['coverage']) == 1}
    return {'n': len(rows), 'G': len(ss), 'coverage_G': len(cg), 'noncoverage_G': len(ss - cg), 'model_key_hash': kh(sorted((key(r) for r in rows))), 'order_hash': kh((key(r) for r in rows))}

def aggregate():
    assert jr(WORK / 'intake_complete.json')['status'] == 'COMPLETE_VERIFIED'
    raw = rc(BW / 'raw_NDC_model_ledger.csv')
    assert len({(r['source_file'], r['source_row']) for r in raw}) == len(raw)
    m0 = rc(BW / 'R1_M0_MID_requested.csv')
    policy = {r['state']: int(r['coverage_2024']) for r in m0}
    assert len(policy) == 46 and sum(policy.values()) == 12
    population = {(r['state'], r['calendar_quarter']): r for r in rc(BW / 'quarterly_population_ledger.csv')}
    by = {}
    for r in raw:
        assert r['state'] in policy and r['analytic_brand'] in PRODUCTS and (r['utilization_type'] in CHANNELS) and (r['calendar_quarter'] in D11)
        assert r['calendar_quarter'] == str(int(r['year'])) + 'Q' + str(int(r['quarter'])) and r['suppressed'].lower() in ['true', 'false'] and (len(r['ndc']) == 11) and r['ndc'].isdigit()
        if r['suppressed'].lower() == 'true':
            assert r['observed'] == ''
        else:
            assert math.isfinite(float(r['observed'])) and float(r['observed']) >= 0
        by.setdefault((r['state'], r['calendar_quarter'], r['analytic_brand'], r['utilization_type']), []).append(r)
    cells = []
    mapping = {}
    source_sets = {}
    for state in sorted(policy):
        for q in D11:
            pop = population[state, q]
            N = float(pop['N_R1']) if pop['N_R1'] else math.nan
            valid = int(pop['valid_months']) >= 2 and math.isfinite(N) and (N > 0)
            for p in PRODUCTS:
                for channel in CHANNELS:
                    g = by.get((state, q, p, channel), [])
                    sup = [r for r in g if r['suppressed'].lower() == 'true']
                    obs = [r for r in g if r['suppressed'].lower() == 'false']
                    reported = sum((float(r['observed']) for r in obs))
                    mid = reported + 5.5 * len(sup) if g else None
                    status = 'SOURCE_MISSING_UNKNOWN' if not g else 'SOURCE_PRESENT_SUPPRESSED_ONLY' if len(sup) == len(g) else 'SOURCE_PRESENT_PARTIAL_SUPPRESSION' if sup else 'SOURCE_PRESENT_ALL_RECORDED_VALUES_OBSERVED'
                    ck = '|'.join([state, q, p, channel])
                    sk = sorted((sourcekey(r) for r in g))
                    source_sets[ck] = sk
                    r = {'Analysis_ID': '04D-01_DATA_AUDIT', 'Variant_ID': 'R1_SOURCE_MID_DATA11', 'state': state, 'calendar_quarter': q, 'k': int(q[:4]) * 4 + int(q[-1]) - 8098, 'period': period(q), 'product': p, 'channel': channel, 'clock': 'PAID_QUARTER' if channel == 'FFSU' else 'DISPENSE_QUARTER', 'P1_group': 'COVERAGE' if policy[state] else 'NONCOVERAGE', 'coverage': policy[state], 'source_NDC_rows': len(g), 'actually_reported_NDC_rows': len(obs), 'observed_rx': reported if g else '', 'observed_zero_NDC_rows': sum((float(x['observed']) == 0 for x in obs)), 'SUPPRESSED_NDC_rows': len(sup), 'assigned_5_5_rx': 5.5 * len(sup) if g else '', 'midpoint_y': mid if g else '', 'source_present': bool(g), 'all_recorded_quantities_observed': bool(g) and (not sup), 'verified_total_true_zero': bool(g) and (not sup) and (reported == 0), 'true_zero_evidence': 'RECORDED_ALL_OBSERVED_SOURCE_ZERO' if bool(g) and (not sup) and (reported == 0) else 'NO_VERIFIED_TRUE_ZERO; SOURCE_MISSING_OR_SUPPRESSED_NOT_ZERO', 'source_status': status, 'source_key_hash': kh(sk), 'source_key_count': len(sk), 'total_Medicaid_N_R1': N if valid else '', 'valid_months': int(pop['valid_months']), 'population_valid': valid, 'source_ledger_SHA256': sha(BW / 'raw_NDC_model_ledger.csv') if not cells else cells[0]['source_ledger_SHA256']}
                    cells.append(r)
                    mapping[state, q, p, channel] = r
            saved = [r for r in m0 if r['state'] == state and r['calendar_quarter'] == q]
            assert len(saved) == 2 and all((abs(float(r['N']) - N) <= 1e-09 for r in saved)) and all((int(r['valid_months']) == int(pop['valid_months']) for r in saved))
    assert len(cells) == 2024
    cw(OUT / '04D_A_Channel_Source_Status.csv', cells)
    jw(WORK / 'cell_source_keys.json', source_sets)
    jw(WORK / 'P1_policy.json', policy)
    decomposition = []
    for state in sorted(policy):
        for q in D11:
            for p in PRODUCTS:
                F = mapping[state, q, p, 'FFSU']
                M = mapping[state, q, p, 'MCOU']
                both = F['source_present'] and M['source_present']
                obs = F['observed_rx'] + M['observed_rx'] if both else None
                mid = F['midpoint_y'] + M['midpoint_y'] if both else None
                decomposition.append({'state': state, 'calendar_quarter': q, 'product': p, 'period': period(q), 'both_source_present': both, 'FFSU_observed_rx': F['observed_rx'], 'MCOU_observed_rx': M['observed_rx'], 'FFSU_assigned_5_5_rx': F['assigned_5_5_rx'], 'MCOU_assigned_5_5_rx': M['assigned_5_5_rx'], 'FFSU_mid_y': F['midpoint_y'], 'MCOU_mid_y': M['midpoint_y'], 'combined_observed_part_rx': obs if both else '', 'combined_midpoint_y': mid if both else '', 'all_recorded_quantities_observed': both and F['all_recorded_quantities_observed'] and M['all_recorded_quantities_observed'], 'FFSU_observed_part_share': F['observed_rx'] / obs if both and obs > 0 else '', 'FFSU_midpoint_share': F['midpoint_y'] / mid if both and mid > 0 else '', 'share_scope': 'COMMON_PRODUCT_TWO_CHANNEL_SOURCE_SUPPORT_ONLY; observed_part is not true-total share when suppressed; midpoint is scenario not enrollment', 'midpoint_identity_verified': both, 'FFSU_source_keys_hash': F['source_key_hash'], 'MCOU_source_keys_hash': M['source_key_hash']})
    cw(OUT / '04D_A_Channel_Count_Decomposition.csv', decomposition)
    pairrows = []
    group = []
    variants = []
    comparisons = []
    for window, quarters in [('DATA-11', D11), ('DATA-C10', C10)]:
        selected = {}
        models = {}
        for support in SETS:
            chosen = []
            model = []
            required = [(p, support[3:]) for p in PRODUCTS] if support in ['CH-FFSU', 'CH-MCOU'] else [(p, c) for p in (['WEGOVY'] if support == 'CH-WONLY' else PRODUCTS) for c in CHANNELS]
            for state in sorted(policy):
                for q in quarters:
                    cs = [mapping[state, q, p, c] for p, c in required]
                    valid = all((x['source_present'] for x in cs)) and cs[0]['population_valid']
                    missing = [':'.join([p, c]) for p, c in required if not mapping[state, q, p, c]['source_present']]
                    pairrows.append({'Analysis_ID': '04D-01_SOURCE_SUPPORT' if support != 'CH-WONLY' else '04D-A_DESCRIPTIVE_SUPPORT_ONLY', 'Variant_ID': support + '_' + window, 'support': support, 'window': window, 'state': state, 'calendar_quarter': q, 'period': period(q), 'P1_group': 'COVERAGE' if policy[state] else 'NONCOVERAGE', 'included': valid, 'required_cells': len(cs), 'source_present_cells': sum((x['source_present'] for x in cs)), 'missing_cells': ';'.join(missing), 'population_valid': cs[0]['population_valid'], 'reason': 'SOURCE_PRESENT_PAIRED_WITH_SUPPRESSION_SCENARIO' if valid else 'UNKNOWN_SOURCE_MISSING_KEEP_NA' if missing else 'INVALID_R1_POPULATION', 'source_NDC_rows': sum((x['source_NDC_rows'] for x in cs)), 'actually_reported_NDC_rows': sum((x['actually_reported_NDC_rows'] for x in cs)), 'SUPPRESSED_NDC_rows': sum((x['SUPPRESSED_NDC_rows'] for x in cs))})
                    if not valid:
                        continue
                    chosen.append(state + '|' + q)
                    for p in ['WEGOVY'] if support == 'CH-WONLY' else PRODUCTS:
                        used = [mapping[state, q, p, c] for c in (CHANNELS if support in ['CH-BOTH', 'CH-WONLY'] else [support[3:]])]
                        N = used[0]['total_Medicaid_N_R1']
                        model.append({'state': state, 'calendar_quarter': q, 'quarter_index': int(q[:4]) * 4 + int(q[-1]), 'k': int(q[:4]) * 4 + int(q[-1]) - 8098, 'period': period(q), 'product': p, 'coverage': policy[state], 'noncoverage': 1 - policy[state], 'W': int(p == 'WEGOVY'), 'Post': int(q >= '2024Q2'), 'N_R1_total_Medicaid': N, 'offset': math.log(N), 'observed_rx': sum((x['observed_rx'] for x in used)), 'assigned_5_5_rx': sum((x['assigned_5_5_rx'] for x in used)), 'y_mid': sum((x['midpoint_y'] for x in used)), 'observed_NDC_rows': sum((x['actually_reported_NDC_rows'] for x in used)), 'suppressed_NDC_rows': sum((x['SUPPRESSED_NDC_rows'] for x in used)), 'source_key_hash': kh(sorted((k for x in used for k in source_sets['|'.join([state, q, p, x['channel']])])))})
            selected[support] = set(chosen)
            models[support] = model
            name = support.replace('-', '_') + '_' + window.replace('-', '_')
            cw(WORK / (name + '_model_input.csv'), model)
            cw(WORK / (name + '_pair_keys.csv'), [{'state_quarter_key': k} for k in chosen])
            vv = {'Analysis_ID': '04D-01/02_PRECHECK' if support != 'CH-WONLY' else '04D-A_DESCRIPTIVE', 'Variant_ID': name, 'support': support, 'window': window, 'requested_states': 46, 'requested_state_quarters': 46 * len(quarters), 'included_state_quarters': len(chosen), 'product_observation_rows': len(model), 'DDD_model_rows': 0 if support == 'CH-WONLY' else len(model), **info(model), 'source_ledger_SHA256': cells[0]['source_ledger_SHA256'], 'population_ledger_SHA256': sha(BW / 'quarterly_population_ledger.csv'), 'input_csv_SHA256': sha(WORK / (name + '_model_input.csv')), 'state_quarter_key_hash': kh(sorted(chosen)), 'model_input_hash': kh((key(r) + '|' + '|'.join((f17(r[c]) for c in ['y_mid', 'N_R1_total_Medicaid', 'offset', 'coverage', 'noncoverage', 'W', 'Post', 'quarter_index'])) for r in model)), 'result_type': 'DATA_SUPPORT_AND_STRUCTURAL_AUDIT_NO_ESTIMATE', 'handling': 'R1; present-source only; suppression5.5; missing NA; Q1 transition never clean pre'}
            variants.append(vv)
            for q in quarters:
                for coverage in [0, 1]:
                    f = [r for r in model if r['calendar_quarter'] == q and r['coverage'] == coverage]
                    states = sorted({r['state'] for r in f})
                    group.append({'Variant_ID': name, 'support': support, 'window': window, 'calendar_quarter': q, 'period': period(q), 'group': 'COVERAGE' if coverage else 'NONCOVERAGE', 'states': ';'.join(states), 'G': len(states), 'state_quarters': len(states), 'product_rows': len(f), 'observed_NDC_rows': sum((r['observed_NDC_rows'] for r in f)), 'SUPPRESSED_NDC_rows': sum((r['suppressed_NDC_rows'] for r in f)), 'observed_rx': sum((r['observed_rx'] for r in f)), 'assigned_5_5_rx': sum((r['assigned_5_5_rx'] for r in f)), 'state_quarter_key_hash': kh((state + '|' + q for state in states))})
        assert selected['CH-BOTH'] == selected['CH-FFSU'] & selected['CH-MCOU']
        baseline = selected['CH-BOTH']
        for support in SETS:
            union = selected[support]
            intersection = union & baseline
            added = union - baseline
            absent = baseline - union
            comparisons.append({'window': window, 'support': support, 'unit': 'STATE_QUARTER_PAIR; WONLY IS NOT SAME DDD TARGET', 'native_pairs': len(union), 'CH_BOTH_pairs': len(baseline), 'intersection_pairs': len(intersection), 'native_only_pairs': len(added), 'CH_BOTH_only_pairs': len(absent), 'native_key_hash': kh(sorted(union)), 'intersection_key_hash': kh(sorted(intersection)), 'native_only_key_hash': kh(sorted(added)), 'CH_BOTH_only_key_hash': kh(sorted(absent)), 'comparison_status': 'REQUESTED_SOURCE_SUPPORT_INTERSECTION_ONLY; NO_FORMAL_SEPARATION_COMMON_OR_ESTIMATES'})
            jw(WORK / (support.replace('-', '_') + '_' + window.replace('-', '_') + '_support_differences.json'), {'intersection': sorted(intersection), 'native_only': sorted(added), 'CH_BOTH_only': sorted(absent)})
        if window == 'DATA-C10':
            assert baseline == {r['state'] + '|' + r['calendar_quarter'] for r in rc(CA / '04C_A_Model_Sample.csv')}
        else:
            assert baseline == {r['state'] + '|' + r['calendar_quarter'] for r in rc(B / '04B_M0_M1_Pair_Support.csv') if r['M1_pair_reportable'] == 'True'}
    for support, counts in [('CH-FFSU', [2, 2, 2]), ('CH-MCOU', [15, 19, 17]), ('CH-BOTH', [0, 1, 1])]:
        actual = [next((r['G'] for r in group if r['support'] == support and r['window'] == 'DATA-C10' and (r['group'] == 'NONCOVERAGE') and (r['calendar_quarter'] == q))) for q in C10[:3]]
        assert actual == counts, 'EXPECTED_SUPPORT_MISMATCH_STOP'
    cw(OUT / '04D_A_Channel_Paired_Support.csv', pairrows)
    cw(OUT / '04D_A_Group_Quarter_Channel_Support.csv', group)
    cw(OUT / '04D_A_Common_vs_Native_Support.csv', comparisons)
    cw(OUT / '04D_A_Variant_Manifest.csv', variants)
    jw(WORK / 'variants.json', variants)
    suppression = []
    for channel in CHANNELS:
        for p in PRODUCTS:
            for q in D11:
                for coverage in [0, 1]:
                    f = [r for r in cells if r['channel'] == channel and r['product'] == p and (r['calendar_quarter'] == q) and (r['coverage'] == coverage)]
                    suppression.append({'channel': channel, 'product': p, 'calendar_quarter': q, 'period': period(q), 'group': 'COVERAGE' if coverage else 'NONCOVERAGE', 'requested_cells': len(f), 'present_source_cells': sum((r['source_present'] for r in f)), 'missing_unknown_cells': sum((not r['source_present'] for r in f)), 'any_suppressed_cells': sum((r['SUPPRESSED_NDC_rows'] > 0 for r in f)), 'all_suppressed_source_cells': sum((r['source_status'] == 'SOURCE_PRESENT_SUPPRESSED_ONLY' for r in f)), 'all_recorded_values_observed_cells': sum((r['all_recorded_quantities_observed'] for r in f)), 'verified_true_zero_cells': sum((r['verified_total_true_zero'] for r in f)), 'observed_NDC_rows': sum((r['actually_reported_NDC_rows'] for r in f)), 'SUPPRESSED_NDC_rows': sum((r['SUPPRESSED_NDC_rows'] for r in f)), 'secondary_suppression_upper_bound': 'NOT_VERIFIABLE; not all<=10'})
    cw(OUT / '04D_A_Suppression_and_Missingness.csv', suppression)
    import pandas as pd
    df = pd.read_csv(safe(BW / 'raw_NDC_model_ledger.csv'), dtype={'ndc': str}, float_precision='round_trip')
    df['is_sup'] = df.suppressed.astype(str).str.lower().eq('true')
    df['obs'] = df.observed.where(~df.is_sup, 0)
    other = df.groupby(['state', 'calendar_quarter', 'analytic_brand', 'utilization_type']).agg(source_n=('ndc', 'size'), sup_n=('is_sup', 'sum'), observed=('obs', 'sum'))
    for cell in cells:
        k = (cell['state'], cell['calendar_quarter'], cell['product'], cell['channel'])
        if k in other.index:
            t = other.loc[k]
            assert int(t.source_n) == cell['source_NDC_rows'] and int(t.sup_n) == cell['SUPPRESSED_NDC_rows'] and (float(t.observed) == cell['observed_rx'])
        else:
            assert not cell['source_present'] and cell['midpoint_y'] == ''
    jw(WORK / 'aggregation_QA.json', {'status': 'PASS', 'source_rows': len(raw), 'source_keys_unique': True, 'source_key_hash': kh(sorted((sourcekey(r) for r in raw))), 'raw_ledger_SHA256': cells[0]['source_ledger_SHA256'], 'grid_cells': len(cells), 'missing_cells': sum((not r['source_present'] for r in cells)), 'observed_true_zero_cells': sum((r['verified_total_true_zero'] for r in cells)), 'manual_vs_pandas_groupby': 'ALL_PRESENT_CELLS_EQUAL', 'CH_BOTH_DATA11_vs_B': 'EXACT_PAIR_KEYS', 'CH_BOTH_C10_vs_CA': 'EXACT_PAIR_KEYS', 'expected_pre_presence': 'MATCHED_WITHOUT_DATA_CHANGE', 'models_fitted': 0})
    seal('aggregate', {'variants': 8, 'raw_source_rows': len(raw), 'cells': len(cells), 'QA_SHA256': sha(WORK / 'aggregation_QA.json')})
    print('AGGREGATE PASS', [(v['support'], v['window'], v['n'], v['G']) for v in variants], flush=True)

def numeric_imports():
    global np, la
    import numpy as np
    from scipy import linalg as la
    prior = jr(CA / '_working/environment_gate.json')['packages']
    assert all((metadata.version(k) == v for k, v in prior.items()))
    assert sys.executable.lower() == str(ROOT / '.venv_stage04a/Scripts/python.exe').lower()
    jw(WORK / 'environment.json', {'interpreter': sys.executable, 'installed_versions_exactly_match_CA': True, 'numpy': metadata.version('numpy'), 'scipy': metadata.version('scipy'), 'statsmodels_imported': any((s.startswith('statsmodels') for s in sys.modules)), 'original_environment': 'NOT_VERIFIABLE; approved independent environment used'})

def rank(X):
    c = np.maximum(1, np.max(np.abs(X), axis=0))
    A = X / c
    s = la.svdvals(A)
    tau = max(X.shape) * np.finfo(float).eps * s[0]
    svd = int((s > tau).sum())
    Q, R, piv = la.qr(A, mode='economic', pivoting=True)
    qr = int((np.abs(np.diag(R)) > tau).sum())
    ranks = [int((s > tau * t).sum()) for t in [0.1, 1, 10]]
    assert svd == qr and len(set(ranks)) == 1, 'Rank ambiguity STOP'
    return {'rank': svd, 'QR_rank': qr, 'threshold': float(tau), 'rank_tau_0_1': ranks[0], 'rank_tau_10': ranks[2], 'spectrum': s.tolist(), 'condition_identified': float(s[0] / s[svd - 1])}

def design(rows, kind):
    sp = [r['state'] + ':' + r['product'] for r in rows]
    qs = [r['calendar_quarter'] for r in rows]
    cols = [np.ones(len(rows))]
    names = ['Intercept']
    for v in sorted(set(sp))[1:]:
        cols.append(np.array([s == v for s in sp]))
        names.append('SP:' + v)
    for v in sorted(set(qs))[1:]:
        cols.append(np.array([q == v for q in qs]))
        names.append('Q:' + v)
    W = np.array([int(r['W']) for r in rows])
    NC = np.array([int(r['noncoverage']) for r in rows])
    tt = [('Post', np.array([int(r['Post']) for r in rows]))] if kind == 'F0' else [('Early', np.array([q == '2024Q2' for q in qs])), ('Late', np.array([q >= '2024Q3' for q in qs]))]
    for tag, T in tt:
        for n, c in [('W', T * W), ('NC', T * NC), ('DDD', T * W * NC)]:
            cols.append(c)
            names.append(tag + '×' + n)
    return (np.column_stack(cols).astype(float), names)

def xhash(X):
    return th(str(X.shape) + '|' + str(X.dtype) + '|' + ','.join((f17(x) for x in X.ravel())))

def diag(rows, variant, kind, save=True):
    X, names = design(rows, kind)
    rr = rank(X)
    targets = []
    for j, name in enumerate(names):
        if not name.endswith('×DDD'):
            continue
        other = np.delete(X, j, axis=1)
        without = rank(other)
        scale = np.maximum(1, np.max(np.abs(X), axis=0))
        A = X / scale
        U, s, V = la.svd(np.delete(A, j, axis=1), full_matrices=False)
        tau = max(other.shape) * np.finfo(float).eps * s[0]
        basis = U[:, s > tau]
        res = A[:, j] - basis @ (basis.T @ A[:, j])
        ok = rr['rank'] == without['rank'] + 1
        targets.append({'Analysis_ID': '04D-01' if kind == 'F0' else '04D-02', 'Variant_ID': variant, 'design': kind, 'target': name, **info(rows), 'design_columns': len(names), 'rank': rr['rank'], 'rank_without_target': without['rank'], 'target_identifiable': ok, 'target_residual_norm': float(la.norm(res)), 'reason': 'ESTIMABLE_COLUMN_SPACE_ONLY' if ok else 'COLUMN_ALL_ZERO' if not np.any(X[:, j]) else 'ABSORBED_BY_OTHER_COLUMNS', 'QR_rank': rr['QR_rank'], 'rank_tau_0_1': rr['rank_tau_0_1'], 'rank_tau_10': rr['rank_tau_10'], 'structural_status': 'PASS' if ok else 'NOT_IDENTIFIABLE', 'can_enter_future_separation_solver_gate': ok and info(rows)['coverage_G'] >= 2 and (info(rows)['noncoverage_G'] >= 2), 'G_SEPARATION': 'NOT_EXECUTED', 'G_SOLVER': 'NOT_EXECUTED', 'G_COV': 'NOT_EXECUTED', 'X_hash': xhash(X), 'names_hash': kh(names)})
        if save:
            for axis in ['state', 'calendar_quarter']:
                for level in sorted({r[axis] for r in rows}):
                    mask = np.array([r[axis] == level for r in rows])
                    part = float(np.sum(res[mask] ** 2))
                    total = float(np.sum(res ** 2))
                    CONCENTRATION.append({'Variant_ID': variant, 'target': name, 'axis': axis, 'level': level, 'model_rows': int(mask.sum()), 'target_residual_squared_share': part / total if ok else '', 'interpretation': 'UNWEIGHTED_DESIGN_RESIDUAL_CONCENTRATION_ONLY; NOT_PPML_SCORE_OR_CAUSAL_INFLUENCE', 'status': 'STRUCTURAL_DESCRIPTOR' if ok else 'NOT_APPLICABLE_TARGET_ABSORBED'})
    if save:
        np.savez_compressed(target(WORK / (variant + '_design.npz')), X=X, names=np.array(names), keys=np.array([key(r) for r in rows]))
        jw(WORK / (variant + '_diagnostics.json'), {'targets': targets, 'rank_details': rr, 'names': names, 'full_matrix_SHA256': sha(WORK / (variant + '_design.npz'))})
    return targets

def structure():
    global CONCENTRATION
    CONCENTRATION = []
    numeric_imports()
    assert jr(WORK / 'aggregate_complete.json')['status'] == 'COMPLETE_VERIFIED'
    vv = jr(WORK / 'variants.json')
    models = {}
    pre = []
    ident = []
    loo = []
    for support in ['CH-FFSU', 'CH-MCOU', 'CH-BOTH']:
        v = next((v for v in vv if v['support'] == support and v['window'] == 'DATA-C10'))
        p = WORK / (v['Variant_ID'] + '_model_input.csv')
        assert sha(p) == v['input_csv_SHA256']
        rows = rc(p)
        models[support] = rows
        assert len({key(r) for r in rows}) == len(rows) and len(rows) == 2 * len({r['state'] + '|' + r['calendar_quarter'] for r in rows})
        for r in rows:
            assert r['calendar_quarter'] in C10 and int(r['k']) == int(r['quarter_index']) - 8098 and (int(r['Post']) == int(r['calendar_quarter'] >= '2024Q2')) and (float(r['N_R1_total_Medicaid']) > 0) and (abs(math.log(float(r['N_R1_total_Medicaid'])) - float(r['offset'])) < 3e-14)
        for state in sorted({r['state'] for r in rows if r['period'] == 'PRE'}):
            for product in PRODUCTS:
                f = [r for r in rows if r['state'] == state and r['period'] == 'PRE' and (r['product'] == product)]
                pre.append({'support': support, 'state': state, 'group': 'COVERAGE' if int(f[0]['coverage']) else 'NONCOVERAGE', 'product': product, 'pre_quarters': ';'.join((r['calendar_quarter'] for r in f)), 'model_n': len(f), 'observed_NDC_rows': sum((int(r['observed_NDC_rows']) for r in f)), 'suppressed_NDC_rows': sum((int(r['suppressed_NDC_rows']) for r in f)), 'observed_rx': sum((float(r['observed_rx']) for r in f)), 'assigned_5_5_rx': sum((float(r['assigned_5_5_rx']) for r in f)), 'all_pre_quantity_from_assignment': all((float(r['observed_rx']) == 0 for r in f)), 'sample_key_hash': kh(sorted((key(r) for r in f)))})
        for kind in ['F0', 'EL1']:
            ident += diag(rows, support.replace('-', '_') + '_NATIVE_' + kind, kind)
    common_pairs = {r['state'] + '|' + r['calendar_quarter'] for r in models['CH-BOTH']}
    for support in ['CH-FFSU', 'CH-MCOU']:
        rows = [r for r in models[support] if r['state'] + '|' + r['calendar_quarter'] in common_pairs]
        for kind in ['F0', 'EL1']:
            ident += diag(rows, support.replace('-', '_') + '_CH_BOTH_SUPPORT_' + kind, kind)
    for support, rows in models.items():
        for state in sorted(jr(WORK / 'P1_policy.json')):
            retained = [r for r in rows if r['state'] != state]
            record = diag(retained, support + '_WITHOUT_' + state, 'F0', False)[0]
            loo.append({'support': support, 'removed_state': state, 'removed_native_product_rows': len(rows) - len(retained), 'remaining_n': record['n'], 'remaining_G': record['G'], 'remaining_coverage_G': record['coverage_G'], 'remaining_noncoverage_G': record['noncoverage_G'], 'rank': record['rank'], 'design_columns': record['design_columns'], 'rank_without_target': record['rank_without_target'], 'target_identifiable': record['target_identifiable'], 'failure_reason': '' if record['target_identifiable'] else record['reason'], 'sample_key_hash': record['model_key_hash'], 'numeric_LOO_executed': False})
    cw(OUT / '04D_A_F0_EL1_Identifiability.csv', ident)
    cw(OUT / '04D_A_State_Influence_Structural_Precheck.csv', loo)
    cw(OUT / '04D_A_Preperiod_State_Information.csv', pre)
    cw(OUT / '04D_A_Structural_Target_Concentration.csv', CONCENTRATION)
    jw(WORK / 'structure_summary.json', {'status': 'PASS_EXECUTION', 'identifiability_rows': ident, 'LOO_requested_states_per_support': 46, 'LOO_matrix_rows': len(loo), 'LOO_not_identifiable': [{k: r[k] for k in ['support', 'removed_state', 'remaining_n', 'rank', 'rank_without_target']} for r in loo if not r['target_identifiable']], 'new_regression_fits': 0, 'new_effect_or_significance_values': 0})
    seal('structure', {'model_design_target_rows': len(ident), 'LOO_matrix_rows': len(loo), 'identifiability_csv_SHA256': sha(OUT / '04D_A_F0_EL1_Identifiability.csv')})
    print('STRUCTURE COMPLETE', [(r['Variant_ID'], r['target'], r['n'], r['rank'], r['design_columns'], r['target_identifiable']) for r in ident], flush=True)
if __name__ == '__main__':
    {'intake': intake, 'aggregate': aggregate, 'structure': structure}[sys.argv[1]]()
