"""Stage04C-A only. Independent inputs, diagnostics, one authorized binary fit.
Prior research files read only. Phases run explicitly; no research IO on import.
"""
import csv, hashlib, json, os, stat, sys, zipfile, shutil, platform, subprocess, math, traceback
from pathlib import Path
ROOT = Path(__file__).absolute().parents[2]
CODE = ROOT / '02_audit_code/Stage04C_A'
OUT = ROOT / '03_audit_outputs/Stage04C_A'
WORK = OUT / '_working'
B = ROOT / '03_audit_outputs/Stage04B'
BW = B / '_working/R1'
C10 = ['2023Q2', '2023Q3', '2023Q4', '2024Q2', '2024Q3', '2024Q4', '2025Q1', '2025Q2', '2025Q3', '2025Q4']
REQUEST = Path('external_resources/已粘贴的文本.txt')

def safe(p):
    p = Path(p).absolute()
    for q in [p, *p.parents]:
        if os.path.lexists(q):
            s = q.lstat()
            assert not (stat.S_ISLNK(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 1024), f'reparse blocked {q}'
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

def f17(x):
    return format(float(x), '.17g')

def jr(p):
    return json.loads(safe(p).read_text(encoding='utf-8-sig'))

def jw(p, x):
    target(p).write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

def rc(p):
    with safe(p).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def cw(p, rows):
    assert rows, 'Nonempty audit CSV required'
    fields = list(dict.fromkeys((k for r in rows for k in r)))
    with target(p).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def md(name, text):
    target(OUT / name).write_text(text.strip() + '\n', encoding='utf-8')

def files(d):
    for p in sorted(safe(d).iterdir()):
        if p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 1024:
            continue
        if p.is_dir():
            yield from files(p)
        elif p.is_file():
            yield p

def jsonable(x):
    if isinstance(x, dict):
        return {k: jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if hasattr(x, 'tolist'):
        return jsonable(x.tolist())
    if isinstance(x, float) and (not math.isfinite(x)):
        return 'NONFINITE_' + str(x).upper()
    return x

def checkpoint(phase, details):
    jw(WORK / (phase + '_complete.json'), {'phase': phase, 'status': 'COMPLETE_VERIFIED', 'details': details, 'code_sha': sha(CODE / 'audit.py'), 'core_sha': sha(CODE / 'stat_core.py')})

def intake():
    assert not (WORK / 'intake_complete.json').exists(), 'Do not replace completed intake'
    authorities = [ROOT / 'AGENTS.md', ROOT / 'PROJECT_CHARTER.md', ROOT / '03_audit_outputs/Issue_Register.csv', REQUEST]
    s3 = ['Stage04_Protocol_Lock.csv', 'Stage04_Execution_Plan.md', 'Event_Time_Adjudication.md', 'Parallel_Trend_Protocol.md', 'Fixed_Effect_Alternatives.md', 'Stage04_Decision_Gates.md', 'Model_Failure_Stop_Rules.md', 'Cluster_Inference_Plan.md']
    authorities += [ROOT / '03_audit_outputs/Stage03' / ('03_' + n) for n in s3]
    authorities += [ROOT / '03_audit_outputs/Stage04A_R3C' / ('04A_R3C_' + n) for n in ['Executive_Report.md', 'Independent_PPML_Results.csv', 'Model_Gates.csv', 'Model_Input_Hashes.json']]
    authorities += [B / ('04B_' + n) for n in ['Model_Results.csv', 'Model_Gates.csv', 'M0_M1_Pair_Support.csv', 'Requested_Effective_Support_Audit.csv', 'Group_Product_PrePost_Support.csv', 'COMMON_Comparison_Status.csv', 'Source_Suppression_Scenarios.csv', 'R1_Quality_Assurance.md', 'R1_Numerical_QA.json', 'Stage04C_Readiness.md', 'Negative_and_Failed_Results.md']]
    for p in authorities:
        assert safe(p).is_file(), f'BLOCKED missing authority {p}'
        p.read_text(encoding='utf-8-sig')
    protected = set(authorities)
    for d in ['03_audit_outputs/Stage04A_R3C', '03_audit_outputs/Stage04B', '02_audit_code/Stage04A_R3C', '02_audit_code/Stage04B']:
        protected.update(files(ROOT / d))
    gate = jr(BW / 'input_gate.json')
    assert gate['G_DATA'] == 'PASS'
    for r in gate['source_sha']:
        p = safe(r['Path'])
        assert sha(p) == r['SHA256'], f'Source drift {p}'
        protected.add(p)
    vm = jr(BW / 'variant_manifest.json')
    for v in vm:
        if v['Variant_ID'] in ['R1_M1_MID', 'R1_M0_MID']:
            assert sha(v['input_csv']) == v['input_csv_sha']
    inventory = {r['Path']: r for r in rc(B / '04B_R1_File_Inventory.csv')}
    for p in [BW / 'raw_NDC_model_ledger.csv', BW / 'quarterly_population_ledger.csv']:
        assert sha(p) == inventory[str(p)]['SHA256'], f'Ledger drift {p}'
    for p in [ROOT / 'feedback/Medicaid_Wegovy_Stage04B_R1_Feedback.zip']:
        assert safe(p).exists()
        with zipfile.ZipFile(p) as z:
            assert z.testzip() is None
        protected.add(p)
    snapshot = [{'path': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size, 'authority': p in authorities} for p in sorted(protected)]
    jw(WORK / 'protected_before.json', snapshot)
    jw(WORK / 'frozen_plan.json', {'request_sha': sha(REQUEST), 'C10': C10, 'k_rule': 'year*4+quarter - (2024*4+2)', 'event_reference': '2023Q4 k=-2', 'primary': 'R1/M1/S5.5/P1_46/F0; post >=2024Q2', 'event_families': {'EV_CLEAN': [-4, -3, 0, 1, 2, 3, 4, 5, 6], 'EV_TRANS': [-4, -3, -1, 0, 1, 2, 3, 4, 5, 6]}, 'fit_only': 'PRIMARY_BINARY_CLEAN', 'M0': 'SUPPORT_AND_IDENTIFIABILITY_ONLY', 'COMMON': 'fresh native effective key intersection plus certified separation union; max10 iterations', 'single_pre_state': 'MAJOR_CAUTION_NOT_AUTOMATIC_TARGET_FAIL', 'core_lineage': 'Stage04B/R1 stat_core byte-identical', 'thresholds': {'score': 1e-08, 'last_five_deviance': 1e-10, 'iterations_strictly_less': 1000, 'symmetry': 1e-10, 'scaled_PSD': 1e-10}, 'start_tolerances': [{'start': 'exposure', 'tol': 1e-10}, {'start': 'zeros', 'tol': 1e-10}, {'start': 'exposure', 'tol': 1e-12}]})
    assert sha(CODE / 'stat_core.py') == sha(ROOT / '02_audit_code/Stage04B/R1/stat_core.py')
    checkpoint('intake', {'protected_files': len(snapshot), 'source_files_verified': len(gate['source_sha']), 'authority_files': len(authorities)})
    print('INTAKE PASS', len(snapshot), flush=True)

def imports():
    global np, pd, sc, linalg, stats
    import numpy as np
    import pandas as pd
    import stat_core as sc
    from scipy import linalg, stats

def keys(f):
    return (f.state + '|' + f.calendar_quarter + '|' + f.analytic_brand).tolist()

def datahash(f):
    fields = ['y', 'N', 'offset', 'coverage_2024', 'noncoverage_2024', 'obesity', 'post', 'quarter_index']
    return kh((k + '|' + '|'.join((f17(r[c]) for c in fields)) for k, (_, r) in zip(keys(f), f.iterrows())))

def frameinfo(f):
    return {'n': len(f), 'G': int(f.state.nunique()), 'coverage_G': int(f.loc[f.coverage_2024 == 1, 'state'].nunique()), 'noncoverage_G': int(f.loc[f.coverage_2024 == 0, 'state'].nunique()), 'keys_hash': kh(sorted(keys(f))), 'order_hash': kh(keys(f)), 'input_hash': datahash(f), 'quarters': sorted(f.calendar_quarter.unique().tolist())}

def writeframe(f, name):
    p = target(WORK / (name + '.csv'))
    f.to_csv(p, index=False, float_format='%.17g')
    return sha(p)

def readframe(name):
    p = safe(WORK / (name + '.csv'))
    f = pd.read_csv(p, float_precision='round_trip')
    if name.endswith('_requested'):
        variant = name[:-10]
        v = next((v for v in jr(WORK / 'variant_manifest.json') if v['Variant_ID'] == variant))
        assert sha(p) == v['derived_requested_csv_sha'] and datahash(f) == v['input_hash']
        assert kh(sorted(keys(f))) == v['keys_hash'] and kh(keys(f)) == v['order_hash']
    return f

def support():
    imports()
    assert (WORK / 'intake_complete.json').exists()
    import importlib.metadata as meta
    packages = list(jr(BW / 'environment_gate.json')['installed'])
    versions = {p: meta.version(p) for p in packages}
    assert versions == jr(BW / 'environment_gate.json')['installed'], 'Environment changed since B'
    assert all((not meta.version(p).lower().endswith('dev') and (not __import__('packaging.version', fromlist=['Version']).Version(meta.version(p)).is_prerelease) for p in packages))
    pipe = subprocess.run([sys.executable, '-B', '-m', 'pip', 'check'], capture_output=True, text=True)
    assert pipe.returncode == 0, pipe.stdout + pipe.stderr
    assert sys.executable.lower() == str(ROOT / '.venv_stage04a/Scripts/python.exe').lower()
    assert sc.target_estimable(np.array([[1.0, 0], [1, 1], [1, 2]]), 1)
    assert not sc.target_estimable(np.array([[1.0, 1], [1, 1], [1, 1]]), 1)
    jw(WORK / 'environment_gate.json', {'G_ENV': 'PASS', 'python': sys.executable, 'version': platform.python_version(), 'packages': versions, 'pip_check': pipe.stdout.strip(), 'core_sha': sha(CODE / 'stat_core.py'), 'rank_microcheck': 'PASS'})
    vm = jr(BW / 'variant_manifest.json')
    bframes = {}
    for v in vm:
        if v['Variant_ID'] in ['R1_M1_MID', 'R1_M0_MID']:
            f = pd.read_csv(safe(v['input_csv']), float_precision='round_trip')
            assert datahash(f) == v['requested_data_hash']
            assert kh(sorted(keys(f))) == v['requested_keys_hash']
            bframes[v['Variant_ID']] = f
    m0 = bframes['R1_M0_MID']
    m1 = bframes['R1_M1_MID']
    assert len(m0) == 1012 and m0.state.nunique() == 46
    policy = m0.groupby('state').coverage_2024.first()
    assert int(policy.sum()) == 12 and len(policy) == 46
    raw = pd.read_csv(safe(BW / 'raw_NDC_model_ledger.csv'), dtype={'ndc': str}, float_precision='round_trip')
    sup = raw.suppressed.astype(str).str.lower().eq('true')
    raw['assigned_y'] = raw.observed.where(~sup, 5.5)
    assignment = kh(('|'.join([r.source_file, str(r.source_row), r.state, r.calendar_quarter, r.ndc, r.utilization_type, f17(r.assigned_y)]) for r in raw.itertuples()))
    assert assignment == '70d375008fab37dc085746b703c9dcbfa797ca1b77d38e116bf4e9226aa89f16'
    aggregated = raw.groupby(['state', 'calendar_quarter', 'analytic_brand']).assigned_y.sum()
    for r in m0.itertuples():
        assert float(aggregated.get((r.state, r.calendar_quarter, r.analytic_brand), 0)) == r.y
    assert (m0.N > 0).all() and np.max(np.abs(np.log(m0.N) - m0.offset)) < 3e-14
    sources = {}
    for key, g in raw.groupby(['state', 'calendar_quarter', 'analytic_brand', 'utilization_type']):
        s = g.suppressed.astype(str).str.lower().eq('true')
        o = g.loc[~s, 'observed']
        sources[key] = {'source_NDC_rows': len(g), 'actually_reported_NDC_rows': len(o), 'observed_positive_NDC_rows': int((o > 0).sum()), 'observed_zero_NDC_rows': int((o == 0).sum()), 'suppressed_NDC_rows': int(s.sum()), 'observed_rx_sum': float(o.sum()), 'suppression_assigned_rx': 5.5 * int(s.sum()), 'midpoint_channel_rx': float(g.assigned_y.sum())}
    bpair = {(r['state'], r['calendar_quarter']): r for r in rc(B / '04B_M0_M1_Pair_Support.csv')}
    supportrows = []
    exclusions = []
    cleanpairs = set()
    for state in sorted(policy.index):
        for q in C10:
            cells = [sources.get((state, q, p, c), {}) for p in ['OZEMPIC', 'WEGOVY'] for c in ['FFSU', 'MCOU']]
            paired = all((x.get('source_NDC_rows', 0) > 0 for x in cells))
            assert paired == (bpair[state, q]['M1_pair_reportable'] == 'True')
            if paired:
                cleanpairs.add((state, q))
            else:
                exclusions.append({'state': state, 'calendar_quarter': q, 'group': 'COVERAGE' if policy[state] else 'NONCOVERAGE', 'reason': 'UNKNOWN_CHANNEL_MISSING; EXCLUDE_BOTH_PRODUCTS', 'missing_channels': ';'.join((p + ':' + c for p in ['OZEMPIC', 'WEGOVY'] for c in ['FFSU', 'MCOU'] if (state, q, p, c) not in sources))})
            for p in ['OZEMPIC', 'WEGOVY']:
                for c in ['FFSU', 'MCOU']:
                    x = sources.get((state, q, p, c))
                    supportrows.append({'state': state, 'calendar_quarter': q, 'k': int(q[:4]) * 4 + int(q[-1]) - 8098, 'group': 'COVERAGE' if policy[state] else 'NONCOVERAGE', 'product': p, 'channel': c, 'source_status': 'REPORTED_SOURCE' if x else 'UNKNOWN_CHANNEL_MISSING_NA', 'M1_complete_pair': paired, **(x or {k: 0 if k.endswith('rows') else '' for k in ['source_NDC_rows', 'actually_reported_NDC_rows', 'observed_positive_NDC_rows', 'observed_zero_NDC_rows', 'suppressed_NDC_rows', 'observed_rx_sum', 'suppression_assigned_rx', 'midpoint_channel_rx']})})
    cw(OUT / '04C_A_Channel_Reportability.csv', supportrows)
    cw(OUT / '04C_A_Excluded_State_Quarters.csv', exclusions)
    specs = {'PRIMARY_BINARY_CLEAN': m1[m1.calendar_quarter.isin(C10)].copy(), 'EV_CLEAN': m1[m1.calendar_quarter.isin(C10)].copy(), 'EV_TRANS': m1.copy(), 'M0_CLEAN_REFERENCE': m0[m0.calendar_quarter.isin(C10)].copy()}
    manifests = []
    for name, f in specs.items():
        f['post'] = (f.quarter_index >= 8098).astype(int)
        f['k'] = f.quarter_index - 8098
        assert all(f.quarter_index == f.year * 4 + f.quarter)
        assert f.k.tolist() == [int(q[:4]) * 4 + int(q[-1]) - 8098 for q in f.calendar_quarter]
        if name != 'EV_TRANS':
            assert set(f.calendar_quarter).issubset(set(C10)) and '2024Q1' not in set(f.calendar_quarter)
        if name != 'M0_CLEAN_REFERENCE':
            assert set(zip(f.state, f.calendar_quarter)) == (cleanpairs if name != 'EV_TRANS' else set(zip(m1.state, m1.calendar_quarter)))
        for col in ['source_NDC_rows', 'actually_reported_NDC_rows', 'observed_positive_NDC_rows', 'observed_zero_NDC_rows', 'suppressed_NDC_rows', 'observed_rx_sum', 'suppression_assigned_rx']:
            f[col] = [sum((sources.get((r.state, r.calendar_quarter, r.analytic_brand, c), {}).get(col, 0) for c in ['FFSU', 'MCOU'])) for r in f.itertuples()]
        assert np.array_equal(f.y.to_numpy(), (f.observed_rx_sum + f.suppression_assigned_rx).to_numpy())
        manifests.append({'Variant_ID': name, 'R': 'R1', 'M': 'M0' if name == 'M0_CLEAN_REFERENCE' else 'M1', 'S': 'SOURCE_SUPPRESSED_5.5', 'P': 'P1_46_12_34', 'F': 'F0_BINARY' if name in ['PRIMARY_BINARY_CLEAN', 'M0_CLEAN_REFERENCE'] else 'F0_EVENT_FULL_FAMILY', 'DATA_window': 'DATA-11' if name == 'EV_TRANS' else 'DATA-C10', 'quarter_set': ';'.join(sorted(f.calendar_quarter.unique())), 'source_assignment_sha': assignment, 'source_input_path': str(BW / ('R1_M0_MID_requested.csv' if name == 'M0_CLEAN_REFERENCE' else 'R1_M1_MID_requested.csv')), 'derived_requested_csv_sha': writeframe(f, name + '_requested'), **frameinfo(f)})
    pre = specs['PRIMARY_BINARY_CLEAN'].query('noncoverage_2024==1 and obesity==1 and post==0')
    assert set(zip(pre.state, pre.calendar_quarter)) == {('NM', '2023Q3'), ('NM', '2023Q4')}
    assert (pre.observed_rx_sum == 0).all() and (pre.suppressed_NDC_rows > 0).all()
    jw(WORK / 'input_gate.json', {'G_DATA': 'PASS', 'B_MID_assignment_hash_verified': assignment, 'clean_reportable_pairs': len(cleanpairs), 'source_reportability_grid': len(supportrows), 'clean_noncoverage_W_pre_states': sorted(pre.state.unique()), 'clean_noncoverage_W_pre_keys': keys(pre), 'major_caution': 'SINGLE_STATE_NONCOVERAGE_WEGOVY_CLEAN_PRE_SUPPORT', 'all_pre_NCW_outcome_from_suppression_assignment': True})
    jw(WORK / 'variant_manifest.json', manifests)
    primary = specs['PRIMARY_BINARY_CLEAN']
    rows = []
    for group in [0, 1]:
        for product in ['OZEMPIC', 'WEGOVY']:
            for q in C10:
                g = primary[(primary.coverage_2024 == group) & (primary.analytic_brand == product) & (primary.calendar_quarter == q)]
                rows.append({'Variant_ID': 'PRIMARY_BINARY_CLEAN', 'group': 'COVERAGE' if group else 'NONCOVERAGE', 'product': product, 'calendar_quarter': q, 'k': int(q[:4]) * 4 + int(q[-1]) - 8098, 'pre_post': 'POST' if q >= '2024Q2' else 'PRE', 'requested_model_observations': len(g), 'states': ';'.join(sorted(g.state.unique())), 'G': int(g.state.nunique()), 'positive_model_outcomes': int((g.y > 0).sum()), 'zero_model_outcomes': int((g.y == 0).sum()), **{c: float(g[c].sum()) for c in ['actually_reported_NDC_rows', 'observed_positive_NDC_rows', 'observed_zero_NDC_rows', 'suppressed_NDC_rows', 'observed_rx_sum', 'suppression_assigned_rx']}})
    cw(OUT / '04C_A_Group_Quarter_Support.csv', rows)
    rows = []
    for group in [0, 1]:
        for product in ['OZEMPIC', 'WEGOVY']:
            for post in [0, 1]:
                g = primary[(primary.coverage_2024 == group) & (primary.analytic_brand == product) & (primary.post == post)]
                rows.append({'group': 'COVERAGE' if group else 'NONCOVERAGE', 'product': product, 'pre_post': 'POST' if post else 'PRE', 'n': len(g), 'G': int(g.state.nunique()), 'states': ';'.join(sorted(g.state.unique())), 'actually_reported_NDC_rows': int(g.actually_reported_NDC_rows.sum()), 'suppressed_NDC_rows': int(g.suppressed_NDC_rows.sum()), 'observed_rx_sum': float(g.observed_rx_sum.sum()), 'suppression_assigned_rx': float(g.suppression_assigned_rx.sum())})
    cw(OUT / '04C_A_Group_Product_PrePost_Support.csv', rows)
    checkpoint('support', {'variants': 4, 'primary': frameinfo(primary), 'single_state_pre': True})
    print('SUPPORT PASS', frameinfo(primary), flush=True)

def design(f, name):
    sp = (f.state + ':' + f.analytic_brand).to_numpy()
    levels = sorted(set(sp))
    qs = sorted(set(f.calendar_quarter))
    event = name in ['EV_CLEAN', 'EV_TRANS']
    ref = '2023Q4' if event else qs[0]
    columns = [np.ones(len(f))]
    names = ['Intercept']
    for v in levels[1:]:
        columns.append((sp == v).astype(float))
        names.append('SP:' + v)
    for q in qs:
        if q != ref:
            columns.append((f.calendar_quarter == q).to_numpy(float))
            names.append('Q:' + q)
    targets = []
    times = jr(WORK / 'frozen_plan.json')['event_families'][name] if event else ['POST']
    for k in times:
        time = (f.k == k).to_numpy(float) if event else f.post.to_numpy(float)
        for tag, mult in [('W', f.obesity), ('NC', f.noncoverage_2024), ('DDD', f.obesity * f.noncoverage_2024)]:
            columns.append(time * mult.to_numpy(float))
            names.append(('Event[' + str(k) + ']' if event else 'Post') + '×' + tag)
            if tag == 'DDD':
                targets.append(len(names) - 1)
    return (np.column_stack(columns), names, targets, {'SP_base': levels[0], 'quarter_FE_reference': ref, 'event_interaction_reference': '2023Q4' if event else 'PRE', 'family_size': len(targets)})

def xhash(X):
    return th(str(X.shape) + '|' + str(X.dtype) + '|' + ','.join((f17(x) for x in X.ravel())))

def effective(f, name, tag):
    removed = []
    rounds = []
    certs = []
    for iteration in range(10):
        X, names, targets, normalization = design(f, name)
        s = sc.separation(X, f.y.to_numpy())
        rows = keys(f)
        drop = [rows[i] for i in np.flatnonzero(s['affected'])]
        rounds.append({'iteration': iteration + 1, 'n': len(f), 'status': s['status'], 'dropped_keys': drop})
        certs.append(jsonable(s))
        if not s['detected']:
            return (f, {'rounds': rounds, 'certificates': certs, 'removed_keys': removed, 'stable': True})
        removed += drop
        f = f.loc[~s['affected']].copy()
    return (f, {'rounds': rounds, 'certificates': certs, 'removed_keys': removed, 'stable': False})

def diagnose(f, name, tag, requested, sep):
    X, names, targets, norm = design(f, name)
    r = sc.rank_info(X)
    info = frameinfo(f)
    targetrows = []
    allcols = []
    for j, n in enumerate(names):
        other = np.delete(X / r['scale'], j, axis=1)
        u, s, v = linalg.svd(other, full_matrices=False)
        tau = max(other.shape) * np.finfo(float).eps * s[0]
        basis = u[:, s > tau]
        a = X[:, j] / r['scale'][j]
        residual = a - basis @ (basis.T @ a)
        estimable = sc.target_estimable(X, j)
        reason = 'IDENTIFIABLE' if estimable else 'COLUMN_ALL_ZERO' if not np.any(X[:, j]) else 'LINEARLY_ABSORBED_BY_OTHER_COLUMNS'
        row = {'Variant_ID': tag, 'parameter': n, 'is_DDD_target': j in targets, 'column_index': j, 'estimable': estimable, 'reason': reason, 'residual_norm': float(linalg.norm(residual)), 'column_norm': float(linalg.norm(a)), 'X_rank': r['rank'], 'nominal_k': r['k'], 'rank_without_column': sc.rank_info(np.delete(X, j, axis=1))['rank'], 'tau': r['threshold']}
        if j in targets:
            for label, sub in [('TARGET_PERIOD', f[f.k == int(n.split('[')[1].split(']')[0])]), ('REFERENCE_2023Q4', f[f.calendar_quarter == '2023Q4'])] if name in ['EV_CLEAN', 'EV_TRANS'] else [('PRE', f[f.post == 0]), ('POST', f[f.post == 1])]:
                for group in [0, 1]:
                    for product in ['OZEMPIC', 'WEGOVY']:
                        cell = sub[(sub.coverage_2024 == group) & (sub.analytic_brand == product)]
                        prefix = label + ('_C_' if group else '_NC_') + product
                        row[prefix + '_n'] = len(cell)
                        row[prefix + '_G'] = int(cell.state.nunique())
                        row[prefix + '_states'] = ';'.join(sorted(cell.state.unique()))
        allcols.append(row)
        if j in targets:
            targetrows.append(row)
    overall = all((x['estimable'] for x in targetrows)) and info['coverage_G'] >= 2 and (info['noncoverage_G'] >= 2) and sep['stable']
    if name not in ['EV_CLEAN', 'EV_TRANS']:
        overall = overall and r['rank'] == r['k'] == r['rank_tau_0_1'] == r['rank_tau_10']
    obj = target(WORK / (tag + '_design.npz'))
    np.savez_compressed(obj, X=X, y=f.y.to_numpy(), offset=f.offset.to_numpy(), clusters=f.state.to_numpy(dtype=str), names=np.array(names), keys=np.array(keys(f)))
    writeframe(f, tag + '_effective')
    d = {'Variant_ID': tag, 'design': name, 'requested': frameinfo(requested), 'effective': info, 'rank': jsonable(r), 'normalization': norm, 'target_family': targetrows, 'G_TARGET': 'PASS' if overall else 'NOT_VERIFIABLE' if name in ['EV_CLEAN', 'EV_TRANS'] else 'FAIL', 'separation': sep, 'X_hash': xhash(X), 'names_hash': kh(names), 'object_path': str(obj), 'object_sha': sha(obj), 'requested_X_hash': xhash(design(requested, name)[0]), 'diagnostics_only': name != 'PRIMARY_BINARY_CLEAN'}
    jw(WORK / (tag + '_diagnostics.json'), d)
    return (d, allcols)

def diagnostics():
    imports()
    assert jr(WORK / 'support_complete.json')['status'] == 'COMPLETE_VERIFIED'
    assert jr(WORK / 'environment_gate.json')['G_ENV'] == 'PASS' and jr(WORK / 'input_gate.json')['G_DATA'] == 'PASS'
    assert sha(CODE / 'stat_core.py') == jr(WORK / 'environment_gate.json')['core_sha']
    for v in jr(BW / 'variant_manifest.json'):
        if v['Variant_ID'] in ['R1_M0_MID', 'R1_M1_MID']:
            assert sha(v['input_csv']) == v['input_csv_sha']
    for p in [BW / 'raw_NDC_model_ledger.csv', BW / 'quarterly_population_ledger.csv', REQUEST]:
        frozen = next((r for r in jr(WORK / 'protected_before.json') if r['path'] == str(p)))
        assert sha(p) == frozen['sha256']
    assert sha(REQUEST) == jr(WORK / 'frozen_plan.json')['request_sha']
    results = []
    allrows = []
    fs = {}
    native = []
    for name in ['PRIMARY_BINARY_CLEAN', 'EV_CLEAN', 'EV_TRANS', 'M0_CLEAN_REFERENCE']:
        req = readframe(name + '_requested')
        f, sep = effective(req, name, name)
        d, rows = diagnose(f, name, name, req, sep)
        results.append(d)
        allrows += rows
        fs[name] = f
        native.append(d)
        print('DIAG', name, len(req), len(f), d['rank']['rank'], d['rank']['k'], d['G_TARGET'], flush=True)
    members = ['PRIMARY_BINARY_CLEAN', 'M0_CLEAN_REFERENCE']
    common = set.intersection(*(set(keys(fs[m])) for m in members))
    rounds = []
    stable = False
    initial_common = set(common)
    for iteration in range(10):
        union = set()
        proofs = {}
        for m in members:
            f = fs[m].loc[np.array([k in common for k in keys(fs[m])])].copy()
            X, n, t, _ = design(f, m)
            s = sc.separation(X, f.y.to_numpy())
            drop = {keys(f)[i] for i in np.flatnonzero(s['affected'])}
            union |= drop
            proofs[m] = jsonable(s)
        rounds.append({'iteration': iteration + 1, 'n': len(common), 'drop_union': sorted(union), 'certificates': proofs})
        if not union:
            stable = True
            break
        common -= union
    commonrows = []
    for m in members:
        native_req = readframe(m + '_requested')
        req = fs[m].loc[np.array([k in initial_common for k in keys(fs[m])])].copy()
        f = fs[m].loc[np.array([k in common for k in keys(fs[m])])].copy()
        sep = {'stable': stable, 'rounds': rounds, 'certificates': [], 'removed_keys': sorted(initial_common - common)}
        writeframe(req, m + '_COMMON_C10_requested')
        d, rows = diagnose(f, m, m + '_COMMON_C10', req, sep)
        results.append(d)
        allrows += rows
        d['native_requested'] = frameinfo(native_req)
        d['common_initial_keys_hash'] = kh(sorted(initial_common))
        jw(WORK / (m + '_COMMON_C10_diagnostics.json'), d)
        commonrows.append({'family': 'M0_M1_C10', 'member': m, 'status': 'STABLE_VERIFIED' if stable else 'NOT_VERIFIABLE', 'iterations': len(rounds), 'native_requested_n': len(native_req), 'native_requested_G': int(native_req.state.nunique()), 'common_initial_n': len(initial_common), 'model_requested_n': len(req), 'model_requested_G': int(req.state.nunique()), 'n': len(f), 'keys_hash': kh(sorted(common)), 'G_TARGET': d['G_TARGET'], 'numeric_comparison': 'NOT_EXECUTED_M0_DIAGNOSTICS_ONLY', 'old_B_COMMON_reusable': False, 'rule': 'new C10 native-effective key intersection; certificate union only'})
    cw(OUT / '04C_A_Common_Support_Status.csv', commonrows)
    jw(WORK / 'common_rounds.json', rounds)
    cw(OUT / '04C_A_Model_Identifiability.csv', allrows)
    jw(WORK / 'diagnostics_index.json', results)
    sample = []
    for d in results:
        a = d['requested']
        e = d['effective']
        sample.append({'Variant_ID': d['Variant_ID'], 'requested_n': a['n'], 'effective_n': e['n'], 'requested_G': a['G'], 'effective_G': e['G'], 'effective_coverage_G': e['coverage_G'], 'effective_noncoverage_G': e['noncoverage_G'], 'nominal_parameters': d['rank']['k'], 'rank': d['rank']['rank'], 'rank_tau_0_1': d['rank']['rank_tau_0_1'], 'rank_tau_10': d['rank']['rank_tau_10'], 'requested_key_hash': a['keys_hash'], 'effective_key_hash': e['keys_hash'], 'requested_input_hash': a['input_hash'], 'effective_input_hash': e['input_hash'], 'effective_quarters': ';'.join(e['quarters']), 'certified_native_separation_drops': len(d['separation']['removed_keys']) if '_COMMON_' not in d['Variant_ID'] else 'COMMON_INTERSECTION_EXCLUSIONS', 'G_TARGET': d['G_TARGET'], 'fit_authorized': d['Variant_ID'] == 'PRIMARY_BINARY_CLEAN'})
    cw(OUT / '04C_A_Clean_Window_Sample_Audit.csv', sample)
    texts = ['# Stage04C-A separation diagnostics', 'Formal core LP uses unrestricted directions, positive-outcome equality, zero-outcome nonpositivity, and sum normalization <= -1. Only certified strictly negative zero-row margins are removed. Rank failure is a separate condition.', 'All-positive outcomes imply no Poisson recession separation: every observed row is constrained to equality; no zero-outcome row can supply a strict decrease. NO_ZERO_OUTCOMES is this exact certificate, not an executed LP.']
    for d in native:
        texts += [f"\n## {d['Variant_ID']}", f"Requested {d['requested']['n']}; effective {d['effective']['n']}; stable={d['separation']['stable']}.", json.dumps(d['separation']['rounds'], ensure_ascii=False), f"Removed keys: {d['separation']['removed_keys']}.", f"Full local certificate/proof: _working/{d['Variant_ID']}_diagnostics.json; X SHA {d['X_hash']}."]
    md('04C_A_Separation_Diagnostics.md', '\n\n'.join(texts))
    checkpoint('diagnostics', {'designs': len(results), 'common_stable': stable, 'diagnostics_index_sha': sha(WORK / 'diagnostics_index.json'), 'variant_manifest_sha': sha(WORK / 'variant_manifest.json'), 'plan_sha': sha(WORK / 'frozen_plan.json')})
    print('DIAGNOSTICS COMPLETE', flush=True)

def primary():
    imports()
    d = jr(WORK / 'PRIMARY_BINARY_CLEAN_diagnostics.json')
    env = jr(WORK / 'environment_gate.json')
    gate = jr(WORK / 'input_gate.json')
    base = {'Analysis_ID': '04C-01', 'Variant_ID': 'PRIMARY_BINARY_CLEAN', 'beta': '', 'SE': '', 'IRR': '', 'CI_low': '', 'CI_high': '', 'P': '', 'requested_n': d['requested']['n'], 'effective_n': d['effective']['n'], 'G': d['effective']['G'], 'coverage_G': d['effective']['coverage_G'], 'noncoverage_G': d['effective']['noncoverage_G'], 'rank': d['rank']['rank'], 'df': d['effective']['G'] - 1, 'input_hash': d['effective']['input_hash'], 'X_hash': d['X_hash'], 'status': 'FAILED', 'reason': ''}
    gates = {'G_ENV': env['G_ENV'], 'G_DATA': gate['G_DATA'], 'G_TARGET': d['G_TARGET'], 'G_SOLVER': 'NOT_EXECUTED', 'G_COV': 'NOT_EXECUTED'}
    attempted_runs = 0
    try:
        done = jr(WORK / 'diagnostics_complete.json')
        assert done['status'] == 'COMPLETE_VERIFIED'
        assert sha(WORK / 'diagnostics_index.json') == done['details']['diagnostics_index_sha']
        assert sha(WORK / 'variant_manifest.json') == done['details']['variant_manifest_sha'] and sha(WORK / 'frozen_plan.json') == done['details']['plan_sha']
        assert d == next((x for x in jr(WORK / 'diagnostics_index.json') if x['Variant_ID'] == 'PRIMARY_BINARY_CLEAN'))
        req = readframe('PRIMARY_BINARY_CLEAN_requested')
        eff = readframe('PRIMARY_BINARY_CLEAN_effective')
        assert frameinfo(req) == d['requested'] and frameinfo(eff) == d['effective']
        assert all((gates[g] == 'PASS' for g in ['G_ENV', 'G_DATA', 'G_TARGET'])), 'PREREQUISITE_GATE_FAILURE'
        assert d['rank']['rank'] == d['rank']['k'] == d['rank']['rank_tau_0_1'] == d['rank']['rank_tau_10'], 'G_TARGET rank sensitivity failure'
        assert d['separation']['stable']
        assert sha(d['object_path']) == d['object_sha']
        assert sha(CODE / 'stat_core.py') == env['core_sha']
        z = np.load(safe(d['object_path']), allow_pickle=False)
        X = z['X']
        y = z['y']
        off = z['offset']
        cl = z['clusters']
        j = z['names'].tolist().index('Post×DDD')
        r = X.shape[1]
        assert xhash(X) == d['X_hash']
        starts = [np.r_[np.log((y.sum() + 0.1) / np.exp(off).sum()), np.zeros(r - 1)], np.zeros(r), np.r_[np.log((y.sum() + 0.1) / np.exp(off).sum()), np.zeros(r - 1)]]
        runs = []
        solvers = []
        for i, (start, tol) in enumerate(zip(starts, [1e-10, 1e-10, 1e-12])):
            attempted_runs += 1
            gates['G_SOLVER'] = 'FAIL'
            gates['G_COV'] = 'NOT_EXECUTED'
            fit = sc.glm_fit(y, X, off, start, tol)
            solvers.append(fit)
            jw(WORK / f'primary_run_{i + 1}_solver.json', jsonable(fit))
            np.savez_compressed(target(WORK / f'primary_run_{i + 1}_solver_object.npz'), params=fit['params'], mu=fit['mu'], raw_score=fit['raw_score'])
            assert fit['solver_gate'], f'G_SOLVER failed run {i + 1}'
            gates['G_SOLVER'] = 'PASS'
            gates['G_COV'] = 'FAIL'
            cov = sc.covariance(X, y, fit['mu'], cl)
            np.savez_compressed(target(WORK / f'primary_run_{i + 1}_full.npz'), params=fit['params'], mu=fit['mu'], V=cov['V'], bread=cov['bread'], H=cov['H'], meat=cov['meat'], cluster_scores=cov['cluster_scores'], groups=cov['groups'], weighted_spectrum=cov['weighted_spectrum'])
            jw(WORK / f'primary_run_{i + 1}_cov_gate.json', jsonable({k: v for k, v in cov.items() if k not in ['V', 'bread', 'H', 'meat', 'cluster_scores', 'groups', 'weighted_spectrum']}))
            assert cov['covariance_gate'] and cov['V'][j, j] > 0, f'G_COV failed run {i + 1}'
            gates['G_COV'] = 'PASS'
            est = sc.inference(fit['params'][j], cov['V'][j, j], cov['G'])
            assert all((np.isfinite(est[c]) for c in ['beta', 'SE', 'IRR', 'CI_low', 'CI_high', 'P']))
            summary = {**est, 'run': i + 1, 'start': 'zeros' if i == 1 else 'exposure', 'tol': tol, 'iterations': fit['iterations'], 'score': fit['normalized_score'], 'last_five_deviance_relative_max': fit['last_five_deviance_relative_max'], 'objective_explanation': fit['objective_explanation'], 'CR1': cov['CR1'], 'n': cov['n'], 'rank': cov['r'], 'G': cov['G'], 'symmetry_relative': cov['symmetry_relative'], 'min_eigenvalue': cov['min_eigenvalue'], 'PSD_scale': cov['PSD_scale'], 'weighted_rank': cov['weighted_rank'], 'object_sha': sha(WORK / f'primary_run_{i + 1}_full.npz')}
            runs.append(summary)
            print('PRIMARY RUN', i + 1, est, flush=True)
        ref = solvers[0]
        v0 = np.load(WORK / 'primary_run_1_full.npz')['V']
        e0 = runs[0]
        gates['G_SOLVER'] = 'FAIL'
        gates['G_COV'] = 'NOT_VERIFIABLE'
        for i in [1, 2]:
            f = solvers[i]
            vi = np.load(WORK / f'primary_run_{i + 1}_full.npz')['V']
            ei = runs[i]
            assert abs(ei['beta'] - e0['beta']) <= 1e-06 + 1e-06 * abs(e0['beta'])
            assert np.all(np.abs(f['mu'] - ref['mu']) <= 1e-08 + 1e-06 * np.abs(ref['mu']))
        gates['G_SOLVER'] = 'PASS'
        gates['G_COV'] = 'FAIL'
        for i in [1, 2]:
            vi = np.load(WORK / f'primary_run_{i + 1}_full.npz')['V']
            ei = runs[i]
            assert abs(ei['SE'] - e0['SE']) <= 1e-06 + 0.0001 * abs(e0['SE'])
            assert np.all(np.abs(vi - v0) <= 1e-08 + 0.0001 * np.abs(v0))
        gates.update(G_SOLVER='PASS', G_COV='PASS', G_QA='FAIL')
        base.update({k: e0[k] for k in ['beta', 'SE', 'IRR', 'CI_low', 'CI_high', 'P']})
        base.update(status='VALID_CLEAN_CONDITIONAL_ASSOCIATION', reason='SINGLE_STATE_NONCOVERAGE_WEGOVY_CLEAN_PRE_SUPPORT; ALL_PRE_NCW_RX_IMPUTED_SUPPRESSION')
        jw(WORK / 'primary_runs.json', runs)
        zz = np.load(WORK / 'primary_run_1_full.npz')
        mu = zz['mu']
        H = np.zeros((r, r))
        M = np.zeros((r, r))
        for x, m in zip(X, mu):
            H += m * np.outer(x, x)
        for g in sorted(set(cl)):
            score = np.zeros(r)
            for x, yy, m in zip(X[cl == g], y[cl == g], mu[cl == g]):
                score += x * (yy - m)
            M += np.outer(score, score)
        Hinv = linalg.solve(H, np.eye(r), assume_a='pos')
        G = len(set(cl))
        correction = G / (G - 1) * (len(y) - 1) / (len(y) - r)
        V = correction * (Hinv @ M @ Hinv)
        assert np.allclose(V, zz['V'], rtol=1e-07, atol=1e-08)
        beta = zz['params'][j]
        se = float(np.sqrt(V[j, j]))
        lo, hi = stats.t.interval(0.95, G - 1)
        pv = 2 * (1 - stats.t.cdf(abs(beta / se), G - 1))
        ci = (np.exp(beta + lo * se), np.exp(beta + hi * se))
        assert abs(se - base['SE']) < 1e-07 and abs(pv - base['P']) < 1e-08 and np.allclose(ci, [base['CI_low'], base['CI_high']], rtol=1e-07)
        jw(WORK / 'independent_numeric_QA.json', {'status': 'PASS', 'method': 'rowwise unscaled H / independent cluster-loop meat / positive-definite solve / t interval and CDF', 'CR1': correction, 'SE': se, 'P': pv, 'CI': list(ci), 'max_abs_full_V_difference': float(np.max(np.abs(V - zz['V']))), 'target_variance': float(V[j, j])})
        gates['G_QA'] = 'PASS'
    except Exception as e:
        if attempted_runs < 3 and gates['G_COV'] == 'FAIL' and (gates['G_SOLVER'] == 'PASS'):
            gates['G_SOLVER'] = 'NOT_VERIFIABLE'
        base.update(status='FAILED', reason=type(e).__name__ + ': ' + str(e))
        base.update({k: '' for k in ['beta', 'SE', 'IRR', 'CI_low', 'CI_high', 'P']})
        jw(WORK / 'primary_failure.json', {'error': base['reason'], 'gates': gates, 'traceback': traceback.format_exc()})
        print('PRIMARY FAILED', base['reason'], flush=True)
    cw(OUT / '04C_A_Primary_PPML_Results.csv', [base])
    jw(WORK / 'primary_gates.json', gates)
    checkpoint('primary', {'numeric_status': 'PASS' if base['status'].startswith('VALID') else 'FAIL', 'result_csv_sha': sha(OUT / '04C_A_Primary_PPML_Results.csv')})
    print('PRIMARY COMPLETE', base['status'], gates, flush=True)
if __name__ == '__main__':
    {'intake': intake, 'support': support, 'diagnostics': diagnostics, 'primary': primary}[sys.argv[1]]()
