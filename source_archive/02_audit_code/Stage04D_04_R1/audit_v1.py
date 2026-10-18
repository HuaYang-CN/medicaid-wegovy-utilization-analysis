"""04D-04 clean F0 only. Explicit phases, read-only history, hash checkpoints.
No historical research modules imported. No fits on module import.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import sys, csv, json, hashlib, math, stat, platform, traceback, subprocess, importlib.metadata as meta
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import linalg as la, optimize
import stat_core_v1 as sc
from covariance_v1 import native_factor
ROOT = Path(__file__).absolute().parents[2]
CODE = ROOT / '02_audit_code/Stage04D_04_R1'
OUT = ROOT / '03_audit_outputs/Stage04D_04_R1'
WORK = OUT / '_working'
CA = ROOT / '03_audit_outputs/Stage04C_A'
CW = CA / '_working'
BW = ROOT / '03_audit_outputs/Stage04B/_working/R1'
S3 = ROOT / '03_audit_outputs/Stage03'
R2 = ROOT / '03_audit_outputs/Stage04C_R2_R2'
SRC = Path('external_data')
STATES = set('AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())
COVER = set('CA DE KS MA MI MN MS NH PA RI VA WI'.split())
P1 = STATES - set('MO SC TN UT NC'.split())
C10 = ['2023Q2', '2023Q3', '2023Q4', '2024Q2', '2024Q3', '2024Q4', '2025Q1', '2025Q2', '2025Q3', '2025Q4']

def safe(p):
    p = Path(p).absolute()
    for q in [p, *p.parents]:
        if os.path.lexists(q):
            s = q.lstat()
            assert not (stat.S_ISLNK(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 1024), 'Reparse blocked ' + str(q)
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
    if isinstance(v, (list, tuple)):
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

def md(n, s):
    target(OUT / n).write_text(s.strip() + '\n', encoding='utf-8')

def files(p):
    for q in sorted(safe(p).iterdir()):
        if q.is_symlink() or getattr(q.lstat(), 'st_file_attributes', 0) & 1024:
            continue
        if q.is_dir():
            yield from files(q)
        elif q.is_file():
            yield q

def frame(p):
    return pd.read_csv(safe(p), float_precision='round_trip', dtype={'ndc': str})

def wf(p, f):
    f.to_csv(target(p), index=False, float_format='%.17g')

def keys(f):
    return (f.state + '|' + f.calendar_quarter + '|' + f.analytic_brand).tolist()

def dh(f):
    return kh((k + '|' + '|'.join((f17(r[c]) for c in ['y', 'N', 'offset', 'coverage_2024', 'noncoverage_2024', 'obesity', 'post', 'quarter_index'])) for k, (_, r) in zip(keys(f), f.iterrows())))

def xh(X):
    return hashlib.sha256((str(X.shape) + '|' + str(X.dtype) + '|' + ','.join((f17(x) for x in X.ravel()))).encode()).hexdigest()

def info(f):
    return {'n': len(f), 'G': int(f.state.nunique()), 'coverage_G': int(f[f.coverage_2024 == 1].state.nunique()), 'noncoverage_G': int(f[f.coverage_2024 == 0].state.nunique()), 'key_hash': kh(sorted(keys(f))), 'order_hash': kh(keys(f)), 'data_hash': dh(f), 'quarter_set': sorted(f.calendar_quarter.unique().tolist()), 'pre_NCW_G': int(f[(f.post == 0) & (f.obesity == 1) & (f.noncoverage_2024 == 1)].state.nunique())}

def seal(s, phase, objects, details, status='COMPLETE_VERIFIED'):
    p = WORK / s / (phase + '_checkpoint.json')
    assert not p.exists(), 'No silent checkpoint overwrite'
    jw(p, {'state': s, 'phase': phase, 'execution_status': status, 'artifact_integrity': 'VERIFIED', 'code_SHA256': {p.name: sha(p) for p in CODE.glob('*.py')}, 'objects': {str(p.relative_to(ROOT)): sha(p) for p in objects}, 'details': details})

def checked(s, phase):
    p = WORK / s / (phase + '_checkpoint.json')
    if not p.exists():
        return None
    v = jr(p)
    for n, h in v['code_SHA256'].items():
        assert sha(CODE / n) == h, 'Versioned repair required; code mismatch'
    for n, h in v['objects'].items():
        assert sha(ROOT / n) == h, 'Checkpoint artifact mismatch'
    return v

def validate(f):
    assert not f.duplicated(['state', 'calendar_quarter', 'analytic_brand']).any()
    assert f.state.isin(P1).all() and f.calendar_quarter.isin(C10).all() and f.analytic_brand.isin(['WEGOVY', 'OZEMPIC']).all()
    assert (f.quarter_index == f.year * 4 + f.quarter).all() and (f.post == (f.quarter_index >= 8098).astype(int)).all() and (f.k == f.quarter_index - 8098).all()
    assert (f.coverage_2024 == f.state.isin(COVER).astype(int)).all() and (f.noncoverage_2024 == 1 - f.coverage_2024).all() and (f.obesity == (f.analytic_brand == 'WEGOVY').astype(int)).all()
    assert np.isfinite(f.y).all() and (f.y >= 0).all() and np.isfinite(f.N).all() and (f.N > 0).all() and np.isfinite(f.offset).all() and (np.max(np.abs(np.log(f.N) - f.offset)) < 3e-14) and (f.valid_months >= 2).all()
    for _, g in f.groupby(['state', 'calendar_quarter']):
        assert len(g) == 2 and set(g.analytic_brand) == {'WEGOVY', 'OZEMPIC'} and (g.N.nunique() == g.offset.nunique() == 1)

def f0(f):
    n = len(f)
    cols = [np.ones(n)]
    names = ['Intercept']
    for vals, prefix in [((f.state + ':' + f.analytic_brand).tolist(), 'SP:'), (f.calendar_quarter.tolist(), 'Q:')]:
        for v in sorted(set(vals))[1:]:
            cols.append(np.array([int(x == v) for x in vals]))
            names.append(prefix + v)
    P = f.post.to_numpy()
    W = f.obesity.to_numpy()
    G = f.noncoverage_2024.to_numpy()
    for name, v in [('Post×W', P * W), ('Post×NC', P * G), ('Post×DDD', P * W * G)]:
        names.append(name)
        cols.append(v)
    return (np.column_stack(cols).astype(float), names)

def intake():
    assert not (WORK / 'protected_before.json').exists()
    authorities = [ROOT / 'AGENTS.md', ROOT / 'PROJECT_CHARTER.md', ROOT / '03_audit_outputs/Issue_Register.csv'] + [S3 / ('03_' + n) for n in ['Stage04_Protocol_Lock.csv', 'Stage04_Execution_Plan.md', 'Cluster_Inference_Plan.md', 'PPML_Separation_Convergence_Protocol.md', 'Model_Failure_Stop_Rules.md', 'Stage04_Decision_Gates.md', 'Independent_Replication_Spec.md']]
    for st, prefix in [('Stage04C_A', '04C_A_'), ('Stage04C_R1', '04C_R1_'), ('Stage04D_A', '04D_A_'), ('Stage04D_B', '04D_B_'), ('Stage04C_R2_R2', '04C_R2_')]:
        authorities += [p for p in (ROOT / '03_audit_outputs' / st).iterdir() if p.is_file() and p.name.startswith(prefix) and (p.suffix in ['.md', '.csv', '.json', '.txt'])]
    for p in authorities:
        safe(p).read_text(encoding='utf-8-sig')
    precheck = rc(ROOT / '03_audit_outputs/Stage04D_A/04D_A_State_Influence_Structural_Precheck.csv')
    assert len(precheck) == 138 and all((r['numeric_LOO_executed'] == 'False' for r in precheck))
    assert jr(R2 / '04C_R2_Independent_Numerical_QA.json')['numeric_pass_models'] == 7
    protected = set(authorities)
    for directory in ['00_original', '02_audit_code', '03_audit_outputs', 'feedback']:
        for p in files(ROOT / directory):
            if not (p.is_relative_to(CODE) or p.is_relative_to(OUT)):
                protected.add(p)
    for r in jr(BW / 'input_gate.json')['source_sha']:
        p = safe(r['Path'])
        assert sha(p) == r['SHA256']
        protected.add(p)
    before = []
    for i, p in enumerate(sorted(protected)):
        before.append({'path': str(p), 'SHA256': sha(p), 'bytes': p.stat().st_size})
        if (i + 1) % 500 == 0:
            print('PROTECTION_BASELINE', i + 1, flush=True)
    jw(WORK / 'protected_before.json', before)
    cw(OUT / '04D_04_Authority_Manifest.csv', [{'path': str(p), 'SHA256': sha(p), 'role': 'frozen v1.1 / accepted-stage evidence, not new LOO'} for p in authorities])
    prior = jr(R2 / '04C_R2_R2_Environment_Lock.json')['packages']
    installed = {n: meta.version(n) for n in prior}
    assert installed == prior and platform.python_version() == '3.13.5'
    assert sha(CODE / 'stat_core_v1.py') == sha(ROOT / '02_audit_code/Stage04C_R2_R2/stat_core_v1.py')
    pipe = subprocess.run([sys.executable, '-I', '-B', '-m', 'pip', '--isolated', '--disable-pip-version-check', 'check'], capture_output=True, text=True)
    assert pipe.returncode == 0
    jw(OUT / '04D_04_Environment_Lock.json', {'G_ENV': 'PASS', 'interpreter': sys.executable, 'Python': platform.python_version(), 'packages': installed, 'pip_check': pipe.stdout, 'original_research_environment': 'NOT_VERIFIABLE; accepted project venv reused', 'reviewed_native_core_SHA256': sha(CODE / 'stat_core_v1.py'), 'pure_function_lineage': jr(WORK / 'copied_function_lineage.json'), 'install_download_network': False})
    jw(WORK / 'frozen_plan.json', {'Analysis_ID': '04D-04', 'F': 'F0 SP+T+PA+PG+PAG', 'domain_states': sorted(P1), 'base': 'Stage04C_A PRIMARY_BINARY_CLEAN; reuse only, no fit', 'data': 'P1-46 R1 M1 MID5.5 DATA-C10', 'quarter_index': 'actual year*4+quarter; Q1 excluded; post from8098', 'inference': 'full stable Gram sandwich, CR1 G/(G-1)*(n-1)/(n-r), t(G-1)', 'primary_runs': ['exposure tol1e-10', 'zero tol1e-10', 'exposure tol1e-12'], 'independent_path': 'copied accepted direct Newton + einsum/add.at + unscaled numpy.solve Gram; not native fit/cov', 'separation': 'free-direction LP, primal/dual1e-9, residual1e-8; certified deletes only', 'rank': 'max(n,k)*eps*smax, column maxabs scale; .1/10 checks', 'score': 1e-08, 'last5_deviance': 1e-10, 'maxiter_exclusive': 1000, 'target_stability': 1e-06, 'symmetry_scaled_PSD': 1e-10, 'influence_trigger': 'sign change OR abs(delta_beta)>0.5; disclose size near zero; never remove states by influence', 'one_step': 'IJ=-H^-1 U_g infinitesimal; deletion Newton on actual retained estimable F0 at full predictions; NM target no approximation reported', 'leverage': 'weighted hat cluster block trace/max eigenvalue; all SP clusters expected unit eigenvalues; additional DDD residualized information share', 'no_other_stage': True})
    print('INTAKE PASS', len(before), flush=True)

def baseline():
    import numerical_qa_v1 as iq
    assert (WORK / 'protected_before.json').exists() and (not (OUT / '04D_04_Base_Model_Reconciliation.json').exists())
    f = frame(CA / '04C_A_Model_Sample.csv')
    validate(f)
    assert len(f) == 348 and info(f)['G'] == 29 and (info(f)['coverage_G'] == 10) and (info(f)['noncoverage_G'] == 19)
    z = np.load(safe(CW / 'PRIMARY_BINARY_CLEAN_design.npz'), allow_pickle=False)
    fit = np.load(safe(CW / 'primary_run_1_full.npz'), allow_pickle=False)
    X, names = f0(f)
    old = rc(CA / '04C_A_Primary_PPML_Results.csv')[0]
    assert xh(X) == old['X_hash'] and dh(f) == old['input_hash']
    assert np.array_equal(X, z['X']) and np.array_equal(f.y, z['y']) and np.array_equal(f.offset, z['offset']) and (keys(f) == z['keys'].tolist()) and (names == z['names'].tolist())
    ri = sc.rank_info(X)
    assert ri['rank'] == ri['rank_tau_0_1'] == ri['rank_tau_10'] == X.shape[1] == 70
    assert all((jr(CW / 'primary_gates.json')[g] == 'PASS' for g in ['G_ENV', 'G_DATA', 'G_TARGET', 'G_SOLVER', 'G_COV', 'G_QA']))
    raw = rc(BW / 'raw_NDC_model_ledger.csv')
    by = {}
    for r in raw:
        by.setdefault((r['state'], r['calendar_quarter'], r['analytic_brand']), []).append(r)
    inventory = {r['Path']: r['SHA256'] for r in rc(ROOT / '03_audit_outputs/Stage04B/04B_R1_File_Inventory.csv')}
    for p in [BW / 'raw_NDC_model_ledger.csv', BW / 'quarterly_population_ledger.csv']:
        assert sha(p) == inventory[str(p)]
    pop = {(r['state'], r['calendar_quarter']): r for r in rc(BW / 'quarterly_population_ledger.csv')}
    aliases = []
    for r in f.itertuples():
        g = by[r.state, r.calendar_quarter, r.analytic_brand]
        sup = [x for x in g if x['suppressed'].lower() == 'true']
        obs = [x for x in g if x['suppressed'].lower() == 'false']
        assert {x['utilization_type'] for x in g} == {'FFSU', 'MCOU'}
        assert len(sup) == r.suppressed_NDC_rows and len(obs) == r.actually_reported_NDC_rows and (sum((float(x['observed']) for x in obs)) == r.observed_rx_sum) and (len(sup) * 5.5 == r.suppression_assigned_rx) and (r.y == r.observed_rx_sum + r.suppression_assigned_rx)
        qp = pop[r.state, r.calendar_quarter]
        pn = float(qp['N_R1'])
        assert r.valid_months == int(qp['valid_months']) >= 2 and abs(r.N - pn) <= 2 * np.spacing(pn)
        if r.N != r.N_R1:
            aliases.append({'sample_key': r.state + '|' + r.calendar_quarter + '|' + r.analytic_brand, 'N': f17(r.N), 'N_R1': f17(r.N_R1), 'difference': r.N - r.N_R1, 'preserved': True})
    assert len(aliases) == 30
    cw(OUT / '04D_04_Preserved_Population_Aliases.csv', aliases)
    wf(WORK / 'BASE_input.csv', f)
    sourceQA = iq.source_qa()
    cv = native_factor(X, z['y'], fit['mu'], z['clusters'])
    icv = iq.sandwich(X, z['y'], fit['mu'], z['clusters'])
    infl = np.linalg.solve(icv['H'], icv['cluster_scores'].T)
    iv = icv['CR1'] * np.einsum('ig,jg->ij', infl, infl)
    assert cv['covariance_gate'] and iq.close(cv['V'], fit['V'], 1e-08, 0.0001) and iq.close(iv, fit['V'], 1e-08, 0.0001)
    j = names.index('Post×DDD')
    inf = iq.infer(float(fit['params'][j]), float(fit['V'][j, j]), 29)
    expected = {'beta': -0.0002445627211488952, 'SE': 0.3286774412407873, 'IRR': 0.9997554671818756, 'CI_low': 0.5099157409657245, 'CI_high': 1.9601493224490112, 'P': 0.9994115852180573}
    assert all((iq.close(inf[k], v, 1e-12, 1e-10) for k, v in expected.items()))
    assert sc.normalized_score(X, z['y'], fit['mu'])[1] <= 1e-08
    obj = {'status': 'PASS_REUSED_FROZEN_NO_BASE_FIT', 'sample': info(f), 'rank': ri, 'base_inference': inf, 'CR1': cv['CR1'], 'DDD_index': j, 'X_hash': xh(X), 'source_checks': sourceQA, 'N_N_R1_aliases_preserved': 30, 'full_covariance_native_independent_vs_saved': 'PASS', 'full_covariance_max_abs_diff': float(np.max(np.abs(iv - fit['V']))), 'object_SHA256': {n: sha(CW / n) for n in ['PRIMARY_BINARY_CLEAN_design.npz', 'primary_run_1_full.npz', 'primary_gates.json']}, 'C_A_sample_SHA256': sha(CA / '04C_A_Model_Sample.csv'), 'source_component_hashes': jr(BW / 'input_gate.json')['source_sha'], 'base_new_fits': 0, 'interpretation': 'RETAIN_DDD_WITH_ASSOCIATIONAL_INTERPRETATION'}
    jw(OUT / '04D_04_Base_Model_Reconciliation.json', obj)
    print('BASE F0 VERIFIED/REUSED no fit', info(f), flush=True)

def diagnose():
    base = frame(WORK / 'BASE_input.csv')
    assert jr(OUT / '04D_04_Base_Model_Reconciliation.json')['status'] == 'PASS_REUSED_FROZEN_NO_BASE_FIT'
    manifest = []
    for s in sorted(P1):
        d = WORK / s
        removed = base[base.state == s]
        f = base[base.state != s].copy()
        nremoved = len(removed)
        sample = info(f)
        if checked(s, 'matrix'):
            di = jr(d / 'diagnostics.json')
        else:
            if not checked(s, 'input'):
                if nremoved:
                    wf(d / 'requested.csv', f)
                    inp = d / 'requested.csv'
                else:
                    inp = WORK / 'BASE_input.csv'
                jw(d / 'deletion.json', {'removed_state': s, 'removed_rows': nremoved, 'removed_keys': keys(removed), 'removed_keys_hash': kh(keys(removed)), 'requested': sample, 'base_key_hash': info(base)['key_hash'], 'policy_group': 'COVERAGE' if s in COVER else 'NONCOVERAGE', 'whole_state_both_products_all_quarters': True})
                seal(s, 'input', [inp, d / 'deletion.json'], {'nremoved': nremoved, 'requested': sample}, 'COMPLETE_VERIFIED' if nremoved else 'NO_EFFECTIVE_ROWS')
            if not nremoved:
                di = {'state': s, 'status': 'NO_EFFECTIVE_ROWS', 'nremoved': 0, 'requested': sample, 'effective': sample, 'rank': '', 'nominal_columns': '', 'target_estimable': '', 'G_TARGET': 'NOT_APPLICABLE', 'G_SEPARATION': 'NOT_APPLICABLE', 'reason': '17-state no-row audit domain; no distinct model/fit; baseline sample would be unchanged'}
                jw(d / 'diagnostics.json', di)
                seal(s, 'matrix', [d / 'diagnostics.json'], di, 'NO_EFFECTIVE_ROWS')
                seal(s, 'separation', [d / 'diagnostics.json'], di, 'NO_EFFECTIVE_ROWS')
            else:
                validate(f)
                X, names = f0(f)
                r = sc.rank_info(X)
                j = names.index('Post×DDD')
                without = sc.rank_info(np.delete(X, j, axis=1))
                assert r['rank'] == r['rank_tau_0_1'] == r['rank_tau_10']
                A = X / r['scale']
                U, sp, V = la.svd(np.delete(A, j, axis=1), full_matrices=False)
                basis = U[:, sp > without['threshold']]
                res = A[:, j] - basis @ (basis.T @ A[:, j])
                est = r['rank'] == without['rank'] + 1
                q, qr, piv = la.qr(A, mode='economic', pivoting=True)
                qrank = int((np.abs(np.diag(qr)) > r['threshold']).sum())
                assert qrank == r['rank']
                y = f.y.to_numpy()
                zero = y == 0
                Az = A[zero]
                lp = optimize.linprog(np.zeros(X.shape[1]), A_ub=np.vstack([Az, Az.sum(axis=0)]), b_ub=np.r_[np.zeros(zero.sum()), -1.0], A_eq=A[~zero], b_eq=np.zeros((~zero).sum()), bounds=[(None, None)] * X.shape[1], method='highs', options={'primal_feasibility_tolerance': 1e-09, 'dual_feasibility_tolerance': 1e-09})
                assert lp.status == 2, 'New separation requires explicit versioned certificate handling; no subjective drop'
                zf = [n for jj, n in enumerate(names) if n.startswith(('SP:', 'Q:')) and np.any(X[:, jj] != 0) and np.all(y[X[:, jj] != 0] == 0)]
                collinear = []
                for term in ['Post×W', 'Post×NC', 'Post×DDD']:
                    jj = names.index(term)
                    w = sc.rank_info(np.delete(X, jj, axis=1))['rank']
                    collinear.append({'term': term, 'rank_without': w, 'individually_estimable': r['rank'] == w + 1})
                di = {'state': s, 'nremoved': nremoved, 'requested': sample, 'effective': sample, 'rank': r, 'rank_without_DDD': without['rank'], 'nominal_columns': X.shape[1], 'target_estimable': est, 'target_residual_norm': float(la.norm(res)), 'QR_rank': qrank, 'explicit_lower_target_terms': collinear, 'DDD_index': j, 'names': names, 'X_hash': xh(X), 'G_TARGET': 'PASS' if est else 'FAIL', 'G_SEPARATION': 'PASS', 'LP_status': int(lp.status), 'LP_message': lp.message, 'LP_bounds': 'free', 'LP_normalization': 'sum(Xscaled_zero d)<=-1', 'zero_outcomes': int(zero.sum()), 'all_zero_FE': zf, 'separated_rows': 0, 'separation_drop_keys': [], 'status': 'DESIGN_READY' if est else 'NOT_IDENTIFIABLE', 'reason': '' if est else 'DDD target lies in nuisance span; noncoverage true-pre support absent after deletion'}
                np.savez_compressed(target(d / 'input.npz'), X=X, y=y, offset=f.offset.to_numpy(), clusters=f.state.to_numpy().astype(str), keys=keys(f), names=names, rank_spectrum=r['spectrum'], null_space=la.null_space(A, rcond=r['threshold'] / r['spectrum'][0]))
                wf(d / 'effective.csv', f)
                jw(d / 'diagnostics.json', di)
                seal(s, 'matrix', [d / 'input.npz', d / 'diagnostics.json'], {'G_TARGET': di['G_TARGET'], 'actual_rank': r['rank'], 'columns': len(names), 'target_estimable': est})
                seal(s, 'separation', [d / 'diagnostics.json', d / 'effective.csv'], {'G_SEPARATION': 'PASS', 'LP_status': 2, 'certified_drops': 0})
                if s == 'NM':
                    assert not est and len(f) == 332 and (r['rank'] == without['rank'] == 66) and (X.shape[1] == 68) and (sample['pre_NCW_G'] == 0)
                    assert np.array_equal(X[:, names.index('Post×NC')], f.noncoverage_2024) and np.array_equal(X[:, j], f.noncoverage_2024 * f.obesity)
                    jw(d / 'NM_collinearity_certificate.json', {'rank': 66, 'columns': 68, 'rank_without_DDD': 66, 'noncoverage_pre_G': 0, 'PG_equals_static_G': True, 'PAG_equals_static_GA': True, 'static_G_GA_in_state_product_span': True, 'lower_terms_retained': True, 'no_legal_original_DDD_estimate': True})
            print('DESIGN', s, nremoved, di['status'], di['rank']['rank'] if isinstance(di['rank'], dict) else '', flush=True)
        manifest.append({'Analysis_ID': '04D-04', 'Variant_ID': 'LOO_' + s, 'removed_state': s, 'policy_group': 'COVERAGE' if s in COVER else 'NONCOVERAGE', 'effective_rows_removed': nremoved, 'F': 'F0 SP+T+PA+PG+PAG', 'rules': 'P1-46/R1/M1/MID5.5/DATA-C10', 'requested_quarters': ';'.join(C10), 'requested_n': sample['n'], 'effective_n': di['effective']['n'], 'G': sample['G'], 'coverage_G': sample['coverage_G'], 'noncoverage_G': sample['noncoverage_G'], 'pre_NCW_G': sample['pre_NCW_G'], 'request_key_hash': sample['key_hash'], 'effective_key_hash': di['effective']['key_hash'], 'data_hash': sample['data_hash'], 'input_object_SHA256': sha(d / 'input.npz') if nremoved else sha(WORK / 'BASE_input.csv'), 'design_state': di['status'], 'interpretation': 'RETAIN_DDD_WITH_ASSOCIATIONAL_INTERPRETATION'})
    cw(OUT / '04D_04_Protocol_and_Model_Manifest.csv', manifest)
    print('46 STATE DESIGN DISPOSITION COMPLETE', flush=True)

def fits():
    for s in sorted(P1):
        d = WORK / s
        if checked(s, 'final'):
            print('REUSE CURRENT DISPOSITION', s, flush=True)
            continue
        assert checked(s, 'matrix') and checked(s, 'separation')
        di = jr(d / 'diagnostics.json')
        gate = {'state': s, 'G_ENV': 'PASS', 'G_DATA': 'PASS', 'G_TARGET': di['G_TARGET'], 'G_SEPARATION': di['G_SEPARATION'], 'G_SOLVER': 'NOT_EXECUTED', 'G_COV': 'NOT_EXECUTED', 'G_QA': 'NOT_EXECUTED', 'G_POLICY': 'NOT_VERIFIABLE', 'G_IDENTIFICATION': 'NOT_VERIFIABLE', 'status': di['status'], 'reason': di['reason'], 'actual_native_fit': False}
        if di['status'] in ['NO_EFFECTIVE_ROWS', 'NOT_IDENTIFIABLE']:
            gate['status'] = di['status']
            jw(d / 'primary_gate.json', gate)
            for phase in ['solver', 'covariance', 'QA']:
                seal(s, phase, [d / 'primary_gate.json'], {'status': gate['status'], 'model_fit': False, 'reason': gate['reason']}, 'NOT_EXECUTED_BLOCKED' if di['status'] == 'NOT_IDENTIFIABLE' else 'NO_EFFECTIVE_ROWS')
            jw(d / 'final_gate.json', gate)
            seal(s, 'final', [d / 'final_gate.json'], gate, di['status'])
            continue
        try:
            ob = np.load(d / 'input.npz', allow_pickle=False)
            X, y, off, cl = [ob[k] for k in ['X', 'y', 'offset', 'clusters']]
            assert sc.rank_info(X)['rank'] == X.shape[1]
            solutions = []
            if not checked(s, 'solver'):
                objects = []
                for label, exposure, tol in [('exposure', True, 1e-10), ('zero', False, 1e-10), ('tight', True, 1e-12)]:
                    p = d / (label + '_fit.npz')
                    q = d / (label + '_solver.json')
                    if p.exists() and q.exists():
                        sol = jr(q)
                        sv = np.load(p, allow_pickle=False)
                        assert sol['input_SHA256'] == sha(d / 'input.npz') and sol['core_SHA256'] == sha(CODE / 'stat_core_v1.py')
                        assert np.array_equal(sol['params'], sv['params']) and np.array_equal(sol['mu'], sv['mu'])
                        sol.update({'params': sv['params'], 'mu': sv['mu'], 'raw_score': sv['raw_score']})
                    else:
                        start = np.zeros(X.shape[1])
                        start[0] = math.log(float(y.sum() / np.exp(off).sum())) if exposure else 0
                        sol = sc.glm_fit(y, X, off, start, tol)
                        np.savez_compressed(target(p), params=sol['params'], mu=sol['mu'], raw_score=sol['raw_score'])
                        jw(q, {**sol, 'input_SHA256': sha(d / 'input.npz'), 'core_SHA256': sha(CODE / 'stat_core_v1.py'), 'label': label, 'tol': tol})
                    solutions.append(sol)
                    objects += [p, q]
                    print('SOLVER', s, label, sol['iterations'], sol['solver_gate'], flush=True)
                j = di['DDD_index']
                bs = max((abs(float(v['params'][j] - solutions[0]['params'][j])) for v in solutions))
                mustable = all((np.all(np.abs(v['mu'] - solutions[0]['mu']) <= 1e-08 + 1e-06 * np.abs(solutions[0]['mu'])) for v in solutions))
                sg = {'G_SOLVER': 'PASS' if all((v['solver_gate'] for v in solutions)) and bs <= 1e-06 and mustable else 'FAIL', 'target_stability_max': bs, 'mu_stability': mustable, 'runs': [{k: v[k] for k in ['iterations', 'converged', 'normalized_score', 'last_five_deviance_relative_max', 'objective_explanation', 'warnings', 'solver_gate']} for v in solutions]}
                jw(d / 'solver_gate.json', sg)
                seal(s, 'solver', objects + [d / 'solver_gate.json'], sg)
            gate['G_SOLVER'] = jr(d / 'solver_gate.json')['G_SOLVER']
            gate['actual_native_fit'] = True
            assert gate['G_SOLVER'] == 'PASS', 'Solver gate failed'
            if not checked(s, 'covariance'):
                objects = []
                covs = []
                for label in ['exposure', 'zero', 'tight']:
                    sv = np.load(d / (label + '_fit.npz'), allow_pickle=False)
                    cv = native_factor(X, y, sv['mu'], cl)
                    assert cv['V'][di['DDD_index'], di['DDD_index']] > 0
                    np.savez_compressed(target(d / (label + '_cov.npz')), **{k: v for k, v in cv.items() if isinstance(v, np.ndarray)})
                    jw(d / (label + '_cov.json'), {k: v for k, v in cv.items() if not isinstance(v, np.ndarray)})
                    objects += [d / (label + '_cov.npz'), d / (label + '_cov.json')]
                    covs.append(cv)
                stable = all((np.all(np.abs(v['V'] - covs[0]['V']) <= 1e-08 + 0.0001 * np.abs(covs[0]['V'])) for v in covs))
                cg = {'G_COV': 'PASS' if all((v['covariance_gate'] for v in covs)) and stable else 'FAIL', 'full_covariance_stability': stable}
                jw(d / 'covariance_gate.json', cg)
                seal(s, 'covariance', objects + [d / 'covariance_gate.json'], cg)
            gate['G_COV'] = jr(d / 'covariance_gate.json')['G_COV']
            assert gate['G_COV'] == 'PASS', 'Covariance gate failed'
            gate['status'] = 'PENDING_INDEPENDENT_QA'
        except Exception as e:
            gate['status'] = 'NUMERIC_FAIL'
            gate['reason'] = type(e).__name__ + ': ' + str(e)
            jw(d / 'fit_failure_v1.json', {'gate': gate, 'traceback': traceback.format_exc()})
        jw(d / 'primary_gate.json', gate)
        print('PRIMARY', s, gate['status'], gate['reason'], flush=True)

def qa():
    import numerical_qa_v1 as iq
    summary = []
    for s in sorted(P1):
        d = WORK / s
        if checked(s, 'final'):
            gate = jr(d / 'final_gate.json')
            summary.append(jr(d / 'independent_QA.json') if (d / 'independent_QA.json').exists() else {'state': s, 'status': gate['status'], 'model_fit': False, 'reason': gate['reason']})
            continue
        gate = jr(d / 'primary_gate.json')
        checks = {}
        if gate['status'] != 'PENDING_INDEPENDENT_QA':
            obj = {'state': s, 'status': gate['status'], 'reason': gate['reason'], 'independent_optimization': False}
            jw(d / 'independent_QA.json', obj)
            seal(s, 'QA', [d / 'independent_QA.json'], obj, 'NOT_EXECUTED_BLOCKED')
            jw(d / 'final_gate.json', gate)
            seal(s, 'final', [d / 'final_gate.json', d / 'independent_QA.json'], gate, 'FAILED')
            summary.append(obj)
            continue
        try:
            assert checked(s, 'covariance')
            di = jr(d / 'diagnostics.json')
            z = np.load(d / 'input.npz', allow_pickle=False)
            X, y, off, cl = [z[k] for k in ['X', 'y', 'offset', 'clusters']]
            native = np.load(d / 'exposure_fit.npz', allow_pickle=False)
            nv = np.load(d / 'exposure_cov.npz', allow_pickle=False)
            cm = jr(d / 'exposure_cov.json')
            j = di['DDD_index']
            b, mu, hist = iq.newton(y, X, off, d)
            cv = iq.sandwich(X, y, mu, cl)
            influence = np.linalg.solve(cv['H'], cv['cluster_scores'].T)
            cv['direct_product_V'] = cv['V']
            cv['V'] = cv['CR1'] * np.einsum('ig,jg->ij', influence, influence)
            cv['cluster_influence'] = influence.T
            np.savez_compressed(target(d / 'independent_objects.npz'), params=b, mu=mu, **cv)
            qq, rr = np.linalg.qr(X, mode='reduced')
            recovered = np.linalg.solve(rr, qq.T @ (np.log(native['mu']) - off))
            ind = iq.infer(float(b[j]), float(cv['V'][j, j]), cv['G'])
            primary = sc.inference(native['params'][j], nv['V'][j, j], cm['G'])
            same = iq.infer(float(native['params'][j]), float(nv['V'][j, j]), cm['G'])
            sym = float(np.linalg.norm(cv['V'] - cv['V'].T, 2) / max(np.linalg.norm(cv['V'], 2), np.finfo(float).eps))
            vs = (cv['V'] + cv['V'].T) / 2
            emin = float(np.linalg.eigvalsh(vs)[0])
            scale = float(np.linalg.norm(vs, 2))
            checks = {'beta_all': iq.close(b, native['params'], 1e-06, 1e-06), 'mu_all': iq.close(mu, native['mu'], 1e-08, 1e-06), 'full_covariance': iq.close(cv['V'], nv['V'], 1e-08, 0.0001), 'Hessian': iq.close(cv['H'], nv['H'], 1e-08, 1e-06), 'beta_mu_QR_identity': iq.close(recovered, native['params'], 1e-08, 1e-06), 'CR1': abs(cv['CR1'] - cm['CR1']) < 1e-14, 'n_G_r': (cv['n'], cv['G'], cv['r']) == (di['effective']['n'], di['effective']['G'], di['rank']['rank']), 'SE': iq.close(ind['SE'], primary['SE'], 1e-06, 0.0001), 'target_beta': iq.close(ind['beta'], primary['beta'], 1e-06, 1e-06), 'native_t_arithmetic': all((iq.close(same[k], primary[k], 1e-12, 1e-10) for k in ['IRR', 'CI_low', 'CI_high', 'P'])), 'positive_target_variance': cv['V'][j, j] > 0, 'symmetry': sym <= 1e-10, 'scaled_PSD': emin >= -1e-10 * max(scale, np.finfo(float).eps), 'finite': bool(np.isfinite(cv['V']).all())}
            obj = {'state': s, 'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks, 'independent_result': ind, 'native_result': primary, 'iterations': len(hist) - 1, 'score': hist[-1]['score'], 'beta_max_abs_diff': float(np.max(np.abs(b - native['params']))), 'mu_max_abs_diff': float(np.max(np.abs(mu - native['mu']))), 'cov_max_abs_diff': float(np.max(np.abs(cv['V'] - nv['V']))), 'symmetry': sym, 'minimum_eigenvalue': emin, 'PSD_scale': scale, 'input_SHA256': sha(d / 'input.npz'), 'actual_independent_same_model_optimization': True}
            jw(d / 'independent_QA.json', obj)
            assert obj['status'] == 'PASS', 'Independent QA disagreement ' + str([k for k, v in checks.items() if not v])
            gate['G_QA'] = 'PASS'
            gate['status'] = 'NUMERIC_PASS'
            seal(s, 'QA', [d / 'independent_objects.npz', d / 'independent_QA.json', d / 'independent_Newton_history_v1.json'], obj)
        except Exception as e:
            gate['G_QA'] = 'FAIL'
            gate['status'] = 'NUMERIC_FAIL'
            gate['reason'] = type(e).__name__ + ': ' + str(e)
            obj = {'state': s, 'status': 'FAIL', 'checks': checks, 'reason': gate['reason'], 'traceback': traceback.format_exc()}
            jw(d / 'independent_QA_failure_v1.json', obj)
        jw(d / 'final_gate.json', gate)
        seal(s, 'final', [d / 'final_gate.json', d / ('independent_QA.json' if (d / 'independent_QA.json').exists() else 'independent_QA_failure_v1.json')], gate, 'COMPLETE_VERIFIED' if gate['status'] == 'NUMERIC_PASS' else 'FAILED')
        summary.append(obj)
        print('INDEPENDENT_QA', s, gate['status'], gate['reason'], flush=True)
    jw(OUT / '04D_04_Independent_Numerical_QA.json', {'status': 'PASS' if all((r['status'] in ['PASS', 'NO_EFFECTIVE_ROWS', 'NOT_IDENTIFIABLE'] for r in summary)) else 'FAILURES_RETAINED', 'states': summary, 'source_QA': jr(WORK / 'independent_source_QA.json'), 'independent_algorithm': 'direct Newton Poisson Armijo, einsum Hessian/add.at score/unscaled solve Gram, t.isf/cdf; not primary fit or covariance function', 'base_new_fits': 0, 'successful_same_spec_QA': sum((r['status'] == 'PASS' for r in summary)), 'full_domain_records': len(summary), 'no_false_estimates_for_nonestimable': True})
if __name__ == '__main__':
    phase = sys.argv[1]
    try:
        globals()[phase]()
    except Exception:
        p = WORK / (phase + '_failure_v1.json')
        assert not p.exists()
        jw(p, {'traceback': traceback.format_exc()})
        raise
