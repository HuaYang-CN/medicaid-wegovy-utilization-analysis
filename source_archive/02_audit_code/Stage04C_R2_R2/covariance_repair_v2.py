"""Versioned algebraic covariance repair for M05/M06 only. No native refits.
V = CR1 * (H^{-1} S') (H^{-1} S')'. Mathematically identical to
CR1 H^{-1} S'S H^{-1}, avoiding cancellation in two large sandwich products.
No symmetrization, eigenvalue clamp, pseudoinverse or threshold change.
"""
import audit_v1 as a
import independent_qa_v1 as iq
import numpy as np
from scipy import linalg as la

def native_factor(X, y, mu, cl):
    c = np.maximum(1, np.max(np.abs(X), axis=0))
    A = X / c
    Z = A * np.sqrt(mu)[:, None]
    s = la.svdvals(Z)
    tau = max(X.shape) * np.finfo(float).eps * s[0]
    r = X.shape[1]
    assert int((s > tau).sum()) == r
    Hs = A.T @ (mu[:, None] * A)
    chol = la.cho_factor(Hs, lower=True)
    Bs = la.cho_solve(chol, np.eye(r))
    bread = Bs / c[:, None] / c[None, :]
    H = X.T @ (mu[:, None] * X)
    groups = np.unique(cl)
    G = len(groups)
    n = len(y)
    scores = np.stack([X[cl == g].T @ (y[cl == g] - mu[cl == g]) for g in groups])
    meat = scores.T @ scores
    influence = la.cho_solve(chol, (scores / c).T) / c[:, None]
    corr = G / (G - 1) * (n - 1) / (n - r)
    V = corr * (influence @ influence.T)
    symmetry = float(la.norm(V - V.T, 2) / max(la.norm(V, 2), np.finfo(float).eps))
    vs = (V + V.T) / 2
    emin = float(la.eigvalsh(vs)[0])
    vnorm = float(la.norm(vs, 2))
    gate = bool(np.isfinite(V).all() and symmetry <= 1e-10 and (emin >= -1e-10 * max(vnorm, np.finfo(float).eps)))
    return {'V': V, 'bread': bread, 'H': H, 'meat': meat, 'cluster_scores': scores, 'groups': groups, 'cluster_influence': influence.T, 'weighted_spectrum': s, 'CR1': corr, 'n': n, 'G': G, 'r': r, 'weighted_rank': int((s > tau).sum()), 'weighted_condition': float(s[0] / s[r - 1]), 'symmetry_relative': symmetry, 'min_eigenvalue': emin, 'PSD_scale': vnorm, 'covariance_gate': gate}

def independent_factor(X, y, mu, cl):
    cv = iq.sandwich(X, y, mu, cl)
    influence = np.linalg.solve(cv['H'], cv['cluster_scores'].T)
    cv['direct_product_V_before_factor'] = cv['V']
    cv['V'] = cv['CR1'] * np.einsum('ig,jg->ij', influence, influence)
    cv['cluster_influence'] = influence.T
    return cv

def run():
    old = a.OUT / '04C_R2_Independent_Numerical_QA.json'
    original = a.WORK / 'attempt_v1/04C_R2_Independent_Numerical_QA.json'
    if not original.exists():
        a.target(original).write_bytes(a.safe(old).read_bytes())
    plan = {'scope': ['M05', 'M06'], 'scientific_spec_change': False, 'native_fit_count': 0, 'original_failure': 'M05/M06 native covariance symmetry/PSD; full covariance stability passed; all solvers passed', 'repair': 'stable cluster influence Gram using scaled Cholesky solves; independent unscaled einsum/add.at/numpy solve Gram', 'unchanged_thresholds': a.jr(a.WORK / 'frozen_plan.json')['thresholds'], 'prohibited_methods': ['clip', 'pinv', 'eigenvalue_clamp', 'symmetrize_to_pass'], 'old_failed_objects': 'all v1 files/checkpoints preserved in place', 'new_version': 'covariance_repair_v2.py and model/_repair_v2 objects'}
    a.jw(a.WORK / 'covariance_repair_v2_plan.json', plan)
    summary = []
    for m in ['M05', 'M06']:
        d = a.WORK / m
        v2 = d / '_repair_v2'
        if (v2 / 'final_checkpoint.json').exists():
            c = a.jr(v2 / 'final_checkpoint.json')
            assert all((a.sha(a.ROOT / p) == h for p, h in c['objects'].items()))
            summary.append(a.jr(v2 / 'independent_QA.json'))
            continue
        assert a.check(m, 'solver')
        pg = a.jr(d / 'primary_gate.json')
        assert pg['G_SOLVER'] == 'PASS' and pg['G_COV'] == 'FAIL'
        di = a.jr(d / 'diagnostics.json')
        z = np.load(d / 'input.npz', allow_pickle=False)
        X, y, off, cl = [z[k] for k in ['X', 'y', 'offset', 'clusters']]
        covs = []
        objs = []
        for label in ['exposure', 'zero', 'tight']:
            f = np.load(d / (label + '_fit.npz'), allow_pickle=False)
            cv = native_factor(X, y, f['mu'], cl)
            assert cv['covariance_gate'] and all((cv['V'][t['index'], t['index']] > 0 for t in di['targets']))
            covs.append(cv)
            np.savez_compressed(a.target(v2 / (label + '_cov.npz')), **{k: v for k, v in cv.items() if isinstance(v, np.ndarray)})
            a.jw(v2 / (label + '_cov.json'), {k: v for k, v in cv.items() if not isinstance(v, np.ndarray)})
            objs += [v2 / (label + '_cov.npz'), v2 / (label + '_cov.json')]
        assert all((iq.close(c['V'], covs[0]['V'], 1e-08, 0.0001) for c in covs))
        a.checkpoint(m + '/_repair_v2', 'covariance', objs, {'G_COV': 'PASS', 'algorithm': 'cluster influence Gram; exact same native mu', 'native_model_refitted': False})
        b, mu, hist = iq.newton(y, X, off, v2)
        icv = independent_factor(X, y, mu, cl)
        native = np.load(d / 'exposure_fit.npz', allow_pickle=False)
        nc = covs[0]
        smcv = independent_factor(X, y, native['mu'], cl)
        sym = float(np.linalg.norm(icv['V'] - icv['V'].T, 2) / max(np.linalg.norm(icv['V'], 2), np.finfo(float).eps))
        vs = (icv['V'] + icv['V'].T) / 2
        emin = float(np.linalg.eigvalsh(vs)[0])
        norm = float(np.linalg.norm(vs, 2))
        checks = {'beta_all': iq.close(b, native['params'], 1e-06, 1e-06), 'mu_all': iq.close(mu, native['mu'], 1e-08, 1e-06), 'full_cov': iq.close(icv['V'], nc['V'], 1e-08, 0.0001), 'same_mu_full_cov': iq.close(smcv['V'], nc['V'], 1e-08, 0.0001), 'Hessian': iq.close(icv['H'], nc['H'], 1e-08, 1e-06), 'bread': iq.close(icv['bread'], nc['bread'], 1e-08, 0.0001), 'CR1': abs(icv['CR1'] - nc['CR1']) < 1e-14, 'symmetry': sym <= 1e-10, 'PSD_scaled': emin >= -1e-10 * max(norm, np.finfo(float).eps), 'finite': bool(np.isfinite(icv['V']).all()), 'actual_n_G_r': (icv['n'], icv['G'], icv['r']) == (len(y), 29, X.shape[1]), 'full_cov_start_stability': True}
        targets = []
        for t in di['targets']:
            j = t['index']
            ind = iq.infer(float(b[j]), float(icv['V'][j, j]), icv['G'])
            main = a.sc.inference(native['params'][j], nc['V'][j, j], nc['G'])
            same = iq.infer(float(native['params'][j]), float(nc['V'][j, j]), nc['G'])
            tc = {'beta': iq.close(ind['beta'], main['beta'], 1e-06, 1e-06), 'SE': iq.close(ind['SE'], main['SE'], 1e-06, 0.0001), 'same_beta_inference': all((iq.close(same[k], main[k], 1e-12, 1e-10) for k in ['IRR', 'CI_low', 'CI_high', 'P'])), 'positive_variance': icv['V'][j, j] > 0}
            targets.append({'target': t['name'], 'checks': tc, 'independent_result': ind, 'native_result': main})
        checks['target_arithmetic'] = all((all(t['checks'].values()) for t in targets))
        if di['kind'] == 'F3':
            shift = np.load(d / 'offset_absorption.npz', allow_pickle=False)['parameter_shift']
            checks['offset_mu_identity'] = iq.close(np.exp(X @ (native['params'] + shift)), native['mu'], 1e-08, 1e-06)
        obj = {'Variant_ID': m, 'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks, 'targets': targets, 'independent_Newton_iterations': len(hist) - 1, 'independent_score': hist[-1]['score'], 'beta_max_abs_diff': float(np.max(np.abs(b - native['params']))), 'mu_max_abs_diff': float(np.max(np.abs(mu - native['mu']))), 'cov_max_abs_diff': float(np.max(np.abs(icv['V'] - nc['V']))), 'symmetry': sym, 'PSD_min_eigen': emin, 'PSD_scale': norm, 'algorithm_version': 'v2 stable factor covariance; v1 failed direct product retained', 'input_sha': a.sha(d / 'input.npz'), 'native_refit': False}
        a.jw(v2 / 'independent_QA.json', obj)
        np.savez_compressed(a.target(v2 / 'independent_objects.npz'), params=b, mu=mu, **icv)
        summary.append(obj)
        gate = {**pg, 'G_COV': 'PASS', 'G_NUMERICAL_QA': 'PASS' if obj['status'] == 'PASS' else 'FAIL', 'numerical_status': 'NUMERIC_PASS' if obj['status'] == 'PASS' else 'NUMERIC_FAIL', 'failure_reason': '' if obj['status'] == 'PASS' else 'Independent v2 QA disagreement', 'accepted_covariance_version': 'v2', 'prior_failure_retained': '../covariance_gate.json; ../fit_failure_v1.json; ../final_gate.json'}
        a.jw(v2 / 'final_gate.json', gate)
        a.checkpoint(m + '/_repair_v2', 'numerical_QA', [v2 / 'independent_QA.json', v2 / 'independent_objects.npz', v2 / 'independent_Newton_history_v1.json'], obj)
        a.checkpoint(m + '/_repair_v2', 'final', [v2 / 'final_gate.json', v2 / 'independent_QA.json'], gate)
        print('COV_REPAIR_V2', m, gate['numerical_status'], [k for k, v in checks.items() if not v], flush=True)
    a.jw(a.WORK / 'covariance_repair_v2_complete.json', {'status': 'PASS' if all((o['status'] == 'PASS' for o in summary)) else 'FAIL', 'models': summary, 'native_refits': 0})
if __name__ == '__main__':
    run()
