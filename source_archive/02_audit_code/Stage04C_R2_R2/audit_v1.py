"""NEW_INDEPENDENT_IMPLEMENTATION. Explicit phases; no historical module imports.
All writes limited to this stage. Reviewed A-R3C core copied byte-for-byte.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import sys, csv, json, hashlib, math, stat, platform, traceback, subprocess, importlib.metadata as meta
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import linalg as la, optimize, stats
import stat_core_v1 as sc
ROOT = Path(__file__).absolute().parents[2]
CODE = ROOT / '02_audit_code/Stage04C_R2_R2'
OUT = ROOT / '03_audit_outputs/Stage04C_R2_R2'
WORK = OUT / '_working'
BW = ROOT / '03_audit_outputs/Stage04B/_working/R1'
CA = ROOT / '03_audit_outputs/Stage04C_A'
S3 = ROOT / '03_audit_outputs/Stage03'
SRC = Path('external_data')
STATES = set('AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())
COVER = set('CA DE KS MA MI MN MS NH PA RI VA WI'.split())
P1 = STATES - set('MO SC TN UT NC'.split())
C10 = ['2023Q2', '2023Q3', '2023Q4', '2024Q2', '2024Q3', '2024Q4', '2025Q1', '2025Q2', '2025Q3', '2025Q4']
MODELS = {'M01': ('04C-03', 'EL1', C10), 'M02': ('04C-03', 'F0', C10[:6]), 'M03': ('04C-03', 'F0', C10[2:]), 'M04': ('04C-05', 'F1', C10), 'M05': ('04C-05', 'F2', C10), 'M06': ('04C-05', 'F3', C10), 'M07': ('04C-05', 'F4', C10)}
FORMULAE = {'F0': 'SP+T+PA+PG+PAG', 'EL1': 'SP+T+EA+EG+EAG+LA+LG+LAG', 'F1': 'SP+ST+PA+PAG', 'F2': 'SP+PT+PG+PAG', 'F3': 'SP+ST+PT+PAG', 'F4': 'SP+T+PA+PG+PAG+tA+tG+tAG'}

def safe(p):
    p = Path(p).absolute()
    for q in [p, *p.parents]:
        if os.path.lexists(q):
            s = q.lstat()
            assert not (stat.S_ISLNK(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 1024), 'REPARSE ' + str(q)
    return p

def target(p):
    p = safe(p)
    assert p.is_relative_to(CODE) or p.is_relative_to(OUT)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def sha(p):
    h = hashlib.sha256()
    with safe(p).open('rb') as f:
        for v in iter(lambda: f.read(1048576), b''):
            h.update(v)
    return h.hexdigest()

def kh(v):
    return hashlib.sha256(''.join((str(x) + '\n' for x in v)).encode()).hexdigest()

def f17(v):
    return format(float(v), '.17g')

def rc(p):
    with safe(p).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def jr(p):
    return json.loads(safe(p).read_text(encoding='utf-8-sig'))

def clean(v):
    if isinstance(v, np.ndarray):
        return clean(v.tolist())
    if isinstance(v, np.generic):
        return clean(v.item())
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, (tuple, list)):
        return [clean(x) for x in v]
    if isinstance(v, float) and (not math.isfinite(v)):
        return str(v)
    return v

def jw(p, v):
    target(p).write_text(json.dumps(clean(v), ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

def cw(p, rows):
    assert rows
    fields = list(dict.fromkeys((k for r in rows for k in r)))
    with target(p).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(clean(rows))

def md(n, v):
    target(OUT / n).write_text(v.strip() + '\n', encoding='utf-8')

def files(p):
    for q in sorted(safe(p).iterdir()):
        if q.is_symlink() or getattr(q.lstat(), 'st_file_attributes', 0) & 1024:
            continue
        if q.is_dir():
            yield from files(q)
        elif q.is_file():
            yield q

def keys(f):
    return (f.state + '|' + f.calendar_quarter + '|' + f.analytic_brand).tolist()

def datahash(f):
    return kh((k + '|' + '|'.join((f17(r[c]) for c in ['y', 'N', 'offset', 'coverage_2024', 'noncoverage_2024', 'obesity', 'post', 'quarter_index'])) for k, (_, r) in zip(keys(f), f.iterrows())))

def xhash(X):
    return hashlib.sha256((str(X.shape) + '|' + str(X.dtype) + '|' + ','.join((f17(x) for x in X.ravel()))).encode()).hexdigest()

def info(f):
    return {'n': len(f), 'G': int(f.state.nunique()), 'coverage_G': int(f[f.coverage_2024 == 1].state.nunique()), 'noncoverage_G': int(f[f.coverage_2024 == 0].state.nunique()), 'order_hash': kh(keys(f)), 'keys_hash': kh(sorted(keys(f))), 'data_hash': datahash(f), 'quarters': sorted(f.calendar_quarter.unique().tolist())}

def frame(p):
    return pd.read_csv(safe(p), float_precision='round_trip', dtype={'ndc': str})

def writeframe(p, f):
    f.to_csv(target(p), index=False, float_format='%.17g')

def checkpoint(name, phase, objects, details):
    p = WORK / name / (phase + '_checkpoint.json')
    assert not p.exists(), 'No silent checkpoint replacement'
    jw(p, {'model': name, 'phase': phase, 'status': 'COMPLETE_VERIFIED', 'code': {str(q.relative_to(ROOT)): sha(q) for q in CODE.glob('*.py')}, 'objects': {str(q.relative_to(ROOT)): sha(q) for q in objects}, 'details': details})

def check(name, phase):
    p = WORK / name / (phase + '_checkpoint.json')
    if not p.exists():
        return False
    d = jr(p)
    assert d['status'] == 'COMPLETE_VERIFIED'
    for q, s in d['code'].items():
        assert sha(ROOT / q) == s, 'Code changed; versioned repair required'
    for q, s in d['objects'].items():
        assert sha(ROOT / q) == s, 'Checkpoint artifact changed'
    return True

def intake():
    assert not (WORK / 'protected_before.json').exists()
    paths = [ROOT / 'AGENTS.md', ROOT / 'PROJECT_CHARTER.md', ROOT / '03_audit_outputs/Issue_Register.csv']
    paths += [S3 / ('03_' + n) for n in ['Stage04_Protocol_Lock.csv', 'Stage04_Execution_Plan.md', 'Stage04_Decision_Gates.md', 'PPML_Separation_Convergence_Protocol.md', 'Independent_Replication_Spec.md', 'Fixed_Effect_Alternatives.md', 'Cluster_Inference_Plan.md', 'Model_Failure_Stop_Rules.md', 'Missingness_Suppression_Protocol.md']]
    for p in paths:
        safe(p).read_text(encoding='utf-8-sig')
    protected = set(paths)
    for base in ['00_original', '02_audit_code', '03_audit_outputs']:
        for p in files(ROOT / base):
            if p.is_relative_to(CODE) or p.is_relative_to(OUT):
                continue
            protected.add(p)
    for r in jr(BW / 'input_gate.json')['source_sha']:
        p = safe(r['Path'])
        assert sha(p) == r['SHA256']
        protected.add(p)
    before = [{'path': str(p), 'SHA256': sha(p), 'bytes': p.stat().st_size} for p in sorted(protected)]
    jw(WORK / 'protected_before.json', before)
    cw(OUT / '04C_R2_R2_Authority_Manifest.csv', [{'path': str(p), 'SHA256': sha(p), 'version': 'Stage03 v1.1 frozen / project authority'} for p in paths])
    prior = jr(CA / '_working/environment_gate.json')['packages']
    installed = {k: meta.version(k) for k in prior}
    assert installed == prior
    pipe = subprocess.run([sys.executable, '-I', '-B', '-m', 'pip', '--isolated', '--disable-pip-version-check', 'check'], capture_output=True, text=True)
    assert pipe.returncode == 0
    jw(OUT / '04C_R2_R2_Environment_Lock.json', {'G_ENV': 'PASS', 'python': sys.executable, 'version': platform.python_version(), 'packages': installed, 'pip_check': pipe.stdout, 'original_environment': 'NOT_VERIFIABLE; explicit independent venv', 'core_origin': 'static-reviewed Stage04A_R3C/stat_core.py byte-identical', 'core_SHA256': sha(CODE / 'stat_core_v1.py'), 'implementation': 'NEW_INDEPENDENT_IMPLEMENTATION', 'no_installs_downloads': True})
    plan = {'models': MODELS, 'formulae': FORMULAE, 'COMMON': 'FE_FAMILY includes frozen C-A F0 and M04-M07; EL1 compared to same BASE F0; fixed windows separate estimands, no universal intersection', 'rule': 'native certified-effective intersection; certificate union iterations max10; no beta/P selection', 'starts': ['exposure 1e-10', 'zero 1e-10', 'exposure 1e-12'], 'primary_core': 'static-reviewed native statsmodels QR IRLS / explicit scaled solve covariance', 'independent': 'direct Newton with Armijo exact objective delta, numpy rowwise Hessian/add.at sandwich', 'interpretation': 'RETAIN_DDD_WITH_ASSOCIATIONAL_INTERPRETATION', 'history_state': 'EXECUTION_UNKNOWN', 'thresholds': {'score': 1e-08, 'objective_last5': 1e-10, 'stability': 1e-06, 'maxiter_exclusive': 1000, 'symmetry': 1e-10, 'PSD_scaled': 1e-10, 'mu_atol': 1e-08, 'mu_rtol': 1e-06}}
    jw(WORK / 'frozen_plan.json', plan)
    print('INTAKE PASS', len(before), flush=True)

def inputs():
    assert (WORK / 'protected_before.json').exists()
    assert not (WORK / 'input_gate.json').exists()
    mapping = {r['NDC']: (r['Observed_Brands'], set(r['Observed_Product_Names'].split(';'))) for r in rc(ROOT / '03_audit_outputs/Stage02/02_NDC_Product_Mapping.csv')}
    pieces = []
    partition = []
    for year in [2023, 2024, 2025]:
        rel = f'raw/sdud/sdud_glp1_{year}.csv'
        allraw = pd.read_csv(safe(SRC / rel), dtype=str, keep_default_na=False)
        allraw['source_row'] = np.arange(1, len(allraw) + 1)
        allraw['source_file'] = rel
        keep = allraw.state.isin(P1) & allraw.analytic_brand.isin(['WEGOVY', 'OZEMPIC']) & (allraw.year.astype(int) * 4 + allraw.quarter.astype(int) >= 8094)
        raw = allraw[keep].copy()
        assert raw.ndc.str.fullmatch('\\d{11}').all() and raw.utilization_type.isin(['FFSU', 'MCOU']).all()
        assert all((r.ndc in mapping and r.analytic_brand == mapping[r.ndc][0] and (r.product_name.strip() in mapping[r.ndc][1]) for r in raw.itertuples()))
        partition.append({'source': rel, 'SHA256': sha(SRC / rel), 'read_rows': len(allraw), 'eligible_rows': len(raw), 'excluded_explicit_rows': int((~keep).sum()), 'unmapped_invalid_unresolved': 0})
        pieces.append(raw)
    raw = pd.concat(pieces, ignore_index=True)
    assert not raw.duplicated(['state', 'year', 'quarter', 'ndc', 'utilization_type']).any()
    assert raw.suppression_used.str.lower().isin(['true', 'false']).all()
    raw['suppressed'] = raw.suppression_used.str.lower().eq('true')
    raw['observed'] = pd.to_numeric(raw.number_of_prescriptions, errors='coerce')
    assert (np.isfinite(raw.loc[~raw.suppressed, 'observed']) & (raw.loc[~raw.suppressed, 'observed'] >= 0)).all() and raw.loc[raw.suppressed, 'observed'].isna().all()
    raw['calendar_quarter'] = raw.year + 'Q' + raw.quarter
    raw['assigned'] = raw.observed.where(~raw.suppressed, 5.5)
    old = frame(BW / 'raw_NDC_model_ledger.csv')
    assert len(raw) == len(old) == 5988
    assert raw[['source_file', 'source_row', 'state', 'calendar_quarter', 'ndc', 'utilization_type', 'analytic_brand']].astype(str).values.tolist() == old[['source_file', 'source_row', 'state', 'calendar_quarter', 'ndc', 'utilization_type', 'analytic_brand']].astype(str).values.tolist()
    assert raw.suppressed.tolist() == old.suppressed.tolist()
    assert np.array_equal(raw.loc[~raw.suppressed, 'observed'], old.loc[~old.suppressed, 'observed'])
    assignment = kh(('|'.join([r.source_file, str(r.source_row), r.state, r.calendar_quarter, r.ndc, r.utilization_type, f17(r.assigned)]) for r in raw.itertuples()))
    assert assignment == '70d375008fab37dc085746b703c9dcbfa797ca1b77d38e116bf4e9226aa89f16'
    e = pd.read_csv(safe(SRC / 'raw/enrollment/cms_monthly_enrollment_2019_2025.csv'), dtype=str, keep_default_na=False)
    e = e[(e.preliminary_or_updated == 'U') & (e.final_report == 'Y') & e.state_abbreviation.isin(STATES)].copy()
    assert not e.duplicated(['state_abbreviation', 'reporting_period']).any()
    e['value'] = pd.to_numeric(e.total_medicaid_enrollment, errors='coerce')
    e['valid'] = np.isfinite(e.value) & (e.value >= 0) & e.total_medicaid_enrollment__footnotes.str.strip().ne('Unable to Provide Data due to System Limitations')
    e['R1'] = e.value.where(e.valid)
    e['calendar_quarter'] = e.reporting_period.str[:4] + 'Q' + ((e.reporting_period.str[4:].astype(int) - 1) // 3 + 1).astype(str)
    pop = e.groupby(['state_abbreviation', 'calendar_quarter']).agg(N_R1=('R1', 'mean'), valid_months=('valid', 'sum'))
    pop.loc[pop.valid_months < 2, 'N_R1'] = np.nan
    presence = set(zip(raw.state, raw.calendar_quarter, raw.analytic_brand, raw.utilization_type))
    pairs = set()
    for s in P1:
        for q in C10:
            if all(((s, q, p, c) in presence for p in ['WEGOVY', 'OZEMPIC'] for c in ['FFSU', 'MCOU'])) and (s, q) in pop.index and (pop.loc[(s, q), 'valid_months'] >= 2) and (pop.loc[(s, q), 'N_R1'] > 0):
                pairs.add((s, q))
    ca = frame(CA / '04C_A_Model_Sample.csv')
    assert len(ca) == 348 and len(pairs) == 174 and (len(set(keys(ca))) == 348)
    assert set(zip(ca.state, ca.calendar_quarter)) == pairs
    agg = raw.groupby(['state', 'calendar_quarter', 'analytic_brand']).assigned.sum()
    diffs = []
    for r in ca.itertuples():
        assert r.calendar_quarter in C10 and r.quarter_index == r.year * 4 + r.quarter and (r.k == r.quarter_index - 8098)
        assert r.coverage_2024 == int(r.state in COVER) and r.noncoverage_2024 == 1 - r.coverage_2024 and (r.obesity == int(r.analytic_brand == 'WEGOVY')) and (r.post == int(r.quarter_index >= 8098))
        assert r.y == agg.loc[r.state, r.calendar_quarter, r.analytic_brand]
        expected = float(pop.loc[(r.state, r.calendar_quarter), 'N_R1'])
        assert abs(expected - r.N) <= 2 * np.spacing(expected) and abs(expected - r.N_R1) <= 2 * np.spacing(expected)
        assert r.valid_months == int(pop.loc[(r.state, r.calendar_quarter), 'valid_months']) and r.valid_months >= 2 and (r.N > 0) and (abs(math.log(r.N) - r.offset) < 3e-14)
        if r.N != r.N_R1:
            diffs.append({'sample_key': r.state + '|' + r.calendar_quarter + '|' + r.analytic_brand, 'N': f17(r.N), 'N_R1': f17(r.N_R1), 'difference': r.N - r.N_R1, 'raw_R1_reconstructed': f17(expected), 'preserved': 'YES; offset from frozen N, not silently rewritten'})
    assert len(diffs) == 30
    for _, g in ca.groupby(['state', 'calendar_quarter']):
        assert len(g) == 2 and set(g.analytic_brand) == {'OZEMPIC', 'WEGOVY'} and (g.N.nunique() == 1) and (g.offset.nunique() == 1)
    cw(OUT / '04C_R2_R2_Metadata_Float_Differences.csv', diffs)
    cw(OUT / '04C_R2_R2_Source_Partition.csv', partition)
    writeframe(WORK / 'BASE_input.csv', ca)
    writeframe(WORK / 'raw_rebuilt_ledger.csv', raw[['source_file', 'source_row', 'state', 'calendar_quarter', 'ndc', 'utilization_type', 'analytic_brand', 'suppressed', 'observed', 'assigned']])
    jw(WORK / 'input_gate.json', {'G_DATA': 'PASS', 'input': info(ca), 'source_assignment_hash': assignment, 'source_independently_rebuilt': True, 'population_raw_rebuilt': True, 'preserved_float_alias_rows': 30, 'R0': 'NOT_VERIFIABLE; R1 used', 'P1_requested_G': 46, 'P1_requested_groups': [12, 34], 'M1_pair_count': 174, 'code_sha': sha(CODE / 'audit_v1.py')})
    manifest = []
    sourcekeys = []
    support = []
    by = {(s, q, p): g for (s, q, p), g in raw.groupby(['state', 'calendar_quarter', 'analytic_brand'])}
    for m, (aid, kind, qs) in MODELS.items():
        f = ca[ca.calendar_quarter.isin(qs)].copy()
        d = WORK / m
        writeframe(d / 'requested.csv', f)
        manifest.append({'Analysis_ID': aid, 'Variant_ID': m, 'implementation': 'NEW_INDEPENDENT_IMPLEMENTATION', 'R': 'R1', 'M': 'M1', 'S': 'MID5.5', 'P': 'P1-46 12/34', 'window': 'DATA-C10 prescribed window subset', 'quarters': ';'.join(qs), 'formula': 'log(mu)=log(N_R1 frozen N alias)+' + FORMULAE[kind], 'FE_kind': kind, 'offset': 'preserved frozen log(N), 30 last-bit aliases disclosed', 'cluster': 'state CR1 effective rank / t(G-1)', 'COMMON_family': 'FE_FAMILY' if aid == '04C-05' else 'EL_BASE' if m == 'M01' else 'DISTINCT_WINDOW', 'source_hash': assignment, **info(f), 'G_DATA': 'PASS'})
        for r in f.itertuples():
            g = by[r.state, r.calendar_quarter, r.analytic_brand]
            sk = ['|'.join((str(getattr(s, c)) for c in ['source_file', 'source_row', 'state', 'calendar_quarter', 'analytic_brand', 'utilization_type', 'ndc'])) for s in g.itertuples()]
            sourcekeys.append({'Variant_ID': m, 'sample_key': r.state + '|' + r.calendar_quarter + '|' + r.analytic_brand, 'state': r.state, 'quarter': r.calendar_quarter, 'product': r.analytic_brand, 'y': r.y, 'N': f17(r.N), 'N_R1': f17(r.N_R1), 'offset': f17(r.offset), 'valid_months': r.valid_months, 'source_NDC_rows': len(g), 'source_key_hash': kh(sorted(sk)), 'source_keys': ';'.join(sorted(sk)), 'channels': 'FFSU;MCOU', 'requested': True})
        for cv in [0, 1]:
            for p in ['WEGOVY', 'OZEMPIC']:
                for q in qs + ['ALL_PRE', 'ALL_POST']:
                    g = f[(f.coverage_2024 == cv) & (f.analytic_brand == p) & (f.post == int(q == 'ALL_POST') if q.startswith('ALL_') else f.calendar_quarter == q)]
                    support.append({'Variant_ID': m, 'group': 'COVERAGE' if cv else 'NONCOVERAGE', 'product': p, 'quarter_or_period': q, 'n': len(g), 'G': g.state.nunique(), 'states': ';'.join(sorted(g.state.unique())), 'numeric_NDC_rows': int(g.actually_reported_NDC_rows.sum()), 'suppressed_NDC_rows': int(g.suppressed_NDC_rows.sum()), 'observed_rx': float(g.observed_rx_sum.sum()), 'assigned_5_5_rx': float(g.suppression_assigned_rx.sum()), 'keys_hash': kh(sorted(keys(g))), 'risk': 'SINGLE_STATE_IDENTIFICATION; SUPPRESSION_DEPENDENCE' if cv == 0 and q == 'ALL_PRE' else 'CHANGING_REPORTABILITY_SUPPORT'})
        checkpoint(m, 'input', [d / 'requested.csv', WORK / 'input_gate.json'], info(f))
    cw(OUT / '04C_R2_Protocol_and_Model_Manifest.csv', manifest)
    cw(OUT / '04C_R2_Source_and_Sample_Keys.csv', sourcekeys)
    cw(OUT / '04C_R2_Support_and_Preperiod_Audit.csv', support)
    print('INPUT PASS', info(ca), 'aliases', len(diffs), flush=True)

def design(f, kind):
    n = len(f)
    W = f.obesity.to_numpy()
    G = f.noncoverage_2024.to_numpy()
    P = f.post.to_numpy()
    names = ['Intercept']
    cols = [np.ones(n)]

    def dummy(values, prefix, alllevels=False):
        for v in sorted(set(values))[0 if alllevels else 1:]:
            names.append(prefix + v)
            cols.append(np.array([int(x == v) for x in values]))
    dummy((f.state + ':' + f.analytic_brand).tolist(), 'SP:')
    if kind in ['F0', 'EL1', 'F4']:
        dummy(f.calendar_quarter.tolist(), 'Q:')
    if kind in ['F1', 'F3']:
        dummy((f.state + ':' + f.calendar_quarter).tolist(), 'ST:', True)
    if kind in ['F2', 'F3']:
        dummy((f.analytic_brand + ':' + f.calendar_quarter).tolist(), 'PT:', True)
    inter = []
    if kind == 'EL1':
        for label, T in [('Early', (f.calendar_quarter == '2024Q2').to_numpy()), ('Late', (f.quarter_index >= 8099).to_numpy())]:
            inter += [(label + '×W', T * W), (label + '×NC', T * G), (label + '×DDD', T * W * G)]
    else:
        if kind not in ['F2', 'F3']:
            inter.append(('Post×W', P * W))
        if kind not in ['F1', 'F3']:
            inter.append(('Post×NC', P * G))
        inter.append(('Post×DDD', P * W * G))
    if kind == 'F4':
        t = f.quarter_index.to_numpy() - 8098
        inter += [('t×W', t * W), ('t×NC', t * G), ('t×DDD', t * W * G)]
    for name, c in inter:
        names.append(name)
        cols.append(c)
    return (np.column_stack(cols).astype(float), names)

def normalized_design(f, kind):
    X, names = design(f, kind)
    r = sc.rank_info(X)
    assert r['rank'] == r['rank_tau_0_1'] == r['rank_tau_10']
    targets = [i for i, n in enumerate(names) if n in ['Post×DDD', 'Early×DDD', 'Late×DDD']]
    ts = []
    for j in targets:
        wr = sc.rank_info(np.delete(X, j, axis=1))['rank']
        ts.append({'name': names[j], 'nominal_index': j, 'rank_without': wr, 'estimable': r['rank'] == wr + 1})
    assert all((t['estimable'] for t in ts)), 'NOT_IDENTIFIABLE target'
    if r['rank'] == X.shape[1]:
        selected = list(range(X.shape[1]))
    else:
        mandatory = [i for i, n in enumerate(names) if i == 0 or not n.startswith(('SP:', 'ST:', 'PT:', 'Q:'))]
        nuisance = [i for i in range(X.shape[1]) if i not in mandatory]
        scale = np.maximum(1, np.max(np.abs(X), axis=0))
        A = X / scale
        Q, R = la.qr(A[:, mandatory], mode='economic')
        assert sc.rank_info(X[:, mandatory])['rank'] == len(mandatory)
        residual = A[:, nuisance] - Q @ (Q.T @ A[:, nuisance])
        _, R, piv = la.qr(residual, mode='economic', pivoting=True)
        count = r['rank'] - len(mandatory)
        selected = sorted(mandatory + [nuisance[int(j)] for j in piv[:count]])
    Z = X[:, selected]
    zn = [names[j] for j in selected]
    rr = sc.rank_info(Z)
    assert rr['rank'] == Z.shape[1] == r['rank']
    qz, rz = la.qr(Z, mode='economic')
    mapcoef = la.solve_triangular(rz, qz.T @ X)
    span = float(np.max(np.abs(Z @ mapcoef - X)))
    assert span <= 1e-10
    for t in ts:
        t['index'] = zn.index(t['name'])
        assert sc.target_estimable(Z, t['index'])
    absorption = {'F1': 'PG/P/T; logN in ST', 'F2': 'PA/P/T', 'F3': 'PA/PG/P/T; logN in ST'}.get(kind, 'static lower terms/P in SP/T; all prescribed interactions retained')
    return (Z, zn, {'nominal_rank': r, 'normalized_rank': rr, 'targets': ts, 'nominal_names': names, 'selected_nominal_indices': selected, 'omitted_nuisance': [names[j] for j in range(len(names)) if j not in selected], 'span_residual_max': span, 'absorbed_terms': absorption, 'normalization': 'retain Intercept and EVERY explicit interaction/trend; pivoted QR selects only independent FE columns; omitted FE coefficients fixed zero'}, mapcoef)

def diagnose():
    records = []
    for m, (_, kind, qs) in MODELS.items():
        d = WORK / m
        if check(m, 'separation'):
            diag = jr(d / 'diagnostics.json')
        else:
            assert check(m, 'input')
            f = frame(d / 'requested.csv')
            requested = info(f)
            rounds = []
            for iteration in range(10):
                X, names, di, mapping = normalized_design(f, kind)
                y = f.y.to_numpy()
                zero = y == 0
                A = X / np.maximum(1, np.max(np.abs(X), axis=0))
                Az = A[zero]
                pos = ~zero
                lp = optimize.linprog(np.zeros(X.shape[1]), A_ub=np.vstack([Az, Az.sum(axis=0)]), b_ub=np.r_[np.zeros(zero.sum()), -1.0], A_eq=A[pos], b_eq=np.zeros(pos.sum()), bounds=[(None, None)] * X.shape[1], method='highs', options={'primal_feasibility_tolerance': 1e-09, 'dual_feasibility_tolerance': 1e-09})
                fullzero = [n for j, n in enumerate(names) if n.startswith(('SP:', 'ST:', 'PT:', 'Q:')) and np.any(X[:, j] != 0) and np.all(y[X[:, j] != 0] == 0)]
                rec = {'round': iteration, 'sample': info(f), 'zero_y': int(zero.sum()), 'all_zero_FE': fullzero, 'LP_status': int(lp.status), 'LP_message': lp.message, 'free_direction_bounds': True, 'normalization': 'sum(Xscaled_zero d)<=-1', 'certified_dropped_keys': []}
                if lp.status == 2:
                    rec['result'] = 'NO_SEPARATION_LP_INFEASIBLE'
                    rounds.append(rec)
                    break
                assert lp.success, 'SEPARATED_NOT_RESOLVED LP unreliable'
                margins = A @ lp.x
                eq = float(np.max(np.abs(margins[pos]))) if pos.any() else 0
                ub = float(np.max(margins[zero]))
                norm = float(margins[zero].sum())
                assert eq <= 1e-08 and ub <= 1e-08 and (norm <= -1 + 1e-08)
                drop = zero & (margins < -1e-08)
                assert drop.any()
                rec.update({'result': 'CERTIFIED_DIRECTION', 'equality_residual': eq, 'inequality_residual': ub, 'normalization_sum': norm, 'certified_dropped_keys': np.array(keys(f))[drop].tolist()})
                np.savez_compressed(target(d / f'LP_round{iteration}.npz'), direction_scaled=lp.x, direction_original=lp.x / np.maximum(1, np.max(np.abs(X), axis=0)), margins=margins, names=names, keys=keys(f))
                rounds.append(rec)
                f = f.loc[~drop].copy()
            else:
                raise RuntimeError('SEPARATED_NOT_RESOLVED max10 diagnostic rounds')
            writeframe(d / 'effective.csv', f)
            np.savez_compressed(target(d / 'input.npz'), X=X, y=f.y.to_numpy(), offset=f.offset.to_numpy(), clusters=f.state.to_numpy().astype(str), keys=np.array(keys(f)), names=np.array(names), nominal_to_normalized=mapping)
            di.update({'requested': requested, 'effective': info(f), 'kind': kind, 'X_hash': xhash(X), 'names_hash': kh(names), 'object_SHA256': sha(d / 'input.npz'), 'separation_rounds': rounds, 'G_TARGET': 'PASS', 'G_SEPARATION': 'PASS'})
            if kind in ['F1', 'F3']:
                q, r = la.qr(X, mode='economic')
                shift = la.solve_triangular(r, q.T @ f.offset.to_numpy())
                res = float(np.max(np.abs(X @ shift - f.offset.to_numpy())))
                assert res < 1e-10
                np.savez_compressed(target(d / 'offset_absorption.npz'), parameter_shift=shift, offset=f.offset.to_numpy())
                di['offset_absorption'] = {'max_span_residual': res, 'identity': 'offset+X*b = X*(b+shift); original offset kept in all fits', 'independent_population_effect': 'NOT_IDENTIFIABLE'}
            jw(d / 'diagnostics.json', di)
            diag = clean(di)
            checkpoint(m, 'design', [d / 'input.npz', d / 'diagnostics.json'], {'rank': di['normalized_rank']['rank'], 'targets': di['targets']})
            checkpoint(m, 'separation', [d / 'input.npz', d / 'effective.csv', d / 'diagnostics.json'], {'rounds': rounds, 'finite_MLE_possible': True})
        for t in diag['targets']:
            records.append({'Variant_ID': m, 'kind': kind, 'target': t['name'], 'requested_n': diag['requested']['n'], 'effective_n': diag['effective']['n'], 'G': diag['effective']['G'], 'nominal_columns': diag['nominal_rank']['k'], 'actual_nominal_rank': diag['nominal_rank']['rank'], 'normalized_columns': diag['normalized_rank']['k'], 'rank': diag['normalized_rank']['rank'], 'rank_without_target': t['rank_without'], 'estimable': t['estimable'], 'rank_tau_0_1': diag['normalized_rank']['rank_tau_0_1'], 'rank_tau_10': diag['normalized_rank']['rank_tau_10'], 'absorbed': diag['absorbed_terms'], 'omitted_FE': ';'.join(diag['omitted_nuisance']), 'span_residual_max': diag['span_residual_max'], 'X_hash': diag['X_hash'], 'sample_hash': diag['effective']['keys_hash'], 'offset_absorbed': kind in ['F1', 'F3']})
        print('DESIGN/SEPARATION', m, diag['effective']['n'], diag['normalized_rank']['rank'], diag['separation_rounds'][-1]['result'], flush=True)
    cw(OUT / '04C_R2_Design_Rank_and_Absorption.csv', records)

def fits():
    for m in MODELS:
        d = WORK / m
        if check(m, 'final'):
            print('REUSE VERIFIED', m, flush=True)
            continue
        assert check(m, 'separation')
        di = jr(d / 'diagnostics.json')
        z = np.load(safe(d / 'input.npz'), allow_pickle=False)
        X, y, off, cl = [z[k] for k in ['X', 'y', 'offset', 'clusters']]
        targets = di['targets']
        gate = {'Variant_ID': m, 'G_ENV': 'PASS', 'G_DATA': 'PASS', 'G_TARGET': 'PASS', 'G_SEPARATION': 'PASS', 'G_SOLVER': 'NOT_EXECUTED', 'G_COV': 'NOT_EXECUTED', 'G_NUMERICAL_QA': 'NOT_EXECUTED', 'G_POLICY': 'NOT_VERIFIABLE', 'G_IDENTIFICATION': 'NOT_VERIFIABLE', 'numerical_status': 'NOT_EXECUTED_BLOCKED', 'failure_reason': ''}
        fitobjects = []
        try:
            if not check(m, 'solver'):
                sols = []
                for label, exposure, tol in [('exposure', True, 1e-10), ('zero', False, 1e-10), ('tight', True, 1e-12)]:
                    p = d / (label + '_fit.npz')
                    j = d / (label + '_solver.json')
                    if p.exists() and j.exists():
                        assert jr(j)['input_SHA256'] == sha(d / 'input.npz') and jr(j)['core_SHA256'] == sha(CODE / 'stat_core_v1.py')
                        s = jr(j)
                        saved = np.load(safe(p), allow_pickle=False)
                        s['params'] = saved['params']
                        s['mu'] = saved['mu']
                        s['raw_score'] = saved['raw_score']
                    else:
                        start = np.zeros(X.shape[1])
                        start[0] = math.log(float(y.sum() / np.exp(off).sum())) if exposure else 0
                        s = sc.glm_fit(y, X, off, start, tol)
                        np.savez_compressed(target(p), params=s['params'], mu=s['mu'], raw_score=s['raw_score'])
                        jw(j, {**s, 'input_SHA256': sha(d / 'input.npz'), 'core_SHA256': sha(CODE / 'stat_core_v1.py'), 'start': label, 'tol': tol})
                    sols.append(s)
                    fitobjects += [p, j]
                    print('SOLVER', m, label, s['iterations'], s['solver_gate'], s['normalized_score'], flush=True)
                stability = max((abs(float(s['params'][t['index']] - sols[0]['params'][t['index']])) for s in sols for t in targets))
                jw(d / 'solver_gate.json', {'G_SOLVER': 'PASS' if all((s['solver_gate'] for s in sols)) and stability <= 1e-06 else 'FAIL', 'target_stability_max': stability, 'runs': [{k: s[k] for k in ['iterations', 'converged', 'normalized_score', 'last_five_deviance_relative_max', 'objective_explanation', 'warnings', 'solver_gate']} for s in sols]})
                checkpoint(m, 'solver', fitobjects + [d / 'solver_gate.json'], jr(d / 'solver_gate.json'))
            gate['G_SOLVER'] = jr(d / 'solver_gate.json')['G_SOLVER']
            assert gate['G_SOLVER'] == 'PASS', 'NUMERIC_FAIL solver gate'
            if not check(m, 'covariance'):
                cvobjects = []
                summ = []
                for label in ['exposure', 'zero', 'tight']:
                    s = np.load(safe(d / (label + '_fit.npz')), allow_pickle=False)
                    cv = sc.covariance(X, y, s['mu'], cl)
                    assert all((cv['V'][t['index'], t['index']] > 0 for t in targets))
                    np.savez_compressed(target(d / (label + '_cov.npz')), **{k: v for k, v in cv.items() if isinstance(v, np.ndarray)})
                    jw(d / (label + '_cov.json'), {k: v for k, v in cv.items() if not isinstance(v, np.ndarray)})
                    summ.append({k: v for k, v in cv.items() if not isinstance(v, np.ndarray)})
                    cvobjects += [d / (label + '_cov.npz'), d / (label + '_cov.json')]
                ref = np.load(d / 'exposure_cov.npz', allow_pickle=False)
                stability = all((np.all(np.abs(np.load(d / (l + '_cov.npz'), allow_pickle=False)['V'] - ref['V']) <= 1e-08 + 0.0001 * np.abs(ref['V'])) for l in ['zero', 'tight']))
                jw(d / 'covariance_gate.json', {'G_COV': 'PASS' if all((c['covariance_gate'] for c in summ)) and stability else 'FAIL', 'full_cov_stability': bool(stability), 'runs': summ})
                checkpoint(m, 'covariance', cvobjects + [d / 'covariance_gate.json'], jr(d / 'covariance_gate.json'))
            gate['G_COV'] = jr(d / 'covariance_gate.json')['G_COV']
            assert gate['G_COV'] == 'PASS', 'NUMERIC_FAIL covariance gate'
            gate['numerical_status'] = 'PENDING_INDEPENDENT_QA'
        except Exception as e:
            gate['numerical_status'] = 'NUMERIC_FAIL'
            gate['failure_reason'] = type(e).__name__ + ': ' + str(e)
            jw(d / 'fit_failure_v1.json', {'gate': gate, 'traceback': traceback.format_exc()})
        jw(d / 'primary_gate.json', gate)
        print('PRIMARY', m, gate['numerical_status'], gate['failure_reason'], flush=True)
if __name__ == '__main__':
    phase = sys.argv[1]
    try:
        globals()[phase]()
    except Exception:
        p = WORK / (phase + '_failure_v1.json')
        assert not p.exists()
        jw(p, {'traceback': traceback.format_exc()})
        raise
