"""Fit only newly missing formal 04B tasks; exact validated reuse by input hash.
Every new numerical calculation receives two starts, tighter tolerance and full
covariance. No historical module, clip, pinv or significance-based choice.
"""
from common import *
import traceback, math
import numpy as np
from stat_core import glm_fit, covariance, inference

def clean(v):
    if isinstance(v, np.ndarray):
        return clean(v.tolist())
    if isinstance(v, np.generic):
        return clean(v.item())
    if isinstance(v, float) and (not math.isfinite(v)):
        return str(v)
    if isinstance(v, dict):
        return {k: clean(w) for k, w in v.items()}
    if isinstance(v, list):
        return [clean(w) for w in v]
    return v

def calculate(diag, cache):
    signature = diag['model_input_hash']
    if signature in cache:
        return (cache[signature], True)
    path = WORK / (diag['label'] + '_model.npz')
    assert sha(path) == diag['full_npz_sha256']
    d = np.load(safe(path), allow_pickle=False)
    X = d['X']
    y = d['y']
    off = d['offset']
    cl = d['clusters']
    names = d['names'].tolist()
    j = names.index('DDD')
    assert len(y) == diag['n'] and len(np.unique(cl)) == diag['G']
    directory = target(WORK / 'calculations' / signature[:20] / 'placeholder').parent
    exposure = np.zeros(X.shape[1])
    exposure[0] = np.log((y.sum() + 0.1) / np.exp(off).sum())
    specs = [('exposure', exposure, 1e-10), ('zero', np.zeros(X.shape[1]), 1e-10), ('tight', exposure, 1e-12)]
    runs = []
    summaries = []
    result = {'Status': 'FAILED', 'G_SOLVER': 'FAIL', 'G_COV': 'NOT_VERIFIABLE', 'signature': signature, 'directory': str(directory)}
    try:
        for label, start, tol in specs:
            r = glm_fit(y, X, off, start, tol)
            jw(directory / (label + '_solver.json'), clean({k: v for k, v in r.items() if k not in {'params', 'mu', 'raw_score'}}))
            np.savez_compressed(target(directory / (label + '_fit.npz')), params=r['params'], mu=r['mu'], raw_score=r['raw_score'], names=d['names'])
            summary = {k: v for k, v in r.items() if k not in {'params', 'mu', 'raw_score', 'history'}}
            summary.update(run=label, tolerance=tol, beta=float(r['params'][j]))
            c = None
            if r['solver_gate']:
                c = covariance(X, y, r['mu'], cl)
                c['covariance_gate'] = bool(c['covariance_gate'] and np.isfinite(c['V'][j, j]) and (c['V'][j, j] > 0))
                np.savez_compressed(target(directory / (label + '_cov.npz')), **{k: v for k, v in c.items() if isinstance(v, np.ndarray)})
                cs = {k: v for k, v in c.items() if not isinstance(v, np.ndarray)}
                summary['covariance'] = cs
                jw(directory / (label + '_cov.json'), clean(cs))
            summaries.append(clean(summary))
            runs.append((r, c))
            jw(directory / 'attempts_so_far.json', summaries)
        solver = all((r['solver_gate'] for r, c in runs))
        cov = all((c is not None and c['covariance_gate'] for r, c in runs))
        stability = []
        base, bc = runs[0]
        for label, (r, c) in zip(['zero', 'tight'], runs[1:]):
            bd = abs(r['params'][j] - base['params'][j])
            bok = bd <= 1e-06 + 1e-06 * abs(base['params'][j])
            muok = bool(np.all(np.abs(r['mu'] - base['mu']) <= 1e-08 + 1e-06 * np.abs(base['mu'])))
            vok = bool(np.all(np.abs(c['V'] - bc['V']) <= 1e-08 + 0.0001 * np.abs(bc['V']))) if cov else False
            seok = bool(abs(np.sqrt(c['V'][j, j]) - np.sqrt(bc['V'][j, j])) <= 1e-06 + 0.0001 * abs(np.sqrt(bc['V'][j, j]))) if cov else False
            stability.append({'run': label, 'beta_abs_diff': bd, 'beta_pass': bool(bok), 'mu_pass': muok, 'covariance_pass': vok, 'SE_pass': seok})
            solver = solver and bool(bok) and muok
            cov = cov and vok and seok
        result.update(G_SOLVER='PASS' if solver else 'FAIL', G_COV='PASS' if cov else 'FAIL', runs=summaries, stability=stability)
        if solver and cov:
            result.update(Status='COMPLETE_VERIFIED', effect=inference(base['params'][j], bc['V'][j, j], bc['G'], 't'), rank=bc['r'], G=bc['G'], n=bc['n'], CR1=bc['CR1'], primary_iterations=base['iterations'], primary_score=base['normalized_score'], primary_last_five=base['last_five_deviance_relative_max'], primary_loglike=base['loglike'], primary_deviance=base['deviance'])
    except Exception as e:
        target(directory / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        result.update(reason=type(e).__name__ + ': ' + str(e))
    jw(directory / 'calculation.json', clean(result))
    result['artifact_sha'] = {p.name: sha(p) for p in directory.iterdir() if p.is_file()}
    cache[signature] = result
    jw(WORK / 'calculation_cache_index.json', clean(cache))
    return (result, False)

def baseline(diag):
    assert diag['row_key_hash'] == jr(A / '04A_R3C_Model_Input_Hashes.json')['effective_sample_hash']
    aligned = jr(WORK / 'baseline_input_alignment_verified.json')
    assert all(aligned.values())
    assert diag['model_input_hash'] == jr(A / '04A_R3C_Model_Input_Hashes.json')['effective_model_input_hash']
    ag = jr(A / '_working/solver_gate.json')
    assert ag['interpretation_allowed']
    ar = next((r for r in rc(A / '04A_R3C_Independent_PPML_Results.csv') if r['Run'] == 'exposure_start'))
    ad = np.load(safe(A / '_working/effective_model.npz'))
    fit = np.load(safe(A / '_working/exposure_start_fit.npz'))
    cv = np.load(safe(A / '_working/exposure_start_covariance.npz'))
    j = ad['names'].tolist().index('DDD')
    assert abs(fit['params'][j] - float(ar['beta'])) <= 1e-15 and abs(np.sqrt(cv['V'][j, j]) - float(ar['SE'])) <= 1e-15
    g = jr(A / '_working/exposure_start_solver.json')
    c = jr(A / '_working/exposure_start_covariance_diagnostics.json')
    effect = {k: float(ar[k]) for k in ['beta', 'SE', 'IRR', 'CI_low', 'CI_high', 'P']}
    effect.update(reference='t', df=45)
    return {'Status': 'COMPLETE_VERIFIED', 'G_SOLVER': 'PASS', 'G_COV': 'PASS', 'signature': diag['model_input_hash'], 'directory': str(A / '_working'), 'effect': effect, 'rank': 104, 'G': 46, 'n': 1001, 'CR1': c['CR1'], 'primary_iterations': g['iterations'], 'primary_score': g['normalized_score'], 'primary_last_five': g['last_five_deviance_relative_max'], 'primary_loglike': g['loglike'], 'primary_deviance': g['deviance'], 'reuse': 'VERIFIED_04A_BASELINE_NO_FIT', 'artifact_sha': {'exposure_start_fit.npz': sha(A / '_working/exposure_start_fit.npz'), 'exposure_start_covariance.npz': sha(A / '_working/exposure_start_covariance.npz')}}

def main():
    assert jr(WORK / 'diagnosis_complete.json')['Status'] == 'COMPLETE_VERIFIED'
    record('fit')
    eg = jr(WORK / 'environment_gate.json')
    ig = jr(WORK / 'input_gate.json')
    assert eg['G_ENV'] == 'PASS' and eg['stat_core_sha256'] == sha(CODE / 'stat_core.py') and (ig['G_DATA'] == 'PASS')
    assert ig['variant_manifest_sha'] == sha(WORK / 'variant_manifest.json') and ig['plan_sha'] == sha(WORK / 'prospective_plan.json')
    for r in jr(WORK / 'protected_before.json'):
        assert sha(r['path']) == r['sha256']
    manifest = jr(WORK / 'variant_manifest.json')
    mv = {v['Variant_ID']: v for v in manifest}
    ni = jr(WORK / 'native_diagnostics_index.json')
    ci = jr(WORK / 'common_diagnostics_index.json')
    cache = {}
    cache[ni['R3_M0_MID']['model_input_hash']] = baseline(ni['R3_M0_MID'])
    jobs = [(v['Variant_ID'], 'NATIVE', 'NONE', ni[v['Variant_ID']], True) for v in manifest]
    jobs += [(m, 'COMMON', family, d, f['stable']) for family, f in ci.items() for m, d in f['members'].items()]
    rows = []
    gates = []
    execution = []
    fields = ['Analysis_ID', 'Variant_ID', 'Support', 'Family', 'R', 'M', 'S', 'Window', 'P1', 'F', 'Status', 'Result_class', 'Reason', 'requested_n', 'effective_n', 'G', 'coverage_G', 'noncoverage_G', 'rank', 'df', 'Sample_key_hash', 'Sample_order_hash', 'Data_hash', 'X_hash', 'Model_input_hash', 'CR1', 'beta', 'SE', 'IRR', 'CI_low', 'CI_high', 'P', 'reference', 'Iterations', 'Score', 'Last_five_deviance', 'Loglike', 'Deviance', 'Reused', 'Artifact_dir', 'Cluster_caution']
    for vid, scope, family, d, stable in jobs:
        v = mv[vid]
        row = {k: '' for k in fields}
        row.update(Analysis_ID=v['Analysis_ID'], Variant_ID=vid, Support=scope, Family=family, R=v['R'], M=v['M'], S=v['S'], Window='DATA-11', P1='P1_46_12_34', F='F0', requested_n=v['requested_n'], effective_n=d['n'], G=d['G'], coverage_G=d['coverage_G'], noncoverage_G=d['noncoverage_G'], rank=d['rank']['rank'], Sample_key_hash=d['row_key_hash'], Sample_order_hash=d['row_order_hash'], Data_hash=d['data_hash'], X_hash=d['X_hash'], Model_input_hash=d['model_input_hash'], Cluster_caution=d['group_cluster_caution'])
        assert sha(WORK / (d['label'] + '_model.npz')) == d['full_npz_sha256']
        gv = {'G_ENV': 'PASS', 'G_DATA': 'PASS', 'G_TARGET': d['G_TARGET'], 'G_SOLVER': 'NOT_VERIFIABLE', 'G_COV': 'NOT_VERIFIABLE'}
        if d['G_TARGET'] != 'PASS' or not stable:
            row.update(Status='FAILED' if stable else 'NOT_VERIFIABLE', Result_class='DIAGNOSTIC_FAILED', Reason='TARGET_SUPPORT_OR_RANK_FAILED' if stable else 'COMMON_NOT_STABLE_WITHIN10')
        else:
            r, reused = calculate(d, cache)
            gv.update(G_SOLVER=r['G_SOLVER'], G_COV=r['G_COV'])
            row.update(Status=r['Status'], Reused='VERIFIED_IDENTICAL_INPUT' if reused else 'NEW_R1_COMPUTATION', Artifact_dir=r['directory'])
            if r['Status'] == 'COMPLETE_VERIFIED':
                row.update(Result_class='VALID_EFFECTIVE_SAMPLE_RESULT' if vid == 'R3_M0_MID' else 'CORRECTED_DATA_RESULT' if v['Analysis_ID'] in {'04B-01', '04B-03'} else 'SENSITIVITY_RESULT', Reason='ASSOCIATION_ONLY; not bounds or verified full46 quantities', CR1=r['CR1'], Iterations=r['primary_iterations'], Score=r['primary_score'], Last_five_deviance=r['primary_last_five'], Loglike=r['primary_loglike'], Deviance=r['primary_deviance'], **r['effect'])
            else:
                row.update(Result_class='DIAGNOSTIC_FAILED', Reason=r.get('reason', 'SOLVER_COVARIANCE_OR_STABILITY_FAILED'))
            execution.append({'Variant_ID': vid, 'Support': scope, 'Family': family, 'model_signature': d['model_input_hash'], 'Status': r['Status'], 'Reused': reused, 'artifact_dir': r['directory']})
        rows.append(row)
        for k, val in gv.items():
            gates.append({'Analysis_ID': v['Analysis_ID'], 'Variant_ID': vid, 'Support': scope, 'Family': family, 'Gate': k, 'Status': val, 'Evidence_label': d['label'], 'Model_input_hash': d['model_input_hash']})
        cw(OUT / '04B_Model_Results.csv', rows, fields)
        cw(OUT / '04B_Model_Gates.csv', gates)
        jw(WORK / 'run_execution_index.json', execution)
        jw(WORK / 'fit_progress.json', {'jobs_completed': len(rows), 'jobs_total': len(jobs), 'unique_calculations': len(cache), 'failed_rows': sum((z['Status'] != 'COMPLETE_VERIFIED' for z in rows))})
        print(f"{vid} {scope}/{family} {row['Status']} n={d['n']} G={d['G']} reuse={row['Reused']}", flush=True)
    jw(WORK / 'fit_complete.json', {'Status': 'COMPLETE_VERIFIED', 'result_rows': len(rows), 'new_unique_calculations': len(cache) - 1, 'inherited_baseline_calculations': 1, 'failed_rows': sum((z['Status'] != 'COMPLETE_VERIFIED' for z in rows)), 'native_and_common': True, 'results_sha': sha(OUT / '04B_Model_Results.csv'), 'gates_sha': sha(OUT / '04B_Model_Gates.csv')})
    jw(WORK / 'calculation_cache_index.json', clean(cache))
    print('FIT COMPLETE; all negative/failed rows preserved; no next-stage actions')
if __name__ == '__main__':
    try:
        main()
    except Exception:
        target(WORK / 'fit_failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
