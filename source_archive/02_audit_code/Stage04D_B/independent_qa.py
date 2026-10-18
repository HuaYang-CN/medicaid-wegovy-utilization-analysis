"""Independent numerical validation of the SAME eight frozen model inputs.
Does not call stat_core fit/covariance/inference. Direct Newton likelihood,
rowwise Hessian, add.at cluster aggregation, numpy solve, independent tails.
No selection of models, supports, tolerances or substantive hypotheses.
"""
import sys, math, traceback, json
import audit as a

def newton(y, X, off, tag):
    np = a.np
    b = np.zeros(X.shape[1])
    b[0] = math.log(float(y.sum() / np.exp(off).sum()))
    history = []

    def calc(b):
        eta = off + X @ b
        with np.errstate(over='ignore', invalid='ignore'):
            mu = np.exp(eta)
        if not np.isfinite(mu).all() or (mu <= 0).any():
            return None
        obj = float(np.sum(mu - y * (X @ b)))
        g = np.einsum('ij,i->j', X, mu - y)
        H = np.einsum('ij,i,ik->jk', X, mu, X)
        score = float(np.max(np.abs(g) / (1 + np.einsum('ij,i->j', np.abs(X), mu))))
        D = float(2 * np.sum(y * np.log(y / mu) - (y - mu))) if (y > 0).all() else float(2 * np.sum(np.where(y > 0, y * np.log(np.where(y > 0, y, 1) / mu), 0) - (y - mu)))
        return (obj, mu, g, H, score, D)
    for i in range(1000):
        v = calc(b)
        assert v is not None, 'Nonfinite Newton iterate'
        obj, mu, g, H, score, D = v
        history.append({'iteration': i, 'objective': obj, 'deviance': D, 'score': score, 'params': b.copy()})
        a.jw(a.WORK / (tag + '_independent_Newton_history.json'), history)
        if score <= 1e-10:
            return (b, mu, history)
        direction = np.linalg.solve(H, -g)
        slope = float(g @ direction)
        assert slope < 0
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
        assert accepted, 'Newton Armijo failed within locked60 trials'
        history[-1]['step'] = step
        history[-1]['line_search_trials'] = ls + 1
        b = bv
    raise RuntimeError('Independent Newton1000 iteration limit')

def sandwich(X, y, mu, cl):
    np = a.np
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
    return {'H': H, 'bread': bread, 'meat': meat, 'scores': scores, 'groups': gs, 'V': V, 'CR1': corr, 'n': n, 'r': r, 'G': G, 'score': np.einsum('ij,i->j', X, y - mu), 'weighted_rank': int((sw > tw).sum())}

def infer(b, var, G, normal=False):
    assert math.isfinite(var) and var > 0
    se = math.sqrt(var)
    stat = b / se
    crit = 1.96 if normal else float(a.stats.t.isf(0.025, G - 1))
    p = float(2 * a.stats.norm.cdf(-abs(stat))) if normal else float(2 * a.stats.t.cdf(-abs(stat), G - 1))
    return {'beta': float(b), 'SE': se, 'IRR': math.exp(b), 'CI_low': math.exp(b - crit * se), 'CI_high': math.exp(b + crit * se), 'P': p, 'df': None if normal else G - 1}

def close(v, w, ab, rel):
    return bool(a.np.all(a.np.abs(v - w) <= ab + rel * a.np.abs(w)))

def run():
    a.imports()
    np = a.np
    assert a.jr(a.WORK / 'fits_complete.json')['status'] == 'COMPLETE_VERIFIED'
    retry = len(sys.argv) == 2 and sys.argv[1] == 'retry_failed'
    assert len(sys.argv) == 1 or retry
    plan = {'solver': 'direct Poisson Newton from fixed exposure intercept, Armijo1e-4 max60, stop normalized score1e-10, max1000; no native params used for initialization', 'Armijo_arithmetic': 'exact objective delta sum(mu*expm1(step*X*d)-y*step*X*d) avoids subtraction cancellation; no threshold/model/starting value changed', 'covariance': 'numpy einsum Hessian, add.at cluster scores, numpy.linalg.solve unscaled positive full rank H', 'beta': 'independently optimized same input model; also QR inverse log(mu)-offset coefficient identity', 'main_inference': 'scipy.t.isf and cdf, df actual G-1', 'normal': 'critical1.96 fixed legacy reference; normal cdf', 'comparison_tolerances': a.jr(a.WORK / 'frozen_plan.json')['stability'], 'input': 'same requested/effective hashes, X, y, population offset, clusters; no new model specification', 'no_interpretation_selection': True, 'retry_only_failed': retry}
    a.jw(a.WORK / ('independent_QA_retry_plan.json' if retry else 'independent_QA_plan.json'), plan)
    rows = a.rc(a.OUT / '04D_B_Model_Results.csv')
    gates = a.rc(a.OUT / '04D_B_Model_Gates.csv')
    summary = []
    original = a.jr(a.WORK / 'independent_QA_first_attempt/04D_B_Independent_Numerical_QA.json') if retry else None
    for name in a.MODELS:
        g = next((g for g in gates if g['Variant_ID'] == name))
        records = [r for r in rows if r['Variant_ID'] == name]
        d = a.jr(a.WORK / (name + '_diagnostics.json'))
        checks = {}
        failure = ''
        if retry and g['numerical_status'] == 'PASS':
            previous = next((r for r in original['models_checked'] if r['Variant_ID'] == name))
            assert previous['status'] == 'PASS'
            summary.append(previous)
            continue
        if retry and g['G_NUMERICAL_QA'] == 'FAIL':
            assert 'Independent Newton1000 iteration limit' in g['failure_reason'], 'Retry authorized only for identified validator implementation failure'
            native0 = np.load(a.safe(a.WORK / (name + '_run1_fit.npz')), allow_pickle=False)
            cov0 = np.load(a.safe(a.WORK / (name + '_run1_cov.npz')), allow_pickle=False)
            for t in d['targets']:
                rec = next((r for r in records if r['target'] == t['name']))
                j = t['index']
                main = a.sc.inference(native0['params'][j], cov0['V'][j, j], int(cov0['G']))
                normal = a.sc.inference(native0['params'][j], cov0['V'][j, j], int(cov0['G']), 'normal')
                rec.update(main)
                rec.update({'normal_' + k: normal[k] for k in ['IRR', 'CI_low', 'CI_high', 'P']})
                rec['failure_reason'] = ''
                rec['status'] = 'PENDING_INDEPENDENT_QA'
            g['numerical_status'] = 'PENDING_INDEPENDENT_QA'
        if g['numerical_status'] != 'PENDING_INDEPENDENT_QA':
            assert all((all((r.get(k, '') == '' for k in ['beta', 'SE', 'IRR', 'CI_low', 'CI_high', 'P', 'normal_P'])) for r in records))
            summary.append({'Variant_ID': name, 'status': 'NOT_EXECUTED_PRIMARY_NUMERICAL_FAILURE', 'reason': g['failure_reason']})
            continue
        try:
            ob = np.load(a.safe(a.WORK / (name + '_input.npz')), allow_pickle=False)
            assert a.sha(a.WORK / (name + '_input.npz')) == d['object_SHA256']
            X = ob['X']
            y = ob['y']
            off = ob['offset']
            cl = ob['clusters']
            assert a.xhash(X) == d['X_hash'] and a.kh(ob['keys'].tolist()) == d['effective']['order_hash']
            ef = a.readframe(name + '_effective')
            assert a.info(ef) == d['effective']
            b, mu, hist = newton(y, X, off, name)
            cov = sandwich(X, y, mu, cl)
            a.jw(a.WORK / (name + '_independent_Newton_history.json'), hist)
            np.savez_compressed(a.target(a.WORK / (name + '_independent_QA_objects.npz')), params=b, mu=mu, **cov)
            native = np.load(a.safe(a.WORK / (name + '_run1_fit.npz')), allow_pickle=False)
            nv = np.load(a.safe(a.WORK / (name + '_run1_cov.npz')), allow_pickle=False)
            qr, r = np.linalg.qr(X, mode='reduced')
            recovered = np.linalg.solve(r, qr.T @ (np.log(native['mu']) - off))
            checks = {'independent_beta_all': close(b, native['params'], 1e-06, 1e-06), 'native_beta_QR_identity': close(recovered, native['params'], 1e-08, 1e-06), 'independent_mu_all': close(mu, native['mu'], 1e-08, 1e-06), 'independent_Hessian': close(cov['H'], nv['H'], 1e-08, 1e-06), 'independent_full_covariance': close(cov['V'], nv['V'], 1e-08, 0.0001), 'independent_CR1': abs(cov['CR1'] - float(nv['CR1'])) <= 1e-14, 'independent_n_G_r': (cov['n'], cov['G'], cov['r']) == (d['effective']['n'], d['effective']['G'], d['rank']['rank']), 'native_score_identity': close(sandwich(X, y, native['mu'], cl)['score'], native['raw_score'], 1e-07, 1e-06), 'native_H_cov_same_mu': close(sandwich(X, y, native['mu'], cl)['V'], nv['V'], 1e-08, 0.0001)}
            targetqa = []
            for t in d['targets']:
                j = t['index']
                rec = next((r for r in records if r['target'] == t['name']))
                main = infer(b[j], cov['V'][j, j], cov['G'])
                normal = infer(b[j], cov['V'][j, j], cov['G'], True)
                nt = infer(float(native['params'][j]), float(nv['V'][j, j]), cov['G'])
                nn = infer(float(native['params'][j]), float(nv['V'][j, j]), cov['G'], True)
                tc = {'beta': close(b[j], native['params'][j], 1e-06, 1e-06), 'SE': close(main['SE'], float(rec['SE']), 1e-06, 0.0001), 'native_t_arithmetic': all((close(nt[k], float(rec[k]), 1e-12, 1e-10) for k in ['beta', 'SE', 'IRR', 'CI_low', 'CI_high', 'P'])), 'native_normal_arithmetic': all((close(nn[k], float(rec['normal_' + k]), 1e-12, 1e-10) for k in ['IRR', 'CI_low', 'CI_high', 'P'])), 'independent_t_IRR_CI_P': all((close(main[k], float(rec[k]), 1e-06, 0.0001) for k in ['IRR', 'CI_low', 'CI_high', 'P'])), 'independent_normal_IRR_CI_P': all((close(normal[k], float(rec['normal_' + k]), 1e-06, 0.0001) for k in ['IRR', 'CI_low', 'CI_high', 'P'])), 'df': int(rec['df']) == cov['G'] - 1}
                targetqa.append({'target': t['name'], 'checks': tc, 'independent_t': main, 'independent_normal': normal, 'beta_difference': float(b[j] - native['params'][j])})
            symmetry = float(np.linalg.norm(cov['V'] - cov['V'].T, 2) / max(np.linalg.norm(cov['V'], 2), np.finfo(float).eps))
            vs = (cov['V'] + cov['V'].T) / 2
            emin = float(np.linalg.eigvalsh(vs)[0])
            pscale = float(np.linalg.norm(vs, 2))
            checks.update({'finite': bool(np.isfinite(cov['V']).all()), 'symmetry': symmetry <= 1e-10, 'scaled_PSD': emin >= -1e-10 * max(pscale, np.finfo(float).eps), 'strict_target_variance': all((cov['V'][t['index'], t['index']] > 0 for t in d['targets'])), 'all_target_arithmetic': all((all(t['checks'].values()) for t in targetqa))})
            if len(d['targets']) == 2:
                j, k = [t['index'] for t in d['targets']]
                checks['Early_Late_covariance'] = all((close(float(rec['Early_Late_covariance']), cov['V'][j, k], 1e-08, 0.0001) for rec in records))
            obj = {'Variant_ID': name, 'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks, 'target_QA': targetqa, 'independent_Newton_iterations': len(hist) - 1, 'independent_normalized_score': hist[-1]['score'], 'beta_max_abs_diff': float(np.max(np.abs(b - native['params']))), 'full_cov_max_abs_diff': float(np.max(np.abs(cov['V'] - nv['V']))), 'mu_max_abs_diff': float(np.max(np.abs(mu - native['mu']))), 'symmetry': symmetry, 'minimum_eigenvalue': emin, 'PSD_scale': pscale, 'input_sha': d['object_SHA256'], 'input_X_hash': d['X_hash'], 'actual_n_G_r': [cov['n'], cov['G'], cov['r']]}
            a.jw(a.WORK / (name + '_independent_QA.json'), obj)
            assert obj['status'] == 'PASS', 'Independent implementation disagrees ' + str([k for k, v in checks.items() if not v])
            summary.append(obj)
            g['G_NUMERICAL_QA'] = 'PASS'
            g['numerical_status'] = 'PASS'
            g['failure_reason'] = ''
            for rec in records:
                rec['status'] = 'PASS'
        except Exception as e:
            failure = type(e).__name__ + ': ' + str(e)
            summary.append({'Variant_ID': name, 'status': 'FAIL', 'checks': checks, 'failure_reason': failure, 'traceback': traceback.format_exc()})
            g['G_NUMERICAL_QA'] = 'FAIL'
            g['numerical_status'] = 'FAIL'
            g['failure_reason'] = failure
            for rec in records:
                rec['status'] = 'FAIL_INDEPENDENT_QA'
                rec['failure_reason'] = failure
                for col in ['beta', 'SE', 'IRR', 'CI_low', 'CI_high', 'P', 'df', 'normal_IRR', 'normal_CI_low', 'normal_CI_high', 'normal_P', 'Early_Late_covariance']:
                    rec[col] = ''
        a.cw(a.OUT / '04D_B_Model_Results.csv', rows)
        a.cw(a.OUT / '04D_B_Model_Gates.csv', gates)
        a.jw(a.OUT / '04D_B_Independent_Numerical_QA.json', {'status': 'RUNNING', 'models_checked': summary, 'algorithm': 'independent direct Newton and rowwise sandwich, same eight specifications only'})
        print('INDEPENDENT_QA', name, g['G_NUMERICAL_QA'], failure, flush=True)
    status = 'PASS' if all((g['numerical_status'] == 'PASS' for g in gates)) else 'FAIL_OR_PRIMARY_FAILURE_RETAINED'
    a.jw(a.OUT / '04D_B_Independent_Numerical_QA.json', {'status': status, 'models': 8, 'model_pass': sum((g['numerical_status'] == 'PASS' for g in gates)), 'target_records': len(rows), 'all_failures_blank': all((all((r.get(k, '') == '' for k in ['beta', 'SE', 'IRR', 'CI_low', 'CI_high', 'P'])) for r in rows if r['status'] != 'PASS')), 'method': 'Independent direct Poisson Newton from fixed exposure start; beta, score, Hessian, full CR1 covariance, t/normal independently calculated. No stat_core fitting/covariance/inference calls in validation itself; retry restored blanked native scalars from immutable native objects using native inference, before independent arithmetic checks. Additional optimization validates the same8 specifications, not an expanded model family.', 'first_attempt_failure_retained': 'independent_QA_first_attempt; FFSU native F0 Newton1000 limit; first failed partial iterate history not recorded by original implementation, NOT_VERIFIABLE; corrected implementation checkpoints every actual iterate' if retry else None, 'retry_scope': 'one failed validator, exact same data/X/core/tolerances and start; seven completed validations reused' if retry else None, 'normal_critical': 1.96, 'models_checked': summary, 'QA_code_sha': a.sha(a.CODE / 'independent_qa.py')})
    a.checkpoint('independent_QA', {'status': status, 'models_checked': 8})
    a.protect_check()
if __name__ == '__main__':
    run()
