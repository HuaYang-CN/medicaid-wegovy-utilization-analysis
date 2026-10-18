"""Distinct numerical path: direct Newton, rowwise einsum Hessian,
numpy solve, add.at clustered score, cdf/isf inference. Never calls native
fit/covariance/inference. Independent stdlib raw reconstruction too.
"""
import math, sys, traceback
import audit_v1 as a
import numpy as np
from scipy import stats

def close(v, w, ab, rel):
    return bool(np.all(np.abs(v - w) <= ab + rel * np.abs(w)))

def source_qa():
    mapping = {r['NDC']: (r['Observed_Brands'], set(r['Observed_Product_Names'].split(';'))) for r in a.rc(a.ROOT / '03_audit_outputs/Stage02/02_NDC_Product_Mapping.csv')}
    population = {}
    monthly_keys = set()
    for r in a.rc(a.SRC / 'raw/enrollment/cms_monthly_enrollment_2019_2025.csv'):
        if r['preliminary_or_updated'] != 'U' or r['final_report'] != 'Y' or r['state_abbreviation'] not in a.STATES:
            continue
        s = r['state_abbreviation']
        month = r['reporting_period']
        mk = (s, month)
        assert mk not in monthly_keys
        monthly_keys.add(mk)
        q = month[:4] + 'Q' + str((int(month[4:]) - 1) // 3 + 1)
        try:
            v = float(r['total_medicaid_enrollment'])
        except ValueError:
            v = float('nan')
        valid = math.isfinite(v) and v >= 0 and (r['total_medicaid_enrollment__footnotes'].strip() != 'Unable to Provide Data due to System Limitations')
        population.setdefault((s, q), []).append(v if valid else None)
    by = {}
    channels = set()
    sourceids = []
    source_set = set()
    assignments = []
    for year in [2023, 2024, 2025]:
        rel = f'raw/sdud/sdud_glp1_{year}.csv'
        for i, r in enumerate(a.rc(a.SRC / rel), 1):
            if r['state'] not in a.P1 or r['analytic_brand'] not in ['WEGOVY', 'OZEMPIC'] or int(r['year']) * 4 + int(r['quarter']) < 8094:
                continue
            s = r['state']
            q = r['year'] + 'Q' + r['quarter']
            p = r['analytic_brand']
            u = r['utilization_type']
            ndc = r['ndc']
            assert len(ndc) == 11 and ndc.isdigit() and (u in ['FFSU', 'MCOU']) and (ndc in mapping) and (mapping[ndc][0] == p) and (r['product_name'].strip() in mapping[ndc][1])
            sk = (s, q, ndc, u)
            assert sk not in source_set
            source_set.add(sk)
            sup = r['suppression_used'].lower()
            assert sup in ['true', 'false']
            if sup == 'true':
                assert r['number_of_prescriptions'] == ''
                v = 5.5
            else:
                v = float(r['number_of_prescriptions'])
                assert math.isfinite(v) and v >= 0
            by.setdefault((s, q, p), []).append(v)
            channels.add((s, q, p, u))
            sourceids.append((rel, i, s, q, ndc, u, p))
            assignments.append('|'.join([rel, str(i), s, q, ndc, u, a.f17(v)]))
    assert len(sourceids) == 5988 and a.kh(assignments) == a.jr(a.WORK / 'input_gate.json')['source_assignment_hash']
    pairs = set()
    for s in a.P1:
        for q in a.C10:
            pop = [v for v in population.get((s, q), []) if v is not None]
            if len(pop) >= 2 and sum(pop) / len(pop) > 0 and all(((s, q, p, u) in channels for p in ['WEGOVY', 'OZEMPIC'] for u in ['FFSU', 'MCOU'])):
                pairs.add((s, q))
    base = a.rc(a.WORK / 'BASE_input.csv')
    assert set(((r['state'], r['calendar_quarter']) for r in base)) == pairs and len(base) == 2 * len(pairs) == 348
    for r in base:
        s, q, p = (r['state'], r['calendar_quarter'], r['analytic_brand'])
        pop = [v for v in population[s, q] if v is not None]
        N = sum(pop) / len(pop)
        assert abs(N - float(r['N'])) <= 2 * np.spacing(N)
        assert float(r['y']) == sum(by[s, q, p])
    result = {'status': 'PASS', 'algorithm': 'stdlib csv source partition/mapping/uniqueness, Python sum per source NDC; independent U/Y monthly filtering/arithmetic mean and paired channel grid', 'source_rows': len(sourceids), 'pairs': len(pairs), 'model_rows': len(base), 'assignment_hash': a.kh(assignments), 'source_ledger_not_used_as_primary_input': True}
    a.jw(a.WORK / 'independent_source_QA.json', result)
    return result

def newton(y, X, off, d):
    b = np.zeros(X.shape[1])
    b[0] = math.log(float(y.sum() / np.exp(off).sum()))
    hist = []

    def calc(b):
        z = X @ b
        with np.errstate(over='ignore', invalid='ignore'):
            mu = np.exp(off + z)
        if not np.isfinite(mu).all() or (mu <= 0).any():
            return None
        obj = float(np.sum(mu - y * z))
        g = np.einsum('ij,i->j', X, mu - y)
        H = np.einsum('ij,i,ik->jk', X, mu, X)
        score = float(np.max(np.abs(g) / (1 + np.einsum('ij,i->j', np.abs(X), mu))))
        D = float(2 * np.sum(np.where(y > 0, y * np.log(np.where(y > 0, y, 1) / mu), 0) - (y - mu)))
        return (obj, mu, g, H, score, D)
    for i in range(1000):
        v = calc(b)
        assert v is not None, 'Nonfinite independent Newton iterate'
        obj, mu, g, H, score, D = v
        hist.append({'iteration': i, 'objective': obj, 'deviance': D, 'score': score, 'params': b.copy()})
        a.jw(d / 'independent_Newton_history_v1.json', hist)
        changes = [abs(v['deviance'] - u['deviance']) / (1 + abs(u['deviance'])) for u, v in zip(hist[:-1], hist[1:])]
        if score <= 1e-10 and len(changes) >= 5 and (max(changes[-5:]) <= 1e-10):
            return (b, mu, hist)
        direction = np.linalg.solve(H, -g)
        slope = float(g @ direction)
        assert slope <= 0
        step = 1.0
        accepted = False
        for ls in range(60):
            bv = b + step * direction
            vv = calc(bv)
            z = step * (X @ direction)
            with np.errstate(over='ignore', invalid='ignore'):
                delta = float(np.sum(mu * np.expm1(z) - y * z))
            if vv is not None and math.isfinite(delta) and (delta <= 0.0001 * step * slope):
                accepted = True
                break
            step *= 0.5
        assert accepted, 'Independent Armijo60 trial failure'
        hist[-1]['step'] = step
        hist[-1]['line_search_trials'] = ls + 1
        b = bv
    raise RuntimeError('Independent Newton1000 iteration limit')

def sandwich(X, y, mu, cl):
    n, k = X.shape
    H = np.einsum('ij,i,ik->jk', X, mu, X)
    bread = np.linalg.solve(H, np.eye(k))
    gs, inv = np.unique(cl, return_inverse=True)
    scores = np.zeros((len(gs), k))
    np.add.at(scores, inv, X * (y - mu)[:, None])
    meat = np.einsum('gi,gj->ij', scores, scores)
    scale = np.maximum(1, np.max(np.abs(X), axis=0))
    s = np.linalg.svd(X / scale, compute_uv=False)
    tau = max(X.shape) * np.finfo(float).eps * s[0]
    r = int((s > tau).sum())
    sw = np.linalg.svd(X / scale * np.sqrt(mu)[:, None], compute_uv=False)
    tw = max(X.shape) * np.finfo(float).eps * sw[0]
    assert r == k and int((sw > tw).sum()) == r
    G = len(gs)
    corr = G / (G - 1) * (n - 1) / (n - r)
    V = corr * (bread @ meat @ bread)
    return {'H': H, 'bread': bread, 'meat': meat, 'cluster_scores': scores, 'groups': gs, 'V': V, 'CR1': corr, 'n': n, 'r': r, 'G': G, 'score': np.einsum('ij,i->j', X, y - mu), 'weighted_rank': int((sw > tw).sum())}

def infer(b, var, G):
    assert math.isfinite(var) and var > 0
    se = math.sqrt(var)
    crit = float(stats.t.isf(0.025, G - 1))
    p = float(2 * stats.t.cdf(-abs(b / se), G - 1))
    return {'beta': float(b), 'SE': se, 'IRR': math.exp(b), 'CI_low': math.exp(b - crit * se), 'CI_high': math.exp(b + crit * se), 'P': p, 'df': G - 1}

def run():
    source = source_qa()
    summary = []
    for m in a.MODELS:
        d = a.WORK / m
        if a.check(m, 'final'):
            summary.append(a.jr(d / 'independent_QA.json'))
            print('REUSE QA', m, flush=True)
            continue
        gate = a.jr(d / 'primary_gate.json')
        if gate['numerical_status'] != 'PENDING_INDEPENDENT_QA':
            obj = {'Variant_ID': m, 'status': 'NOT_EXECUTED_PRIMARY_FAILURE', 'reason': gate['failure_reason']}
            a.jw(d / 'independent_QA.json', obj)
            summary.append(obj)
            a.jw(d / 'final_gate.json', gate)
            a.checkpoint(m, 'final', [d / 'final_gate.json', d / 'independent_QA.json'], gate)
            continue
        checks = {}
        try:
            assert a.check(m, 'covariance')
            di = a.jr(d / 'diagnostics.json')
            ob = np.load(a.safe(d / 'input.npz'), allow_pickle=False)
            X, y, off, cl = [ob[k] for k in ['X', 'y', 'offset', 'clusters']]
            assert a.xhash(X) == di['X_hash']
            native = np.load(d / 'exposure_fit.npz', allow_pickle=False)
            nv = np.load(d / 'exposure_cov.npz', allow_pickle=False)
            cvmeta = a.jr(d / 'exposure_cov.json')
            b, mu, hist = newton(y, X, off, d)
            cv = sandwich(X, y, mu, cl)
            np.savez_compressed(a.target(d / 'independent_objects.npz'), params=b, mu=mu, **cv)
            qr, rr = np.linalg.qr(X, mode='reduced')
            recover = np.linalg.solve(rr, qr.T @ (np.log(native['mu']) - off))
            same_mu = sandwich(X, y, native['mu'], cl)
            checks = {'beta_all': close(b, native['params'], 1e-06, 1e-06), 'mu_all': close(mu, native['mu'], 1e-08, 1e-06), 'covariance_full': close(cv['V'], nv['V'], 1e-08, 0.0001), 'Hessian': close(cv['H'], nv['H'], 1e-08, 1e-06), 'same_mu_covariance': close(same_mu['V'], nv['V'], 1e-08, 0.0001), 'raw_score_identity': close(same_mu['score'], native['raw_score'], 1e-07, 1e-06), 'native_beta_QR_identity': close(recover, native['params'], 1e-08, 1e-06), 'CR1': abs(cv['CR1'] - cvmeta['CR1']) < 1e-14, 'actual_n_G_r': (cv['n'], cv['G'], cv['r']) == (di['effective']['n'], di['effective']['G'], di['normalized_rank']['rank'])}
            symmetry = float(np.linalg.norm(cv['V'] - cv['V'].T, 2) / max(np.linalg.norm(cv['V'], 2), np.finfo(float).eps))
            vs = (cv['V'] + cv['V'].T) / 2
            emin = float(np.linalg.eigvalsh(vs)[0])
            vnorm = float(np.linalg.norm(vs, 2))
            checks.update({'finite': bool(np.isfinite(cv['V']).all()), 'symmetry': symmetry <= 1e-10, 'PSD_scaled': emin >= -1e-10 * max(vnorm, np.finfo(float).eps)})
            targetqa = []
            for t in di['targets']:
                j = t['index']
                ind = infer(b[j], cv['V'][j, j], cv['G'])
                primary = a.sc.inference(native['params'][j], nv['V'][j, j], cv['G'])
                same = infer(float(native['params'][j]), float(nv['V'][j, j]), cv['G'])
                tc = {'beta': close(ind['beta'], primary['beta'], 1e-06, 1e-06), 'SE': close(ind['SE'], primary['SE'], 1e-06, 0.0001), 'same_beta_inference': all((close(same[k], primary[k], 1e-12, 1e-10) for k in ['IRR', 'CI_low', 'CI_high', 'P'])), 'variance_positive': cv['V'][j, j] > 0}
                targetqa.append({'target': t['name'], 'checks': tc, 'independent_result': ind, 'native_result': primary})
            checks['targets'] = all((all(t['checks'].values()) for t in targetqa))
            if di['kind'] in ['F1', 'F3']:
                shift = np.load(d / 'offset_absorption.npz', allow_pickle=False)['parameter_shift']
                trans = np.exp(X @ (native['params'] + shift))
                checks['offset_absorption_mu_identity'] = close(trans, native['mu'], 1e-08, 1e-06)
            obj = {'Variant_ID': m, 'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks, 'targets': targetqa, 'independent_Newton_iterations': len(hist) - 1, 'independent_score': hist[-1]['score'], 'beta_max_abs_diff': float(np.max(np.abs(b - native['params']))), 'mu_max_abs_diff': float(np.max(np.abs(mu - native['mu']))), 'cov_max_abs_diff': float(np.max(np.abs(cv['V'] - nv['V']))), 'symmetry': symmetry, 'PSD_min_eigen': emin, 'PSD_scale': vnorm, 'input_sha': a.sha(d / 'input.npz')}
            a.jw(d / 'independent_QA.json', obj)
            assert obj['status'] == 'PASS', 'Independent QA disagreement ' + str([k for k, v in checks.items() if not v])
            gate['G_NUMERICAL_QA'] = 'PASS'
            gate['numerical_status'] = 'NUMERIC_PASS'
            a.checkpoint(m, 'numerical_QA', [d / 'independent_QA.json', d / 'independent_objects.npz', d / 'independent_Newton_history_v1.json'], obj)
        except Exception as e:
            gate['G_NUMERICAL_QA'] = 'FAIL'
            gate['numerical_status'] = 'NUMERIC_FAIL'
            gate['failure_reason'] = type(e).__name__ + ': ' + str(e)
            obj = {'Variant_ID': m, 'status': 'FAIL', 'checks': checks, 'failure_reason': gate['failure_reason'], 'traceback': traceback.format_exc()}
            a.jw(d / 'independent_QA_failure_v1.json', obj)
        summary.append(obj)
        a.jw(d / 'final_gate.json', gate)
        a.checkpoint(m, 'final', [d / 'final_gate.json', d / ('independent_QA.json' if (d / 'independent_QA.json').exists() else 'independent_QA_failure_v1.json')], gate)
        print('INDEPENDENT QA', m, gate['numerical_status'], gate['failure_reason'], flush=True)
    a.jw(a.OUT / '04C_R2_Independent_Numerical_QA.json', {'status': 'PASS' if all((o['status'] == 'PASS' for o in summary)) else 'FAILURES_RETAINED', 'models': summary, 'source_QA': source, 'independent_algorithm': 'Newton + einsum unscaled Hessian/numpy solve + add.at cluster scores + t cdf/isf; not native GLM/core covariance', 'code_sha': a.sha(a.CODE / 'independent_qa_v1.py')})
if __name__ == '__main__':
    run()
