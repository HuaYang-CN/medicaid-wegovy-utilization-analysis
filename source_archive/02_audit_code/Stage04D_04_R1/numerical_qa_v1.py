"""Reviewed copied pure numerical/source functions; independent of primary GLM."""
import math
import numpy as np
from scipy import stats
import audit_v1 as a

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
