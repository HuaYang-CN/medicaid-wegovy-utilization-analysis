"""Actual frozen-F0 cluster score/Hessian/leverage and two approximations.
No PPML fit. Exact LOO values joined only from independently accepted objects.
"""
import json, math, sys
import audit_v1 as a
import numpy as np
from scipy import linalg as la

def metrics():
    base = a.frame(a.WORK / 'BASE_input.csv')
    z = np.load(a.CW / 'PRIMARY_BINARY_CLEAN_design.npz', allow_pickle=False)
    saved = np.load(a.CW / 'primary_run_1_full.npz', allow_pickle=False)
    X, y, off, cl = [z[k] for k in ['X', 'y', 'offset', 'clusters']]
    mu = saved['mu']
    j = z['names'].tolist().index('Post×DDD')
    H = X.T @ (mu[:, None] * X)
    L = la.cholesky(H, lower=True)
    bread = la.cho_solve((L, True), np.eye(X.shape[1]))
    Z = X * np.sqrt(mu)[:, None]
    Q, R = la.qr(Z, mode='economic')
    Qn, _ = la.qr(np.delete(Z, j, axis=1), mode='economic')
    v = Z[:, j] - Qn @ (Qn.T @ Z[:, j])
    information = float(v @ v)
    assert abs(information - 1 / bread[j, j]) <= 1e-08 * information
    groups = np.unique(cl)
    scores = np.stack([X[cl == g].T @ (y[cl == g] - mu[cl == g]) for g in groups])
    target_score = np.array([float(bread[j] @ u) for u in scores])
    variance_sum = float(target_score @ target_score)
    rows = []
    checks = []
    for i, g in enumerate(groups):
        d = a.WORK / g
        take = cl == g
        Hg = X[take].T @ (mu[take, None] * X[take])
        Ug = scores[i]
        standard = la.solve_triangular(L, Ug, lower=True)
        hat = Q[take] @ Q[take].T
        ev = la.eigvalsh(hat)
        trace = float(np.trace(hat))
        maximum = float(ev[-1])
        native_hat = Z[take] @ bread @ Z[take].T
        ui = np.einsum('ij,i->j', X[take], y[take] - mu[take])
        hi = np.einsum('ij,i,ik->jk', X[take], mu[take], X[take])
        hs = np.linalg.solve(H, Z[take].T)
        hat_i = np.einsum('ik,kj->ij', Z[take], hs)
        err = float(np.max(np.abs(hat - hat_i)))
        assert np.allclose(Ug, ui, atol=1e-07, rtol=1e-08) and np.allclose(Hg, hi, atol=1e-08, rtol=1e-08) and (err < 1e-08) and (ev[0] >= -1e-10) and (maximum <= 1 + 1e-08)
        diag = a.jr(d / 'diagnostics.json')
        ij = ''
        delta = ''
        approx_beta = ''
        approx_status = 'NOT_IDENTIFIABLE_TARGET'
        identity = ''
        hminus_condition = ''
        if diag['target_estimable']:
            f = a.frame(d / 'effective.csv')
            ob = np.load(d / 'input.npz', allow_pickle=False)
            Xm = ob['X']
            jm = diag['DDD_index']
            retained = np.array([k in set(a.keys(f)) for k in z['keys'].tolist()])
            eta = np.log(mu[retained]) - off[retained]
            qm, rm = la.qr(Xm, mode='economic')
            bbar = la.solve_triangular(rm, qm.T @ eta)
            identity = float(np.max(np.abs(Xm @ bbar - eta)))
            assert identity < 1e-10 and abs(bbar[jm] - saved['params'][j]) < 1e-09
            mum = mu[retained]
            Sm = Xm.T @ (ob['y'] - mum)
            Hm = Xm.T @ (mum[:, None] * Xm)
            cm = la.cho_factor(Hm, lower=True)
            step = la.cho_solve(cm, Sm)
            delta = float(step[jm])
            approx_beta = float(bbar[jm] + step[jm])
            ij = float(-bread[j] @ Ug)
            approx_status = 'DEFINED_NEWTON_AT_FULL_PREDICTIONS_RETAINED_ESTIMABLE_SPACE'
            hminus_condition = float(np.linalg.cond(Hm))
            np.savez_compressed(a.target(d / 'one_step_objects.npz'), full_prediction_remaining_mu=mum, full_prediction_remaining_params=bbar, Hminus=Hm, remaining_score=Sm, Newton_step=step, IJ_full=-bread @ Ug)
        np.savez_compressed(a.target(d / 'cluster_diagnostic_objects.npz'), cluster_score=Ug, Hessian_contribution=Hg, cluster_hat=hat, leverage_eigenvalues=ev, standardized_score=standard, full_parameter_IJ=-bread @ Ug, target_residual_rows=v[take])
        rows.append({'state': g, 'group': 'COVERAGE' if g in a.COVER else 'NONCOVERAGE', 'native_rows': int(take.sum()), 'raw_cluster_score_json': json.dumps(Ug.tolist(), separators=(',', ':')), 'score_names_hash': a.kh(z['names'].tolist()), 'raw_score_norm': float(la.norm(Ug)), 'standardized_score_norm': float(la.norm(standard)), 'Hessian_trace': float(np.trace(Hg)), 'Hessian_Frobenius_norm': float(la.norm(Hg, 'fro')), 'Hessian_object_SHA256': a.sha(d / 'cluster_diagnostic_objects.npz'), 'cluster_leverage_trace': trace, 'cluster_leverage_trace_share': trace / X.shape[1], 'cluster_leverage_lambda_max': maximum, 'leverage_unit_eigenvalues': int(np.sum(np.abs(ev - 1) <= 1e-08)), 'DDD_weighted_residual_information_share': float(v[take] @ v[take] / information), 'DDD_cluster_influence_variance_share': float(target_score[i] ** 2 / variance_sum), 'one_step_IJ_target_delta': ij, 'one_step_deletion_Newton_target_delta': delta, 'one_step_deletion_Newton_beta': approx_beta, 'one_step_status': approx_status, 'full_prediction_parameter_mapping_max_residual': identity, 'Hminus_condition_raw': hminus_condition, 'target_legal_after_deletion': diag['target_estimable'], 'NM_full_target_variance_share_not_identification_proof': g == 'NM', 'metric_type': 'full-model diagnostics and approximations only; not exact LOO estimates'})
        checks.append({'state': g, 'score_einsum': 'PASS', 'Hessian_einsum': 'PASS', 'weighted_hat_QR_vs_unscaled_solve_max_abs_diff': err, 'lambda_min': float(ev[0]), 'lambda_max': maximum, 'target_one_step_permitted': diag['target_estimable']})
    assert abs(sum((r['cluster_leverage_trace'] for r in rows)) - 70) < 1e-08 and abs(sum((r['DDD_weighted_residual_information_share'] for r in rows)) - 1) < 1e-10 and (abs(sum((r['DDD_cluster_influence_variance_share'] for r in rows)) - 1) < 1e-10)
    a.cw(a.OUT / '04D_04_Cluster_Score_Leverage.csv', rows)
    a.jw(a.OUT / '04D_04_Cluster_Diagnostic_QA.json', {'status': 'PASS', 'states': checks, 'leverage_trace_sum': sum((r['cluster_leverage_trace'] for r in rows)), 'rank': 70, 'weighted_target_information': information, 'DDD_information_share_sum': sum((r['DDD_weighted_residual_information_share'] for r in rows)), 'score_variance_share_sum': sum((r['DDD_cluster_influence_variance_share'] for r in rows)), 'no_ppml_fits': True})
    a.md('04D_04_Influence_Definitions.md', "# 影响度的数学定义与边界\n\n在原冻结F0有限满秩参数基类中，mu为原接受拟合预测，U_g=X_g'(y_g-mu_g)，H_g=X_g'diag(mu_g)X_g，H=sum H_g。全cluster score向量以同一70列names顺序输出；完整H_g和杠杆矩阵本地保存，CSV登记对象SHA。标准化score范数是sqrt(U_g'H^{-1}U_g)，用Cholesky白化，不是按处方数量除后的原始范数。\n\n令Z=diag(sqrt(mu))X=QR。cluster hat块L_g=Q_g Q_g'=Z_g H^{-1}Z_g'；报告trace(L_g)、最大特征值、unit eigenvalues及trace/r。对整个样本sum trace=r=70。州产品FE意味着每个有双产品观察的州至少两个unit leverage方向，lambda_max约1是结构现象，不能据它把所有州都宣布为独特异常。trace排序和DDD残差信息份额另列，并不据排名删州。\n\n以Z中DDD列对其余列的QR投影残差v定义信息份额 q_g=v_g'v_g/(v'v)，sum q=1。它衡量在全模型mu加权的目标设计信息集中度，不是因果州权重。a_g=e_DDD'H^{-1}U_g，sandwich目标方差贡献份额 a_g²/sum a_g²；它可能对不可缺的识别州很小，因为拟合得分约束，不等于删除该州不影响识别。\n\nInfinitesimal-Jackknife删除近似 delta_IJ=-e_DDD'H^{-1}U_g，只是州权重从1向下作无穷小变化时的线性近似，不等同完整删簇后的重新拟合。\n实际一轮删除Newton近似：重新建立冻结F0的剩余满秩基类Xm，映射原full预测 eta_full-offset=Xm*bbar；Sm=Xm'(ym-mu_full_remaining)，Hm=Xm'diag(mu_full_remaining)Xm，b_one=bbar+Hm^{-1}Sm。报告target的step和beta；这是在删除后可估空间的真实Newton一步，没有执行优化收敛，也没有推断区间。它可与最终实际LOO beta差异比较。\n\n直接在原70参数空间求(H-Hg)^{-1}不合法，因为该州SP参数失去观察；本轮只在删除后重新规范化且目标可识别的空间求解。NM目标不可识别时两种target删除近似以及真实beta/delta均留空，不以有限infinitesimal表达掩盖原目标失败。未用pinv、ridge、clip或删除下阶项救识别。\n\n真正LOO只来自每州重新拟合、全数值门槛和独立QA；矩阵检查与以上近似不能计为成功回归。预设方向变化/abs(delta)>0.5只触发解释CAUTION，不选择性剔除。全β接近0，微小符号改变须结合实际量级及CI。")
    print('CLUSTER METRICS PASS 29, no fits; leverage traces sum70', flush=True)
if __name__ == '__main__':
    globals()[sys.argv[1]]()
