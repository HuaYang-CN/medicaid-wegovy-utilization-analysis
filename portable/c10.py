"""R2 portable adapter of the actual C10 functions; explicit execution only.
Mathematics and gates unchanged. Input comes from published frozen NDC subset.
Local IO replaces audit infrastructure; old raw CMS re-download is not required.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
from io import BytesIO
import csv,json,hashlib,math,traceback
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from scipy import optimize
import stat_core as sc
import independent_core as ic
ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'output';WORK=AUDIT/'c10'
def now():return datetime.now(timezone.utc).isoformat()
def digest(b):return hashlib.sha256(b).hexdigest()
def read(p):return Path(p).read_bytes()
def savejson(p,o):Path(p).write_text(json.dumps(o,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def writecsv(p,rs,fields=None):
    with Path(p).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rs[0]));w.writeheader();w.writerows(rs)
def obj(x):
    if isinstance(x, dict):
        return {k: obj(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [obj(v) for v in x]
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.generic):
        return x.item()
    return x

def jw(p, x):
    savejson(p, obj(x))

def pdread(p):
    return pd.read_csv(BytesIO(read(p)), float_precision='round_trip')

def framewrite(p, f):
    f.to_csv(p, index=False, float_format='%.17g', lineterminator='\n')

def keys(f):
    return (f.state + '|' + f.calendar_quarter + '|' + f.analytic_brand).tolist()

def kh(ks):
    return digest(''.join((x + '\n' for x in ks)).encode())

def design(f):
    sp = (f.state + ':' + f.analytic_brand).to_numpy()
    lev = sorted(set(sp))
    qs = sorted(set(f.calendar_quarter))
    ref = qs[0]
    cols = [np.ones(len(f))]
    names = ['Intercept']
    for v in lev[1:]:
        cols.append((sp == v).astype(float))
        names.append('SP:' + v)
    for q in qs[1:]:
        cols.append((f.calendar_quarter == q).to_numpy(float))
        names.append('Q:' + q)
    for tag, mult in [('W', f.obesity), ('NC', f.noncoverage_2024), ('DDD', f.obesity * f.noncoverage_2024)]:
        cols.append(f.post.to_numpy(float) * mult.to_numpy(float))
        names.append('Post×' + tag)
    return (np.column_stack(cols), names)

def xhash(X):
    return digest((str(X.shape) + '|' + str(X.dtype) + '|' + ','.join((format(float(x), '.17g') for x in X.ravel()))).encode())

def analysis_log(s):
    with (AUDIT / 'R2_C10_Execution.log').open('a', encoding='utf-8') as f:
        f.write(now() + ' ' + s + '\n')
    print(s, flush=True)

def independent_separation(X, y):
    A = X / np.maximum(1, np.max(np.abs(X), axis=0))
    p = y > 0
    z = y == 0
    if not z.any():
        return {'status': 'NO_ZERO_OUTCOMES_EXACT', 'detected': False}
    r = optimize.linprog(A[z].sum(axis=0), A_ub=A[z], b_ub=np.zeros(z.sum()), A_eq=A[p], b_eq=np.zeros(p.sum()), bounds=[(-1, 1)] * A.shape[1], method='highs-ds', options={'primal_feasibility_tolerance': 1e-09, 'dual_feasibility_tolerance': 1e-09})
    assert r.success
    m = A @ r.x
    return {'status': 'BOUNDED_CONE_LP', 'detected': bool(r.fun < -1e-08), 'objective': float(r.fun), 'direction': r.x, 'margins': m, 'positive_residual': float(np.max(np.abs(m[p]))), 'zero_max': float(np.max(m[z]))}

def scenario(ident):
    d = WORK / ident
    d.mkdir(exist_ok=True)
    cp = d / 'result.json'
    if cp.exists():
        analysis_log('REUSE completed ' + ident)
        return json.loads(cp.read_text())
    requested = pdread(WORK / (ident + '_requested.csv'))
    f = requested.copy()
    removed = []
    rounds = []
    ind_sep = []
    for i in range(10):
        X, names = design(f)
        y = f.y.to_numpy()
        s = sc.separation(X, y)
        ind = independent_separation(X, y)
        assert bool(s['detected']) == bool(ind['detected'])
        rk = sc.rank_info(X)
        rr = {'iteration': i, 'n': len(f), 'rank': rk, 'names': names, 'certificate': s, 'keys': keys(f)}
        jw(d / f'separation_round_{i}.json', rr)
        jw(d / f'independent_separation_round_{i}.json', ind)
        rounds.append(rr)
        ind_sep.append(ind)
        if not s['detected']:
            break
        drop = [keys(f)[j] for j in np.flatnonzero(s['affected'])]
        removed += drop
        f = f.loc[~s['affected']].copy()
    else:
        raise RuntimeError('Separation rounds10 not stable')
    X, names = design(f)
    j = names.index('Post×DDD')
    rank = sc.rank_info(X)
    target = sc.target_estimable(X, j)
    framewrite(d / 'effective.csv', f)
    np.savez_compressed(d / 'design.npz', X=X, y=f.y.to_numpy(), offset=f.offset.to_numpy(), clusters=f.state.to_numpy(dtype=str), names=np.array(names), keys=np.array(keys(f)))
    writecsv(d / 'excluded_rows.csv', [{'row_key': k, 'reason': 'FORMAL_LP_SEPARATION_CERTIFICATE'} for k in removed], fields=['row_key', 'reason'])
    gate = {'scenario': ident, 'requested_n': len(requested), 'effective_n': len(f), 'G': f.state.nunique(), 'coverage_G': f.loc[f.coverage_2024 == 1, 'state'].nunique(), 'noncoverage_G': f.loc[f.coverage_2024 == 0, 'state'].nunique(), 'rank': rank['rank'], 'columns': rank['k'], 'rank_tau_0_1': rank['rank_tau_0_1'], 'rank_tau_10': rank['rank_tau_10'], 'rank_without_DDD': sc.rank_info(np.delete(X, j, axis=1))['rank'], 'target_identifiable': target, 'separated_rows': len(removed), 'separation_status': 'CERTIFIED_ROWS_REMOVED' if removed else rounds[0]['certificate']['status'], 'requested_finite_MLE': 'NO_SEPARATED' if removed else 'YES_IF_SOLVER_GATES_PASS', 'effective_target_finite_MLE': 'NOT_VERIFIABLE_UNIDENTIFIED' if not target else 'PENDING_SOLVER', 'effective_input_sha256': digest((d / 'effective.csv').read_bytes()), 'effective_keys_sha256': kh(keys(f)), 'X_sha256': xhash(X), 'solver_executed': False, 'solver_gate': 'NOT_EXECUTED', 'covariance_gate': 'NOT_EXECUTED', 'independent_QA': 'PENDING', 'implemented_at': now()}
    base = {'scenario': ident, 'assignment': 0 if ident.endswith('_0') else 10, 'beta': 'NA', 'SE': 'NA', 'IRR': 'NA', 'CI_low': 'NA', 'CI_high': 'NA', 'P': 'NA', **{k: gate[k] for k in ['requested_n', 'effective_n', 'G', 'rank', 'columns']}, 'df': gate['G'] - 1, 'CR1': 'NA', 'status': 'NOT_IDENTIFIABLE' if not target else 'PENDING', 'reason': 'DDD absorbed after formal separated-row removal' if not target else '', 'implemented_at': now()}
    if not target or rank['rank'] != rank['k']:
        other = np.delete(X, j, axis=1)
        b, res, rr, sv = np.linalg.lstsq(other, X[:, j], rcond=max(other.shape) * np.finfo(float).eps)
        resid = X[:, j] - other @ b
        assert np.max(np.abs(resid)) < 1e-10 and (not target)
        jw(d / 'independent_identification_QA.json', {'target_projection_residual_max': np.max(np.abs(resid)), 'rank_by_numpy': int(np.linalg.matrix_rank(X)), 'rank_without_target': int(np.linalg.matrix_rank(other)), 'native_target_false': not target, 'all_lower_order_terms_retained': True, 'GLM_skipped_because_nonidentified': True})
        gate['independent_QA'] = 'PASS_FORMAL_NONIDENTIFIABILITY'
        jw(d / 'gates.json', gate)
        jw(cp, base)
        analysis_log(ident + ' NOT_IDENTIFIABLE; no GLM fit; ' + str(len(removed)) + ' certified rows removed')
        return base
    assert rank['rank'] == rank['rank_tau_0_1'] == rank['rank_tau_10']
    y = f.y.to_numpy()
    off = f.offset.to_numpy()
    cl = f.state.to_numpy()
    runs = []
    objects = []
    try:
        for num, (startname, tol) in enumerate([('exposure', 1e-10), ('zeros', 1e-10), ('exposure', 1e-12)], 1):
            prefix = d / f'native_{num}'
            jp = Path(str(prefix) + '.json')
            npz = Path(str(prefix) + '.npz')
            if jp.exists():
                r = json.loads(jp.read_text())
                o = {k:v for k,v in [(k,np.load(npz,allow_pickle=False)[k]) for k in np.load(npz,allow_pickle=False).files if k!='groups']}
                runs.append(r)
                objects.append(o)
                continue
            started = Path(str(prefix) + '.STARTED')
            started.open('x').write(now())
            start = np.zeros(X.shape[1])
            if startname == 'exposure':
                start[0] = np.log((y.sum() + 0.1) / np.exp(off).sum())
            fit = sc.glm_fit(y, X, off, start, tol)
            jw(Path(str(prefix) + '_solver.json'), fit)
            assert fit['solver_gate'], 'Original native solver gate failed'
            cov = sc.covariance(X, y, fit['mu'], cl)
            jw(Path(str(prefix) + '_cov_gate.json'), {k: v for k, v in cov.items() if not isinstance(v, np.ndarray)})
            assert cov['covariance_gate'], 'Original covariance gate failed'
            est = sc.inference(fit['params'][j], cov['V'][j, j], cov['G'])
            o = {'params': fit['params'], 'mu': fit['mu'], 'raw_score': fit['raw_score'], **{k: v for k, v in cov.items() if isinstance(v, np.ndarray)}}
            np.savez_compressed(npz, **o)
            r = {'run': num, 'start': startname, 'tol': tol, 'estimate': est, 'iterations': fit['iterations'], 'normalized_score': fit['normalized_score'], 'last_five_deviance': fit['last_five_deviance_relative_max'], 'solver_gate': fit['solver_gate'], 'covariance_gate': cov['covariance_gate'], 'CR1': cov['CR1'], 'weighted_rank': cov['weighted_rank'], 'warnings': fit['warnings']}
            jw(jp, r)
            runs.append(r)
            objects.append(o)
            analysis_log(ident + ' native QC ' + str(num) + ' completed')
        native = objects[0]
        stability = {str(i): {'params': ic.close(o['params'], native['params'], 1e-06, 1e-06), 'mu': ic.close(o['mu'], native['mu'], 1e-08, 1e-06), 'cov': ic.close(o['V'], native['V'], 1e-08, 0.0001)} for i, o in enumerate(objects[1:], 2)}
        assert all((all(x.values()) for x in stability.values()))
        iq = d / 'independent_QA.json'
        if iq.exists():
            ind = json.loads(iq.read_text())
            assert ind['status'] == 'PASS'
        else:
            (d / 'independent.STARTED').open('x').write(now())
            b, mu, hist = ic.newton(y, X, off, d)
            cv = ic.sandwich(X, y, mu, cl)
            est = ic.infer(b[j], cv['V'][j, j], cv['G'])
            np.savez_compressed(d / 'independent_objects.npz', params=b, mu=mu, **cv)
            checks = {'all_beta': ic.close(b, native['params'], 1e-06, 1e-06), 'all_mu': ic.close(mu, native['mu'], 1e-08, 1e-06), 'full_covariance': ic.close(cv['V'], native['V'], 1e-08, 0.0001), 'SE': ic.close(est['SE'], runs[0]['estimate']['SE'], 1e-06, 0.0001), 'full_H': ic.close(cv['H'], native['H'], 1e-08, 1e-06), 'CR1': abs(cv['CR1'] - runs[0]['CR1']) < 1e-14, 'n_G_r': (cv['n'], cv['G'], cv['r']) == (len(f), f.state.nunique(), rank['rank'])}
            symmetry = np.linalg.norm(cv['V'] - cv['V'].T, 2) / max(np.linalg.norm(cv['V'], 2), np.finfo(float).eps)
            Vs = (cv['V'] + cv['V'].T) / 2
            ev = np.linalg.eigvalsh(Vs)
            checks.update(finite=bool(np.isfinite(cv['V']).all()), symmetry=bool(symmetry <= 1e-10), PSD=bool(ev[0] >= -1e-10 * max(np.linalg.norm(Vs, 2), np.finfo(float).eps)), target_variance_positive=bool(cv['V'][j, j] > 0))
            ind = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'algorithm': 'distinct Newton/einsum/numpy solve/add.at/t-cdf-isf', 'checks': checks, 'estimate': est, 'iterations': len(hist) - 1, 'score': hist[-1]['score'], 'native_stability': stability, 'max_beta_difference': np.max(np.abs(b - native['params'])), 'max_mu_difference': np.max(np.abs(mu - native['mu'])), 'max_cov_difference': np.max(np.abs(cv['V'] - native['V'])), 'symmetry': symmetry, 'min_eigenvalue': ev[0]}
            jw(iq, ind)
            assert ind['status'] == 'PASS', 'Independent QA failed'
        gate.update(solver_executed=True, solver_gate='PASS', covariance_gate='PASS', independent_QA='PASS', effective_target_finite_MLE='YES', iterations=runs[0]['iterations'], score=runs[0]['normalized_score'], CR1=runs[0]['CR1'])
        base.update({k: runs[0]['estimate'][k] for k in ['beta', 'SE', 'IRR', 'CI_low', 'CI_high', 'P']}, CR1=runs[0]['CR1'], status='VALID_CONDITIONAL_SCENARIO', reason='POST_HOC_OPERATIONAL_SUPPRESSION_ASSIGNMENT; NOT_STRICT_BOUND_OR_CAUSAL_EFFECT')
    except Exception as e:
        jw(d / 'failure.json', {'time': now(), 'error': str(e), 'traceback': traceback.format_exc()})
        gate['solver_executed'] = True
        gate['independent_QA'] = 'FAILED_OR_INCOMPLETE'
        base['status'] = 'FAILED_NUMERICAL_QA'
        base['reason'] = type(e).__name__ + ': ' + str(e)
        analysis_log(ident + ' failure retained: ' + base['reason'])
    jw(d / 'gates.json', gate)
    jw(cp, base)
    return base
