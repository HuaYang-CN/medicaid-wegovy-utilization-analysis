"""Stage04D-B authorized eight channel models. No research IO on import.
Run explicit intake, diagnostics, fits, then independent QA and closeout.
Frozen statistical core is copied without changes; adapters are stage specific.
"""
import csv, hashlib, json, os, stat, sys, math, traceback, platform, subprocess, zipfile
from pathlib import Path
ROOT = Path(__file__).absolute().parents[2]
CODE = ROOT / '02_audit_code/Stage04D_B'
OUT = ROOT / '03_audit_outputs/Stage04D_B'
WORK = OUT / '_working'
DA = ROOT / '03_audit_outputs/Stage04D_A'
DW = DA / '_working'
BW = ROOT / '03_audit_outputs/Stage04B/_working/R1'
REQUEST = Path('external_resources/已粘贴的文本.txt')
C10 = ['2023Q2', '2023Q3', '2023Q4', '2024Q2', '2024Q3', '2024Q4', '2025Q1', '2025Q2', '2025Q3', '2025Q4']
MODELS = [f'CH_{ch}_{support}_{model}' for support in ['NATIVE', 'CH_BOTH_SUPPORT'] for ch in ['FFSU', 'MCOU'] for model in ['F0', 'EL1']]
CORE_SHA = 'e207f69b6e2e5ce7ed1849dcb2f7463d1d69a8d54fb6bd4ddd3333a97dc0d99f'

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

def f17(x):
    return format(float(x), '.17g')

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

def js(x):
    if isinstance(x, dict):
        return {str(k): js(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [js(v) for v in x]
    if hasattr(x, 'tolist'):
        return js(x.tolist())
    if isinstance(x, float) and (not math.isfinite(x)):
        return 'NONFINITE_' + str(x)
    return x

def jw(p, x):
    target(p).write_text(json.dumps(js(x), ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

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

def checkpoint(phase, details):
    jw(WORK / (phase + '_complete.json'), {'phase': phase, 'status': 'COMPLETE_VERIFIED', 'details': details, 'code_SHA256': sha(CODE / 'audit.py'), 'core_SHA256': sha(CODE / 'stat_core.py')})

def imports():
    global np, pd, sc, linalg, stats, optimize
    import numpy as np
    import pandas as pd
    import stat_core as sc
    from scipy import linalg, stats, optimize

def keys(f):
    return (f.state + '|' + f.calendar_quarter + '|' + f['product']).tolist()

def datahash(f):
    return kh((k + '|' + '|'.join((f17(r[c]) for c in ['y_mid', 'N_R1_total_Medicaid', 'offset', 'coverage', 'noncoverage', 'W', 'Post', 'quarter_index'])) for k, (_, r) in zip(keys(f), f.iterrows())))

def xhash(X):
    return th(str(X.shape) + '|' + str(X.dtype) + '|' + ','.join((f17(x) for x in X.ravel())))

def info(f):
    pairs = f.drop_duplicates(['state', 'calendar_quarter'])
    return {'n': len(f), 'G': int(f.state.nunique()), 'coverage_G': int(f.loc[f.coverage == 1, 'state'].nunique()), 'noncoverage_G': int(f.loc[f.coverage == 0, 'state'].nunique()), 'key_hash': kh(sorted(keys(f))), 'order_hash': kh(keys(f)), 'data_hash': datahash(f), 'population_hash': kh((r.state + '|' + r.calendar_quarter + '|' + f17(r.N_R1_total_Medicaid) + '|' + f17(r.offset) for r in pairs.itertuples())), 'quantity_source_hash': kh((k + '|' + f17(r.observed_rx) + '|' + f17(r.assigned_5_5_rx) + '|' + r.source_key_hash for k, r in zip(keys(f), f.itertuples())))}

def writeframe(f, n):
    p = target(WORK / (n + '.csv'))
    f.to_csv(p, index=False, float_format='%.17g')
    return sha(p)

def readframe(n):
    return pd.read_csv(safe(WORK / (n + '.csv')), float_precision='round_trip')

def protect_check():
    rows = jr(WORK / 'protected_before.json')
    differences = []
    for r in rows:
        if not safe(r['path']).is_file() or sha(r['path']) != r['sha256']:
            differences.append(r['path'])
    jw(WORK / 'protected_after.json', {'files_checked': len(rows), 'differences': differences, 'status': 'PASS' if not differences else 'FAIL'})
    assert not differences, 'Protected input drift'
    return len(rows)

def intake():
    assert not (WORK / 'intake_complete.json').exists(), 'Completed intake protected'
    authorities = [ROOT / 'AGENTS.md', ROOT / 'PROJECT_CHARTER.md', ROOT / '03_audit_outputs/Issue_Register.csv', REQUEST]
    authorities += [ROOT / '03_audit_outputs/Stage03' / ('03_' + s) for s in ['Stage04_Protocol_Lock.csv', 'FFS_MCO_Design_Protocol.md', 'PPML_Separation_Convergence_Protocol.md', 'Independent_Replication_Spec.md', 'Cluster_Inference_Plan.md', 'Model_Failure_Stop_Rules.md', 'Stage04_Decision_Gates.md']]
    for stage, prefix, names in [('Stage04A_R3C', '04A_R3C_', ['Executive_Report.md', 'Independent_PPML_Results.csv', 'Model_Gates.csv']), ('Stage04B', '04B_', ['Model_Results.csv', 'Model_Gates.csv', 'R1_Numerical_QA.json', 'R1_Quality_Assurance.md']), ('Stage04C_A', '04C_A_', ['Primary_PPML_Results.csv', 'Model_Gates.csv', 'Quality_Assurance.md']), ('Stage04D_A', '04D_A_', ['Executive_Data_Audit.md', 'Variant_Manifest.csv', 'Channel_Source_Status.csv', 'Channel_Paired_Support.csv', 'F0_EL1_Identifiability.csv', 'Common_vs_Native_Support.csv', 'Preperiod_Quantity_Summary.csv', 'Preperiod_State_Information.csv', 'State_Influence_Structural_Precheck.csv', 'Source_Manifest.csv', 'Quality_Assurance.md', 'Stage04D_B_Readiness.md'])]:
        authorities += [ROOT / '03_audit_outputs' / stage / (prefix + n) for n in names]
    protected = set(authorities)
    for p in authorities:
        assert safe(p).is_file(), f'Missing authority {p}'
        p.read_text(encoding='utf-8-sig')
    for d in ['00_original', '03_audit_outputs/Stage03', '03_audit_outputs/Stage04A_R3C', '03_audit_outputs/Stage04B', '03_audit_outputs/Stage04C_A', '03_audit_outputs/Stage04C_R1', '03_audit_outputs/Stage04D_A', '02_audit_code/Stage04A_R3C', '02_audit_code/Stage04B', '02_audit_code/Stage04C_A', '02_audit_code/Stage04C_R1', '02_audit_code/Stage04D_A']:
        protected.update(files(ROOT / d))
    assert jr(DW / 'closeout_complete.json')['status'] == 'COMPLETE_VERIFIED'
    for r in rc(DA / '04D_A_Source_Manifest.csv'):
        if r['role'] in ['AUTHORITATIVE_READONLY_INPUT', 'FROZEN_SOURCE_COMPONENT']:
            assert sha(r['path']) == r['SHA256'], 'D-A authority/source drift ' + r['path']
            protected.add(Path(r['path']))
    for r in jr(BW / 'input_gate.json')['source_sha']:
        assert sha(r['Path']) == r['SHA256']
        protected.add(Path(r['Path']))
    zp = ROOT / 'feedback/Medicaid_Wegovy_Stage04D_A_Feedback.zip'
    assert sha(zp) == '6d1bedea342f2028b871924b4b3a7461364edff23c687fecc3455c6e9c57d612'
    proof = jr(DW / 'package_verification.json')
    with zipfile.ZipFile(safe(zp)) as z:
        assert z.testzip() is None
        for name in z.namelist():
            assert hashlib.sha256(z.read(name)).hexdigest() == sha(ROOT / name), 'D-A archive versus disk drift'
    protected.add(zp)
    snap = [{'path': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size, 'authority': p in authorities} for p in sorted(protected)]
    jw(WORK / 'protected_before.json', snap)
    cw(OUT / '04D_B_Authority_Manifest.csv', [{'path': str(p), 'SHA256': sha(p), 'bytes': p.stat().st_size, 'content_read': 'YES', 'version': 'Stage03 v1.1 or formally closed preceding stage; direct D-B authorization'} for p in authorities])
    plan = {'request_sha': sha(REQUEST), 'models': MODELS, 'analyses': ['04D-01', '04D-02'], 'C10': C10, 'P': 'P1_July2024_46_12_34', 'R': 'R1_total_Medicaid_monthly_mean_ge2', 'S': 'SOURCE_SUPPRESSED_5.5', 'M': 'source-present paired products, missing NA', 'k_rule': 'year*4+quarter-8098', 'Post': 'from2024Q2', 'Early': '2024Q2 only', 'Late': 'from2024Q3', 'event_reference': '2023Q4', 'quarter_FE_normalization': '2023Q2, same as frozen D-A. F0/EL1 pool all three clean pre quarters; no point-specific event coefficients. Quarter FE base reparameterization does not change DDD targets.', 'CH_BOTH': 'intersection native FFSU/MCOU pair keys, quantities individually extracted from respective native CSV; combined y prohibited', 'COMMON_family': 'all eight requested model key sets. Initialize intersection; remove union of certified separation keys; recompute certificate/rank for every family member on intersection; max10 rounds. Stable COMMON matching four CH-BOTH model input signatures reuses their fits. Never select by estimates.', 'starts': [{'name': 'exposure', 'tol': 1e-10}, {'name': 'zeros', 'tol': 1e-10}, {'name': 'exposure', 'tol': 1e-12}], 'thresholds': {'score': 1e-08, 'last5_deviance': 1e-10, 'iterations_lt': 1000, 'symmetry': 1e-10, 'PSD_scaled': 1e-10}, 'stability': {'beta_abs': 1e-06, 'beta_rel': 1e-06, 'SE_abs': 1e-06, 'SE_rel': 0.0001, 'V_abs': 1e-08, 'V_rel': 0.0001, 'mu_abs': 1e-08, 'mu_rel': 1e-06}, 'normal_reference_critical': 1.96, 'main': 'CR1 t(G-1) two sided unadjusted pointwise 95%CI; all twelve sensitivity targets retained; no omnibus multiplicity claim', 'causal': 'NOT_ESTABLISHED', 'unexecuted': ['04D-03', '04D-04', '04D-05', '04D-06', 'numerical LOO', 'bootstrap', 'new negative controls', '04E', '05', 'manuscript edits'], 'core_sha': CORE_SHA, 'review_boundary': 'User specified twelve-output technical-stage structure. Apply statistics reporting rules and reviewer evidence/forensic rules to bounded technical review, not three manuscript referee reports; no external peer review claimed.'}
    jw(WORK / 'frozen_plan.json', plan)
    assert sha(CODE / 'stat_core.py') == CORE_SHA
    checkpoint('intake', {'protected': len(snap), 'authorities': len(authorities), 'D_A_archive_CRC_and_disk_match': 'PASS'})
    print('INTAKE PASS', len(snap), flush=True)

def design(f, model):
    sp = (f.state + ':' + f['product']).to_numpy()
    levels = sorted(set(sp))
    qs = sorted(set(f.calendar_quarter))
    cols = [np.ones(len(f))]
    names = ['Intercept']
    for s in levels[1:]:
        cols.append((sp == s).astype(float))
        names.append('SP:' + s)
    for q in qs[1:]:
        cols.append((f.calendar_quarter == q).to_numpy(float))
        names.append('Q:' + q)
    times = [('Post', f.Post)] if model == 'F0' else [('Early', f.calendar_quarter.eq('2024Q2').astype(int)), ('Late', f.calendar_quarter.ge('2024Q3').astype(int))]
    targets = []
    for label, t in times:
        for tag, a in [('W', f.W), ('NC', f.noncoverage), ('DDD', f.W * f.noncoverage)]:
            cols.append((t * a).to_numpy(float))
            names.append(label + '×' + tag)
            if tag == 'DDD':
                targets.append(len(cols) - 1)
    return (np.column_stack(cols), names, targets, {'SP_base': levels[0], 'quarter_FE_base': qs[0], 'event_ref': '2023Q4', 'binary_EL1_baseline': 'ALL_CLEAN_PRE_QUARTERS'})

def formal_sep(X, y):
    c = np.maximum(1, np.max(np.abs(X), axis=0))
    A = X / c
    pos = y > 0
    Az = A[y == 0]
    lp = optimize.linprog(np.zeros(X.shape[1]), A_ub=np.vstack([Az, Az.sum(axis=0)]), b_ub=np.r_[np.zeros(len(Az)), -1.0], A_eq=A[pos], b_eq=np.zeros(pos.sum()), bounds=[(None, None)] * X.shape[1], method='highs', options={'primal_feasibility_tolerance': 1e-09, 'dual_feasibility_tolerance': 1e-09})
    s = sc.separation(X, y)
    assert lp.status in [0, 2] and (lp.status == 0) == s['detected'], 'Formal LP/core mismatch'
    return {**s, 'formal_LP_status': int(lp.status), 'formal_LP_message': lp.message, 'positive_n': int(pos.sum()), 'zero_n': int((y == 0).sum()), 'LP_bounds': 'all direction coordinates free', 'normalization': 'sum(A_zero*d)<=-1', 'tolerances': {'primal': 1e-09, 'dual': 1e-09, 'certificate': 1e-08}, 'no_zero_proof': 'empty zero-set implies impossible 0<=-1 normalization; no direction/certificate exists' if not len(Az) else None}

def validate_frame(f, cells, ch):
    assert len(keys(f)) == len(set(keys(f)))
    assert set(f.calendar_quarter).issubset(set(C10)) and '2024Q1' not in set(f.calendar_quarter)
    assert (f.quarter_index == [int(q[:4]) * 4 + int(q[-1]) for q in f.calendar_quarter]).all()
    assert (f.k == f.quarter_index - 8098).all() and (f.Post == (f.quarter_index >= 8098).astype(int)).all()
    assert (f.W == f['product'].eq('WEGOVY').astype(int)).all() and (f.coverage + f.noncoverage == 1).all()
    assert f.groupby(['state', 'calendar_quarter'])['product'].apply(lambda x: set(x) == {'WEGOVY', 'OZEMPIC'}).all()
    assert f.groupby('state').coverage.nunique().eq(1).all()
    assert np.isfinite(f[['y_mid', 'observed_rx', 'assigned_5_5_rx', 'N_R1_total_Medicaid', 'offset']].to_numpy()).all()
    assert (f.y_mid >= 0).all() and (f.N_R1_total_Medicaid > 0).all()
    assert np.max(np.abs(np.log(f.N_R1_total_Medicaid) - f.offset)) < 3e-14
    assert (f.y_mid == f.observed_rx + f.assigned_5_5_rx).all() and (f.assigned_5_5_rx == f.suppressed_NDC_rows * 5.5).all()
    assert f.groupby(['state', 'calendar_quarter']).N_R1_total_Medicaid.nunique().eq(1).all()
    for r in f.itertuples():
        s = cells[r.state, r.calendar_quarter, r.product, ch]
        assert s['source_present'] == 'True' and int(s['valid_months']) >= 2 and (s['population_valid'] == 'True')
        for a, b in [('y_mid', 'midpoint_y'), ('observed_rx', 'observed_rx'), ('assigned_5_5_rx', 'assigned_5_5_rx'), ('N_R1_total_Medicaid', 'total_Medicaid_N_R1'), ('observed_NDC_rows', 'actually_reported_NDC_rows'), ('suppressed_NDC_rows', 'SUPPRESSED_NDC_rows')]:
            assert float(getattr(r, a)) == float(s[b])
        assert r.source_key_hash == s['source_key_hash'] and r.coverage == int(s['coverage'])

def diagnostics():
    imports()
    assert jr(WORK / 'intake_complete.json')['status'] == 'COMPLETE_VERIFIED'
    import importlib.metadata as meta
    expected = jr(BW / 'environment_gate.json')['installed']
    versions = {p: meta.version(p) for p in expected}
    assert versions == expected
    from packaging.version import Version
    assert all((not Version(v).is_prerelease and (not Version(v).is_devrelease) for v in versions.values()))
    pc = subprocess.run([sys.executable, '-B', '-m', 'pip', 'check'], capture_output=True, text=True)
    assert pc.returncode == 0
    assert sys.executable.lower() == str(ROOT / '.venv_stage04a/Scripts/python.exe').lower() and sha(CODE / 'stat_core.py') == CORE_SHA
    micro = [formal_sep(np.array([[1.0, 0.0], [1.0, 1.0]]), np.array([1.0, 0.0])), formal_sep(np.array([[1.0, 0.0], [1.0, 1.0]]), np.array([1.0, 1.0]))]
    assert micro[0]['detected'] and (not micro[1]['detected'])
    jw(WORK / 'environment_gate.json', {'G_ENV': 'PASS', 'python': sys.executable, 'version': platform.python_version(), 'packages': versions, 'pip_check': pc.stdout.strip(), 'micro_LP_certificate_and_all_positive_checks': micro, 'core_sha': CORE_SHA, 'original_research_environment': 'NOT_VERIFIABLE', 'startup_warning': 'Failed to find real location of external_resources/python.exe; root cause NOT_VERIFIABLE; verified venv version/imports/pip/LP independent'})
    oldvm = {v['Variant_ID']: v for v in jr(DW / 'variants.json')}
    frames = {}
    for ch in ['FFSU', 'MCOU', 'BOTH']:
        n = 'CH_' + ch + '_DATA_C10'
        v = oldvm[n]
        p = DW / (n + '_model_input.csv')
        assert sha(p) == v['input_csv_SHA256']
        f = pd.read_csv(safe(p), float_precision='round_trip')
        assert kh(keys(f)) == v['order_hash'] and kh(sorted(keys(f))) == v['model_key_hash'] and (datahash(f) == v['model_input_hash'])
        pairset = set((f.state + '|' + f.calendar_quarter).tolist())
        assert pairset == {r['state_quarter_key'] for r in rc(DW / (n + '_pair_keys.csv'))}
        assert kh(sorted(pairset)) == v['state_quarter_key_hash']
        frames[ch] = f
    commonkeys = set(keys(frames['BOTH']))
    assert commonkeys == set(keys(frames['FFSU'])) & set(keys(frames['MCOU']))
    cells = {(r['state'], r['calendar_quarter'], r['product'], r['channel']): r for r in rc(DA / '04D_A_Channel_Source_Status.csv')}
    policy = jr(DW / 'P1_policy.json')
    assert len(policy) == 46 and sum((int(v) for v in policy.values())) == 12
    combined = frames['BOTH'].set_index(['state', 'calendar_quarter', 'product'])
    native_indices = {c: frames[c].set_index(['state', 'calendar_quarter', 'product']) for c in ['FFSU', 'MCOU']}
    for idx, r in combined.iterrows():
        a = native_indices['FFSU'].loc[idx]
        b = native_indices['MCOU'].loc[idx]
        for col in ['observed_rx', 'assigned_5_5_rx', 'y_mid', 'observed_NDC_rows', 'suppressed_NDC_rows']:
            assert r[col] == a[col] + b[col]
        assert r.N_R1_total_Medicaid == a.N_R1_total_Medicaid == b.N_R1_total_Medicaid and r.offset == a.offset == b.offset
    manifest = []
    diaglist = []
    requested = {}
    effective = {}
    for name in MODELS:
        assert not (WORK / (name + '_diagnostics.json')).exists(), 'Do not replace completed diagnosis'
        ch = name.split('_')[1]
        model = name.split('_')[-1]
        req = frames[ch].copy()
        if 'CH_BOTH_SUPPORT' in name:
            req = req[[k in commonkeys for k in keys(req)]].copy()
        validate_frame(req, cells, ch)
        assert all((int(r.coverage) == int(policy[r.state]) for r in req.itertuples()))
        expected_ng = (504, 41, 11, 30) if name.startswith('CH_FFSU_NATIVE') else (620, 34, 11, 23) if name.startswith('CH_MCOU_NATIVE') else (348, 29, 10, 19)
        ri = info(req)
        assert tuple((ri[k] for k in ['n', 'G', 'coverage_G', 'noncoverage_G'])) == expected_ng
        X, names, tjs, norm = design(req, model)
        daobj = np.load(safe(DW / (name + '_design.npz')), allow_pickle=False)
        assert np.array_equal(X, daobj['X']) and names == daobj['names'].tolist() and (keys(req) == daobj['keys'].tolist())
        dad = jr(DW / (name + '_diagnostics.json'))
        assert xhash(X) == dad['targets'][0]['X_hash'] and kh(names) == dad['targets'][0]['names_hash']
        requested[name] = req
        writeframe(req, name + '_requested')
        f = req.copy()
        certs = []
        removed = []
        for iteration in range(10):
            X, names, tjs, norm = design(f, model)
            sep = formal_sep(X, f.y_mid.to_numpy())
            drops = [keys(f)[i] for i in np.flatnonzero(sep['affected'])]
            certs.append({'iteration': iteration + 1, 'input': info(f), 'X_hash': xhash(X), 'certificate': js(sep), 'removed_keys': drops})
            jw(WORK / (name + '_separation.json'), {'iterations': certs, 'removed_keys': removed + drops})
            if not sep['detected']:
                break
            if iteration == 9:
                break
            assert all((f.y_mid.iloc[i] == 0 for i in np.flatnonzero(sep['affected'])))
            removed += drops
            f = f.loc[~sep['affected']].copy()
        jw(WORK / (name + '_separation.json'), {'iterations': certs, 'removed_keys': removed, 'pending_certified_keys': drops if sep['detected'] else [], 'limit_reached': bool(sep['detected'])})
        stable = not sep['detected']
        r = sc.rank_info(X)
        targets = [{'name': names[j], 'index': j, 'rank_without': sc.rank_info(np.delete(X, j, axis=1))['rank'], 'estimable': sc.target_estimable(X, j)} for j in tjs]
        ef = info(f)
        gate = r['rank'] == r['k'] == r['rank_tau_0_1'] == r['rank_tau_10'] and all((t['estimable'] for t in targets)) and (ef['coverage_G'] >= 2) and (ef['noncoverage_G'] >= 2)
        assert len(X) == len(f), 'Saved evaluated input must be coherent even on separation limit'
        ob = target(WORK / (name + '_input.npz'))
        np.savez_compressed(ob, X=X, names=np.array(names), y=f.y_mid.to_numpy(), offset=f.offset.to_numpy(), clusters=f.state.to_numpy(dtype=str), keys=np.array(keys(f)))
        writeframe(f, name + '_effective')
        cw(WORK / (name + '_effective_keys.csv'), [{'key': k, 'channel': ch} for k in keys(f)])
        d = {'Variant_ID': name, 'Analysis_ID': '04D-01' if model == 'F0' else '04D-02', 'channel': ch, 'model': model, 'requested': ri, 'effective': ef, 'rank': r, 'targets': targets, 'normalization': norm, 'X_hash': xhash(X), 'names_hash': kh(names), 'requested_X_hash': xhash(design(req, model)[0]), 'separation_stable': stable, 'removed_keys': removed, 'G_TARGET': 'PASS' if gate else 'FAIL', 'G_SEPARATION': 'PASS' if stable else 'NOT_VERIFIABLE', 'object_SHA256': sha(ob)}
        jw(WORK / (name + '_diagnostics.json'), d)
        effective[name] = f
        diaglist.append(js(d))
        mh = th(json.dumps(js(d), ensure_ascii=False, sort_keys=True, separators=(',', ':')))
        manifest.append({'Variant_ID': name, 'Analysis_ID': d['Analysis_ID'], 'channel': ch, 'clock': 'PAID_QUARTER' if ch == 'FFSU' else 'DISPENSE_QUARTER', 'support': 'NATIVE' if 'NATIVE' in name else 'CH_BOTH_SOURCE', 'R': 'R1', 'M': 'CHANNEL_SOURCE_PRESENT_PAIR', 'S': 'SOURCE_SUPPRESSED_5.5', 'P': 'P1_46_12_34', 'window': 'DATA-C10', 'formula': model, 'pre': '2023Q2;2023Q3;2023Q4', 'Early': '2024Q2', 'Late': '2024Q3-2025Q4', 'source_input_sha': oldvm['CH_' + ch + '_DATA_C10']['input_csv_SHA256'], 'common_keys_only_source_sha': oldvm['CH_BOTH_DATA_C10']['input_csv_SHA256'], 'source_ledger_sha': oldvm['CH_' + ch + '_DATA_C10']['source_ledger_SHA256'], 'population_ledger_sha': oldvm['CH_' + ch + '_DATA_C10']['population_ledger_SHA256'], **{'requested_' + k: v for k, v in ri.items()}, **{'effective_' + k: v for k, v in ef.items()}, 'requested_X_hash': d['requested_X_hash'], 'effective_X_hash': d['X_hash'], 'column_names_hash': d['names_hash'], 'r': r['rank'], 'k': r['k'], 'separated_rows': len(removed), 'composite_diagnostics_hash': mh, 'input_object_sha': sha(ob), 'diagnostics_path': str(WORK / (name + '_diagnostics.json'))})
        print('DIAG', name, ri['n'], ef['n'], r['rank'], r['k'], d['G_TARGET'], sep['formal_LP_status'], flush=True)
    ck = set.intersection(*(set(keys(f)) for f in requested.values()))
    union = set().union(*(set(d['removed_keys']) for d in diaglist))
    ck -= union
    rounds = []
    for it in range(10):
        drops = set()
        detail = []
        for name in MODELS:
            f = requested[name][[k in ck for k in keys(requested[name])]].copy()
            X, names, tjs, norm = design(f, name.split('_')[-1])
            s = formal_sep(X, f.y_mid.to_numpy())
            drops.update((keys(f)[i] for i in np.flatnonzero(s['affected'])))
            detail.append({'Variant_ID': name, 'n': len(f), 'rank': sc.rank_info(X)['rank'], 'k': X.shape[1], 'targets_estimable': all((sc.target_estimable(X, j) for j in tjs)), 'LP_status': s['formal_LP_status'], 'X_hash': xhash(X), 'data_hash': datahash(f), 'complete_separation_certificate': js(s)})
        rounds.append({'iteration': it + 1, 'key_hash': kh(sorted(ck)), 'n': len(ck), 'certified_removed_union': sorted(drops), 'models': detail})
        if not drops:
            break
        if it == 9:
            break
        ck -= drops
    reuse = {}
    common_stable = not drops
    for name in MODELS:
        if 'CH_BOTH_SUPPORT' in name:
            if common_stable and set(keys(effective[name])) == ck:
                f = requested[name][[k in ck for k in keys(requested[name])]].copy()
                if datahash(f) == datahash(effective[name]) and xhash(design(f, name.split('_')[-1])[0]) == next((d['X_hash'] for d in diaglist if d['Variant_ID'] == name)):
                    reuse[name] = name
    common_ok = common_stable and len(reuse) == 4 and all((r['targets_estimable'] for r in rounds[-1]['models']))
    jw(WORK / 'COMMON_support.json', {'status': 'PASS' if common_ok else 'NOT_VERIFIABLE', 'family': 'ALL_EIGHT_PRELOCKED', 'stable': common_stable, 'max10': True, 'rounds': rounds, 'keys': sorted(ck), 'key_hash': kh(sorted(ck)), 'n': len(ck), 'fit_reuse': reuse, 'reuse_proof': 'exact data/order/X/cluster/name identities; four CH-BOTH source model fits are also formal COMMON results; no added model fits' if common_ok else 'COMMON did not stabilize or requires non-reusable support; independently valid native/source fits preserved; no unsupported same-sample claim'})
    cw(OUT / '04D_B_Analysis_Manifest.csv', manifest)
    jw(WORK / 'diagnostics_summary.json', diaglist)
    checkpoint('diagnostics', {'models': 8, 'CH_BOTH_channel_quantity_sum_identity': 'PASS', 'native_source_quantity_identity': 'PASS', 'COMMON_n': len(ck)})

def fits():
    imports()
    assert jr(WORK / 'diagnostics_complete.json')['status'] == 'COMPLETE_VERIFIED'
    assert sha(CODE / 'stat_core.py') == CORE_SHA
    statuses = []
    resultrows = []
    gates = []
    for name in MODELS:
        if (WORK / (name + '_fit_complete.json')).exists():
            raise RuntimeError('Completed model must not be rerun ' + name)
        d = jr(WORK / (name + '_diagnostics.json'))
        assert sha(WORK / (name + '_input.npz')) == d['object_SHA256']
        ob = np.load(safe(WORK / (name + '_input.npz')), allow_pickle=False)
        X = ob['X']
        y = ob['y']
        offset = ob['offset']
        cl = ob['clusters']
        names = ob['names'].tolist()
        assert xhash(X) == d['X_hash']
        actual = {'G_ENV': 'PASS', 'G_DATA': 'PASS', 'G_POLICY': 'NOT_VERIFIABLE', 'G_TARGET': d['G_TARGET'], 'G_SEPARATION': d['G_SEPARATION'], 'G_SOLVER': 'NOT_EXECUTED', 'G_COV': 'NOT_EXECUTED', 'G_IDENTIFICATION': 'NOT_VERIFIABLE', 'G_BOOT': 'NOT_EXECUTED', 'G_NUMERICAL_QA': 'NOT_EXECUTED'}
        success = False
        failure = ''
        runs = []
        metrics = []
        try:
            assert d['G_TARGET'] == 'PASS' and d['G_SEPARATION'] == 'PASS', 'Target/separation gate failed'
            for idx, plan in enumerate(jr(WORK / 'frozen_plan.json')['starts']):
                tag = f'{name}_run{idx + 1}'
                start = np.zeros(X.shape[1])
                if plan['name'] == 'exposure':
                    start[0] = math.log(float(y.sum() / np.exp(offset).sum()))
                jw(WORK / (tag + '_attempt.json'), {'status': 'STARTED', 'start': start, 'tol': plan['tol'], 'model_sha': d['object_SHA256']})
                actual['G_SOLVER'] = 'FAIL'
                fit = sc.glm_fit(y, X, offset, start, plan['tol'])
                jw(WORK / (tag + '_solver.json'), fit)
                np.savez_compressed(target(WORK / (tag + '_fit.npz')), params=fit['params'], mu=fit['mu'], raw_score=fit['raw_score'], start=start)
                assert fit['solver_gate'], 'Solver gate failed'
                actual['G_SOLVER'] = 'PENDING_FIXED_RUN_FAMILY'
                actual['G_COV'] = 'FAIL'
                cov = sc.covariance(X, y, fit['mu'], cl)
                np.savez_compressed(target(WORK / (tag + '_cov.npz')), **cov)
                jw(WORK / (tag + '_cov_summary.json'), {k: v for k, v in cov.items() if k not in ['V', 'bread', 'H', 'meat', 'cluster_scores', 'groups', 'weighted_spectrum']})
                assert cov['covariance_gate'] and all((cov['V'][t['index'], t['index']] > 0 for t in d['targets'])), 'Covariance/target variance gate failed'
                actual['G_COV'] = 'PENDING_FIXED_RUN_FAMILY'
                runs.append((fit, cov))
                metrics.append({'run': idx + 1, 'start': plan['name'], 'tol': plan['tol'], 'per_run_solver': 'PASS', 'per_run_covariance': 'PASS', 'iterations': fit['iterations'], 'score': fit['normalized_score'], 'last5': fit['last_five_deviance_relative_max'], 'objective': fit['objective_explanation'], 'weighted_rank': cov['weighted_rank'], 'CR1': cov['CR1'], 'symmetry': cov['symmetry_relative'], 'minimum_eigenvalue': cov['min_eigenvalue'], 'PSD_scale': cov['PSD_scale'], 'warnings': fit['warnings']})
                print('FIT', name, idx + 1, fit['iterations'], fit['normalized_score'], flush=True)
            ref, cv = runs[0]
            stability = []
            for run, (a, b) in enumerate(runs[1:], 2):
                checks = {'params_target': all((abs(a['params'][t['index']] - ref['params'][t['index']]) <= 1e-06 + 1e-06 * abs(ref['params'][t['index']]) for t in d['targets'])), 'SE_target': all((abs(math.sqrt(b['V'][t['index'], t['index']]) - math.sqrt(cv['V'][t['index'], t['index']])) <= 1e-06 + 0.0001 * math.sqrt(cv['V'][t['index'], t['index']]) for t in d['targets'])), 'full_covariance': bool(np.all(np.abs(b['V'] - cv['V']) <= 1e-08 + 0.0001 * np.abs(cv['V']))), 'mu': bool(np.all(np.abs(a['mu'] - ref['mu']) <= 1e-08 + 1e-06 * np.abs(ref['mu'])))}
                stability.append({'run': run, 'checks': checks, 'target_beta_max_difference': float(max((abs(a['params'][t['index']] - ref['params'][t['index']]) for t in d['targets']))), 'full_V_max_difference': float(np.max(np.abs(b['V'] - cv['V']))), 'mu_max_difference': float(np.max(np.abs(a['mu'] - ref['mu'])))})
            jw(WORK / (name + '_stability.json'), stability)
            actual['G_SOLVER'] = 'PASS' if all((s['checks']['params_target'] and s['checks']['mu'] for s in stability)) else 'FAIL'
            actual['G_COV'] = 'PASS' if all((s['checks']['SE_target'] and s['checks']['full_covariance'] for s in stability)) else 'FAIL'
            assert actual['G_SOLVER'] == actual['G_COV'] == 'PASS', 'Fixed-start/tolerance stability failure'
            cross = float(cv['V'][d['targets'][0]['index'], d['targets'][1]['index']]) if len(d['targets']) == 2 else None
            for t in d['targets']:
                j = t['index']
                inf = sc.inference(ref['params'][j], cv['V'][j, j], cv['G'])
                normal = sc.inference(ref['params'][j], cv['V'][j, j], cv['G'], 'normal')
                common_record = jr(WORK / 'COMMON_support.json')
                result_support = 'NATIVE' if 'NATIVE' in name else 'CH_BOTH_SOURCE_AND_STABLE_COMMON' if common_record['status'] == 'PASS' and common_record['fit_reuse'].get(name) == name else 'CH_BOTH_SOURCE'
                resultrows.append({'Analysis_ID': d['Analysis_ID'], 'Variant_ID': name, 'target': t['name'], 'status': 'PENDING_INDEPENDENT_QA', 'result_type': 'CHANNEL-SPECIFIC ASSOCIATIONAL SENSITIVITY RESULT', 'channel': d['channel'], 'support': result_support, **inf, 'normal_IRR': normal['IRR'], 'normal_CI_low': normal['CI_low'], 'normal_CI_high': normal['CI_high'], 'normal_P': normal['P'], 'normal_critical': 1.96, 'Early_Late_covariance': cross, **{'requested_' + k: v for k, v in d['requested'].items()}, **{'effective_' + k: v for k, v in d['effective'].items()}, 'r': d['rank']['rank'], 'k': d['rank']['k'], 'X_hash': d['X_hash'], 'CR1': cv['CR1'], 'failure_reason': ''})
            success = True
        except Exception as e:
            for gate in ['G_SOLVER', 'G_COV']:
                if actual[gate] == 'PENDING_FIXED_RUN_FAMILY':
                    actual[gate] = 'NOT_VERIFIABLE'
            failure = type(e).__name__ + ': ' + str(e)
            jw(WORK / (name + '_failure.json'), {'reason': failure, 'traceback': traceback.format_exc(), 'gates': actual, 'input_sha': d['object_SHA256'], 'runs_completed': len(runs)})
            status = 'NOT_IDENTIFIABLE' if any((not t['estimable'] for t in d['targets'])) else 'FAIL'
            for t in d['targets']:
                resultrows.append({'Analysis_ID': d['Analysis_ID'], 'Variant_ID': name, 'target': t['name'], 'status': status, 'result_type': 'CHANNEL-SPECIFIC ASSOCIATIONAL SENSITIVITY RESULT', 'channel': d['channel'], 'beta': '', 'SE': '', 'IRR': '', 'CI_low': '', 'CI_high': '', 'P': '', 'df': '', 'normal_IRR': '', 'normal_CI_low': '', 'normal_CI_high': '', 'normal_P': '', 'Early_Late_covariance': '', 'requested_n': d['requested']['n'], 'effective_n': d['effective']['n'], 'effective_G': d['effective']['G'], 'r': d['rank']['rank'], 'k': d['rank']['k'], 'failure_reason': failure})
        gates.append({'Variant_ID': name, 'Analysis_ID': d['Analysis_ID'], **actual, 'P1_associational_scope': 'ALLOWED_BY_DIRECT_AUTHORIZATION', 'numerical_status': 'PENDING_INDEPENDENT_QA' if success else 'FAIL', 'policy_reason': 'July2024 FFS obesity environment only; dated indication/channel scope unknown', 'identification_reason': 'observational reporting support, sparse/assigned pre quantities, comparator shocks and clocks unresolved', 'failure_reason': failure})
        statuses.append({'Variant_ID': name, 'numerical_pre_QA': 'PASS' if success else 'FAIL', 'metrics': metrics, 'failure_reason': failure})
        jw(WORK / (name + '_fit_complete.json'), statuses[-1])
        cw(OUT / '04D_B_Model_Results.csv', resultrows)
        cw(OUT / '04D_B_Model_Gates.csv', gates)
        jw(WORK / 'fit_summary.json', statuses)
    checkpoint('fits', {'models_attempted': 8, 'valid_before_independent_QA': sum((r['numerical_pre_QA'] == 'PASS' for r in statuses)), 'targets': len(resultrows)})
if __name__ == '__main__':
    assert len(sys.argv) == 2 and sys.argv[1] in ['intake', 'diagnostics', 'fits']
    globals()[sys.argv[1]]()
