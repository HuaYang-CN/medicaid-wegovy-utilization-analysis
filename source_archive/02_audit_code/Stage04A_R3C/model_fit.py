"""C5 native PPML fit, preset starts/tolerances, explicit covariance gates."""
from common import *
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import traceback
import numpy as np
from stat_core import glm_fit, covariance, inference
from design_audit import array_hash

def clean(v):
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, dict):
        return {k: clean(w) for k, w in v.items()}
    if isinstance(v, list):
        return [clean(w) for w in v]
    return v

def main():
    assert jr(WORK / 'environment_gate.json')['G_ENV'] == 'PASS'
    assert jr(WORK / 'data_gate.json')['G_DATA'] == 'PASS' and jr(WORK / 'design_gate.json')['G_TARGET'] == 'PASS'
    record('C5_model')
    h = jr(OUT / '04A_R3C_Model_Input_Hashes.json')
    micro = covariance(np.ones((4, 1)), np.array([1.0, 3.0, 2.0, 6.0]), np.full(4, 3.0), np.array(['a', 'a', 'b', 'b']))
    assert micro['covariance_gate'] and abs(micro['V'][0, 0] - 1 / 9) < 1e-12
    jw(WORK / 'C5_covariance_micro_recheck.json', {'Status': 'PASS', 'Expected': 1 / 9, 'Actual': float(micro['V'][0, 0]), 'Reason': 'PSD_scale implementation changed to locked symmetric norm'})
    assert sha(WORK / 'effective_model.npz') == h['effective_full_npz_sha256'], 'full input NPZ changed'
    d = np.load(safe(WORK / 'effective_model.npz'), allow_pickle=False)
    X = d['X']
    y = d['y']
    off = d['offset']
    cl = d['clusters']
    names = d['names'].tolist()
    j = names.index('DDD')
    assert array_hash(X) == h['effective_X_hash'] and kh(names) == h['effective_names_hash'] and (kh(d['keys']) == h['effective_row_order_hash'])
    exposure = np.zeros(X.shape[1])
    exposure[0] = np.log((y.sum() + 0.1) / np.exp(off).sum())
    specs = [('exposure_start', exposure, 1e-10), ('zero_start', np.zeros(X.shape[1]), 1e-10), ('tightened', exposure, 1e-12)]
    runs = []
    results = []
    summaries = []
    for label, start, tol in specs:
        r = glm_fit(y, X, off, start, tol)
        jw(WORK / (label + '_solver.json'), clean({k: v for k, v in r.items() if k not in {'mu', 'raw_score', 'params'}}))
        np.savez_compressed(target(WORK / (label + '_fit.npz')), params=r['params'], mu=r['mu'], raw_score=r['raw_score'], X_hash=np.array(h['effective_X_hash']))
        summary = {k: v for k, v in r.items() if k not in {'history', 'mu', 'raw_score', 'params'}}
        summary.update(run=label, tolerance=tol, beta=float(r['params'][j]))
        if r['solver_gate']:
            c = covariance(X, y, r['mu'], cl)
            assert np.isfinite(c['V'][j, j])
            c['covariance_gate'] = bool(c['covariance_gate'] and c['V'][j, j] > 0)
            np.savez_compressed(target(WORK / (label + '_covariance.npz')), **{k: v for k, v in c.items() if isinstance(v, np.ndarray)})
            summary.update({k: v for k, v in c.items() if not isinstance(v, np.ndarray)})
            jw(WORK / (label + '_covariance_diagnostics.json'), clean({k: v for k, v in c.items() if not isinstance(v, np.ndarray)}))
            if c['covariance_gate']:
                effect = inference(r['params'][j], c['V'][j, j], c['G'], 't')
                results.append({'Run': label, 'Result_class': jr(WORK / 'design_gate.json')['candidate_result_label'], 'Sample_hash': h['effective_sample_hash'], 'Model_input_hash': h['effective_model_input_hash'], 'n': c['n'], 'G': c['G'], 'rank': c['r'], 'G_SOLVER': 'PASS', 'G_COV': 'PASS', **effect})
        summaries.append(clean(summary))
        runs.append((label, r))
        jw(WORK / 'C5_runs_so_far.json', summaries)
        print(label + ' solver=' + str(r['solver_gate']) + '; beta=' + str(r['params'][j]), flush=True)
    solver = all((r['solver_gate'] for _, r in runs))
    cov = all((s.get('covariance_gate', False) for s in summaries))
    base = runs[0][1]
    differences = []
    for label, r in runs[1:]:
        bd = abs(r['params'][j] - base['params'][j])
        muok = np.all(np.abs(r['mu'] - base['mu']) <= 1e-08 + 1e-06 * np.abs(base['mu']))
        V = np.load(safe(WORK / (label + '_covariance.npz')))['V'] if cov else None
        Vb = np.load(safe(WORK / 'exposure_start_covariance.npz'))['V'] if cov else None
        vok = bool(np.all(np.abs(V - Vb) <= 1e-08 + 0.0001 * np.abs(Vb))) if cov else False
        seok = bool(abs(np.sqrt(V[j, j]) - np.sqrt(Vb[j, j])) <= 1e-06 + 0.0001 * abs(np.sqrt(Vb[j, j]))) if cov else False
        bok = bd <= 1e-06 + 1e-06 * abs(base['params'][j])
        differences.append({'run': label, 'beta_absolute_difference': bd, 'beta_tolerance_pass': bool(bok), 'mu_tolerance_pass': bool(muok), 'V_tolerance_pass': vok, 'SE_tolerance_pass': seok})
        solver = solver and bool(bok) and bool(muok)
        cov = cov and vok and seok
    gate = {'G_SOLVER': 'PASS' if solver else 'FAIL', 'G_COV': 'PASS' if cov else 'FAIL', 'runs': summaries, 'stability': differences, 'interpretation_allowed': bool(solver and cov), 'result_scope': jr(WORK / 'design_gate.json')['candidate_result_label'] if solver and cov else 'REPLICATION_FAILED'}
    jw(WORK / 'solver_gate.json', gate)
    if not (solver and cov):
        jw(WORK / 'C5_unvalidated_target_estimates.json', results)
        raise RuntimeError('required solver/covariance/stability gate failed')
    cw(OUT / '04A_R3C_Independent_PPML_Results.csv', results)
    report = []
    for s in summaries:
        report.append(f"- {s['run']}: beta={s['beta']:.17g}; tolerance={s['tolerance']}; native converged={s['converged']}; actual iterations={s['iterations']}; normalized score={s['normalized_score']:.17g}; last-five relative max={s['last_five_deviance_relative_max']:.17g}; objective={s['objective_explanation']}; warnings={s['warnings']}")
    md('04A_R3C_Solver_Convergence.md', '# C5 求解验收\n\nG_SOLVER=PASS。同一certified effective模型，预设人口初值、零初值和tol1e-12复核，未依据旧IRR挑选；native statsmodels Poisson GLM/Log/offset，IRLS QR，无clip/pinv。最多6段同模型原生续算用于实际末五步验证，所有更新及native flag/history均本地保存，无虚构填充。\n\n' + '\n'.join(report) + '\n\n完整score、mu、FE参数、native deviance history及warnings本地保存。两初值与收紧tol按锁定β、mu、SE、V容差全部通过。完整requested FE分离未做伪有限拟合；本估计不修旧缺源零/RI/Q1/policy。数值有效性不授因果或患者公平解释。')
    c = summaries[0]
    md('04A_R3C_Inference_Validity.md', f"# C5 显式簇协方差\n\nG_COV=PASS。r={c['r']}、n={c['n']}、G={c['G']}；CR1=G/(G−1)*(n−1)/(n−r)={c['CR1']:.17g}。每州score、meat、Poisson信息bread及完整V均本地保存。结构尺度c先固定，Z=sqrt(mu)*(X/c)不二次缩放；weighted rank={c['weighted_rank']}，condition={c['weighted_condition']:.17g}；bread为可估空间正定solve，无pinv。symmetry relative={c['symmetry_relative']:.17g}；λmin={c['min_eigenvalue']:.17g}、PSD scale={c['PSD_scale']:.17g}，按1e-10锁定门槛通过，数值级负特征照实保留。目标variance严格正，不clamp。完整V的rank≤G−1属簇结构，不要求104参数V正定。\n\n主推断双侧t(G−1)，df45，原normal/1.96另在legacy对照。不是把新P与原P差异当solver失败。此处只有数值门槛，不验因果识别、真实源完备性或资格人群构念。\n")
    print('G_SOLVER=PASS; G_COV=PASS')
if __name__ == '__main__':
    try:
        main()
    except Exception:
        target(WORK / 'C5_failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
