"""C6 isolated rewrite of statically reviewed legacy formulas, no historical import.
Historical clip/pinv/clamp are diagnostic only, never grant finite-MLE validity.
"""
from common import *
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import traceback
import numpy as np
from scipy import stats
from stat_core import normalized_score, rank_info, inference
from model_fit import clean

def legacy(y, X, off, cl):
    b = np.zeros(X.shape[1])
    b[0] = np.log((y.sum() + 0.1) / np.exp(off).sum())
    hist = []
    converged = False
    for i in range(200):
        eta0 = off + X @ b
        mu = np.exp(np.clip(eta0, -25, 25))
        z = X @ b + (y - mu) / np.maximum(mu, 1e-09)
        new = np.linalg.pinv(X * np.sqrt(mu)[:, None]) @ (z * np.sqrt(mu))
        step = float(np.max(np.abs(new - b)))
        stop = step < 1e-09
        b = new if stop else 0.5 * b + 0.5 * new
        m = np.exp(np.clip(off + X @ b, -25, 25))
        _, score = normalized_score(X, y, m)
        hist.append({'iteration': i + 1, 'max_full_step': step, 'DDD': float(b[-1]), 'min_beta': float(b.min()), 'clip_count_pre_update': int(((eta0 < -25) | (eta0 > 25)).sum()), 'normalized_score': score})
        if stop:
            converged = True
            break
    mu = np.exp(np.clip(off + X @ b, -25, 25))
    H = X.T @ (mu[:, None] * X)
    bread = np.linalg.pinv(H)
    groups = np.unique(cl)
    scores = np.stack([X[cl == g].T @ (y[cl == g] - mu[cl == g]) for g in groups])
    meat = scores.T @ scores
    cr = len(groups) / (len(groups) - 1) * (len(y) - 1) / max(len(y) - X.shape[1], 1)
    V = cr * (bread @ meat @ bread)
    se = np.sqrt(np.maximum(np.diag(V), 0))
    z = b[-1] / se[-1] if se[-1] > 0 else 0.0
    effect = {'beta': float(b[-1]), 'SE': float(se[-1]), 'IRR': float(np.exp(b[-1])), 'CI_low': float(np.exp(b[-1] - 1.96 * se[-1])), 'CI_high': float(np.exp(b[-1] + 1.96 * se[-1])), 'P': float(2 * stats.norm.sf(abs(z))), 'reference': 'normal', 'df': None}
    return {'params': b, 'mu': mu, 'H': H, 'bread': bread, 'meat': meat, 'V': V, 'cluster_scores': scores, 'CR1': cr, 'native_legacy_step_stop': converged, 'iterations': len(hist), 'history': hist, 'effect': effect, 'negative_diagonal_before_legacy_clamp': int((np.diag(V) < 0).sum()), 'normalized_score': normalized_score(X, y, mu)[1]}

def main():
    assert jr(WORK / 'solver_gate.json')['interpretation_allowed']
    record('C6_legacy')
    h = jr(OUT / '04A_R3C_Model_Input_Hashes.json')
    old = jr(WORK / 'original_saved_result.json')
    saved = {'beta': float(old['estimate']), 'SE': float(old['std_error']), 'IRR': float(old['effect']), 'CI_low': float(old['effect_low']), 'CI_high': float(old['effect_high']), 'P': float(old['p_value'])}
    rows = [{'Implementation': 'ORIGINAL_SAVED_RESULT', 'Result_class': 'ORIGINAL_SAVED_RESULT', 'n': 1012, 'G': 46, 'rank': 'NOT_VERIFIABLE', 'Sample_hash': 'NOT_VERIFIABLE_ORIGINAL_RUN', 'Converged': 'NOT_VERIFIABLE', 'reference': 'normal', 'df': 'NA', **saved}]
    alllegacy = {}
    for label in ['requested', 'effective']:
        assert sha(WORK / (label + '_model.npz')) == h[label + '_full_npz_sha256'], 'full input NPZ changed'
        d = np.load(safe(WORK / (label + '_model.npz')), allow_pickle=False)
        r = legacy(d['y'], d['X'], d['offset'], d['clusters'])
        alllegacy[label] = r
        np.savez_compressed(target(WORK / (label + '_legacy_full.npz')), **{k: v for k, v in r.items() if isinstance(v, np.ndarray)})
        jw(WORK / (label + '_legacy_diagnostics.json'), clean({k: v for k, v in r.items() if not isinstance(v, np.ndarray)}))
        rows.append({'Implementation': 'INDEPENDENT_LEGACY_REIMPLEMENTATION_' + label.upper(), 'Result_class': 'REPLICATION_FAILED' if label == 'requested' and (not jr(WORK / 'design_gate.json')['full_finite_FE_MLE']) else 'LEGACY_DIAGNOSTIC', 'n': len(d['y']), 'G': len(np.unique(d['clusters'])), 'rank': rank_info(d['X'])['rank'], 'Sample_hash': h[label + '_sample_hash'], 'Converged': str(r['native_legacy_step_stop']), **r['effect']})
        print(label + ' legacy iterations=' + str(r['iterations']) + ' step-stop=' + str(r['native_legacy_step_stop']), flush=True)
    d = np.load(safe(WORK / 'effective_model.npz'))
    j = d['names'].tolist().index('DDD')
    native = np.load(safe(WORK / 'exposure_start_fit.npz'))
    cv = np.load(safe(WORK / 'exposure_start_covariance.npz'))
    V = cv['V']
    G = len(np.unique(d['clusters']))
    for ref in ['t', 'normal']:
        rows.append({'Implementation': 'INDEPENDENT_STATSMODELS_' + ref.upper(), 'Result_class': 'VALID_EFFECTIVE_SAMPLE_RESULT', 'n': len(d['y']), 'G': G, 'rank': d['X'].shape[1], 'Sample_hash': h['effective_sample_hash'], 'Converged': 'True', **inference(native['params'][j], V[j, j], G, ref)})
    cw(OUT / '04A_R3C_Legacy_Comparison.csv', rows, ['Implementation', 'Result_class', 'n', 'G', 'rank', 'Sample_hash', 'Converged', 'reference', 'df', 'beta', 'SE', 'IRR', 'CI_low', 'CI_high', 'P'])
    l = alllegacy['effective']
    beta = float(native['params'][j])
    se = float(np.sqrt(V[j, j]))
    aligned = {'comparison': 'NATIVE_vs_LEGACY_SAME_EFFECTIVE_SUPPORT', 'beta_absolute_difference': abs(beta - l['effect']['beta']), 'beta_pass': bool(abs(beta - l['effect']['beta']) <= 1e-06 + 1e-06 * abs(l['effect']['beta'])), 'SE_absolute_difference': abs(se - l['effect']['SE']), 'SE_pass': bool(abs(se - l['effect']['SE']) <= 1e-06 + 0.0001 * abs(l['effect']['SE'])), 'covariance_pass': bool(np.all(np.abs(V - l['V']) <= 1e-08 + 0.0001 * np.abs(l['V']))), 'mu_pass': bool(np.all(np.abs(native['mu'] - l['mu']) <= 1e-08 + 1e-06 * np.abs(l['mu']))), 'legacy_step_stop': l['native_legacy_step_stop'], 'legacy_score': l['normalized_score']}
    aligned['legacy_finite_effective_diagnostic_valid'] = bool(l['native_legacy_step_stop'] and l['normalized_score'] <= 1e-08)
    matched = {'beta_saved_absolute_difference': abs(beta - saved['beta']), 'beta_saved_tolerance_pass': bool(abs(beta - saved['beta']) <= 1e-06 + 1e-06 * abs(saved['beta'])), 'SE_saved_absolute_difference': abs(se - saved['SE']), 'SE_saved_tolerance_pass': bool(abs(se - saved['SE']) <= 1e-06 + 0.0001 * abs(saved['SE'])), 'strict_full_finite_MLE_replication': bool(jr(WORK / 'design_gate.json')['full_finite_FE_MLE']), 'aligned_legacy': aligned}
    jw(WORK / 'comparison_gate.json', matched)
    compare = []
    for field in ['beta', 'SE', 'IRR', 'CI_low', 'CI_high', 'P']:
        mainres = inference(beta, V[j, j], G, 't')
        normal = inference(beta, V[j, j], G, 'normal')
        compare.append({'Metric': field, 'Original_saved': saved[field], 'Independent_effective_t45': mainres[field], 'Independent_effective_normal': normal[field], 'Absolute_difference_t_main': abs(mainres[field] - saved[field]), 'Interpretation': 'beta numeric tolerance only, full requested finite FE MLE absent' if field == 'beta' else 'rank/sample CR1; align common effective support separately' if field == 'SE' else 'effective support and t45 vs historical normal; no causal validation'})
    cw(OUT / '04A_R3C_Original_vs_Independent.csv', compare)
    md('04A_R3C_C6_Comparison_Note.md', f"# C6 原与新独立实现\n\n静态原fit_ppml、cluster_covariance及inference_table重写，不import历史脚本。requested与effective各保存200上限、每次步长/DDD/score/minFE/clip数量，完整beta/mu/H/bread/meat/V/cluster scores本地保存。legacy clip[-25,25]、pinv、半步阻尼及diagonal clamp仅忠实诊断，不授有限MLE成功标签。\n\nrequested legacy迭代{alllegacy['requested']['iterations']}、step-stop={alllegacy['requested']['native_legacy_step_stop']}，完整requested FE有限解不存在，不能REPRODUCED_ORIGINAL_SPEC，即使数值β匹配。effective legacy迭代{l['iterations']}、step-stop={l['native_legacy_step_stop']}；共同有效支持和同CR1/normal的β、SE、全V、mu验收={aligned}。失败或不显著结果全部保留。\n\nsaved β比较={matched['beta_saved_tolerance_pass']}，abs差{matched['beta_saved_absolute_difference']:.17g}；SE比较={matched['SE_saved_tolerance_pass']}，abs差{matched['SE_saved_absolute_difference']:.17g}。原run exact sample/order/environment/cov不可恢复，不冒称其内部诊断已知。新版main t45区间/P与旧normal分开，差异不自动说明β复现失败。历史结果不覆盖，数值同现不改变缺源/RI/政策时序/渠道和因果P0。\n")
    print(matched)
if __name__ == '__main__':
    try:
        main()
    except Exception:
        target(WORK / 'C6_failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
