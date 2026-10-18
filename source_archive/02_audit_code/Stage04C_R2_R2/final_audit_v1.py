"""Artifact-level acceptance crosschecks. Read saved model objects; no fits."""
import ast, math
import audit_v1 as a
import independent_qa_v1 as iq
import release_v1 as r
import numpy as np

def run():
    rows = []
    results = a.rc(a.OUT / '04C_R2_Model_Results.csv')
    gates = a.rc(a.OUT / '04C_R2_Model_Gates.csv')
    assert len(gates) == 7 and len(results) == 14 and (sum((x['support'] == 'NATIVE' for x in results)) == 8)
    for p in a.CODE.glob('*.py'):
        ast.parse(a.safe(p).read_text(encoding='utf-8'))
    for m in a.MODELS:
        d = a.WORK / m
        acc = r.accepted(m)
        ob = np.load(d / 'input.npz', allow_pickle=False)
        X, y, off = [ob[k] for k in ['X', 'y', 'offset']]
        di = a.jr(d / 'diagnostics.json')
        ref = np.load(d / 'exposure_fit.npz', allow_pickle=False)
        cv = np.load(acc / 'exposure_cov.npz', allow_pickle=False)
        cm = a.jr(acc / 'exposure_cov.json')
        checks = {}
        for l in ['exposure', 'zero', 'tight']:
            f = np.load(d / (l + '_fit.npz'), allow_pickle=False)
            s = a.jr(d / (l + '_solver.json'))
            checks[l + '_mu_stability'] = iq.close(f['mu'], ref['mu'], 1e-08, 1e-06)
            checks[l + '_predictor_mu_identity'] = iq.close(np.exp(off + X @ f['params']), f['mu'], 1e-08, 1e-06)
            hist = s['history']
            D = [h['deviance'] for h in hist]
            diff = [abs(v - u) / (1 + abs(u)) for u, v in zip(D[:-1], D[1:])]
            checks[l + '_real_last5_objective'] = len(diff) >= 5 and max(diff[-5:]) <= 1e-10
            checks[l + '_score'] = a.sc.normalized_score(X, y, f['mu'])[1] <= 1e-08
            checks[l + '_iterations'] = s['converged'] and s['iterations'] < 1000
        for t in di['targets']:
            j = t['index']
            inf = iq.infer(float(ref['params'][j]), float(cv['V'][j, j]), int(cm['G']))
            for rec in [x for x in results if x['Variant_ID'] == m and x['target'] == t['name']]:
                checks[t['name'] + '_' + rec['support'] + '_table_inference'] = all((iq.close(float(rec[k]), inf[k], 1e-12, 1e-10) for k in ['beta', 'SE', 'IRR', 'CI_low', 'CI_high', 'P', 'df']))
                checks[t['name'] + '_' + rec['support'] + '_key_identity'] = rec['sample_key_hash'] == di['effective']['keys_hash'] and rec['X_hash'] == di['X_hash']
        if acc != d:
            old = np.load(d / 'exposure_cov.npz', allow_pickle=False)
            checks['factor_vs_original_algebra_within_full_cov_tolerance'] = iq.close(cv['V'], old['V'], 1e-08, 0.0001)
            old_diff = float(np.max(np.abs(cv['V'] - old['V'])))
        else:
            old_diff = 0.0
        assert all(checks.values()), (m, [k for k, v in checks.items() if not v])
        rows.append({'Variant_ID': m, 'status': 'PASS', 'checks': checks, 'max_abs_factor_vs_failed_original_cov_difference': old_diff})
    failures = a.rc(a.OUT / '04C_R2_R2_Failed_Attempts.csv')
    assert len(failures) == 2 and all((x['beta'] == x['IRR'] == x['P'] == '' for x in failures))
    a.jw(a.OUT / '04C_R2_R2_Final_Artifact_QA.json', {'status': 'PASS', 'models': rows, 'code_AST': 'PASS', 'result_target_rows': 14, 'native_target_rows': 8, 'failed_attempt_rows_blank': True, 'calibration_and_source_QA_reused': True, 'new_fits': 0})
    print('FINAL ARTIFACT QA PASS 7 models;14 result rows; all failures retained; no fits', flush=True)
if __name__ == '__main__':
    run()
