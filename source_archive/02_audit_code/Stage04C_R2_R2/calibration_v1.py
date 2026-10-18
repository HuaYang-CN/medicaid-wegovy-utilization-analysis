"""Read-only regression calibration on accepted saved objects. No model fit."""
import audit_v1 as a
import independent_qa_v1 as iq
import numpy as np

def run():
    rows = []
    for stage, design, fit, cov in [('Stage04C_A', 'PRIMARY_BINARY_CLEAN_design.npz', 'primary_run_1_full.npz', 'primary_run_1_full.npz'), ('Stage04A_R3C', 'effective_model.npz', 'exposure_start_fit.npz', 'exposure_start_covariance.npz')]:
        d = a.ROOT / '03_audit_outputs' / stage / '_working'
        z = np.load(a.safe(d / design), allow_pickle=False)
        f = np.load(a.safe(d / fit), allow_pickle=False)
        v = np.load(a.safe(d / cov), allow_pickle=False)
        X = z['X']
        y = z['y']
        cl = z['clusters']
        off = z['offset']
        mu = f['mu']
        native = a.sc.covariance(X, y, mu, cl)
        ind = iq.sandwich(X, y, mu, cl)
        j = X.shape[1] - 1
        result = iq.infer(float(f['params'][j]), float(ind['V'][j, j]), ind['G'])
        checks = {'accepted_full_cov_native': iq.close(native['V'], v['V'], 1e-08, 0.0001), 'accepted_full_cov_independent': iq.close(ind['V'], v['V'], 1e-08, 0.0001), 'score': a.sc.normalized_score(X, y, mu)[1] <= 1e-08}
        if stage == 'Stage04C_A':
            expected = {'IRR': 0.9997554671818756, 'CI_low': 0.5099157409657245, 'CI_high': 1.9601493224490112, 'P': 0.9994115852180573}
            base = a.frame(a.WORK / 'BASE_input.csv')
            actual, names = a.design(base, 'F0')
            checks['fresh_F0_same_X'] = a.xhash(actual) == a.xhash(X)
            checks['fresh_F0_same_inputs'] = np.array_equal(base.y.to_numpy(), y) and np.array_equal(base.offset.to_numpy(), off)
            checks['accepted_scalars'] = all((iq.close(result[k], v, 1e-12, 1e-10) for k, v in expected.items()))
        else:
            checks['accepted_A_IRR'] = iq.close(result['IRR'], 4.0901125792291895, 1e-12, 1e-10)
        assert all(checks.values()), str(checks)
        rows.append({'stage': stage, 'status': 'PASS', 'checks': checks, 'result_inherited_not_refitted': result, 'objects_SHA256': {n: a.sha(d / n) for n in set([design, fit, cov])}, 'actual_n_G_r': [native['n'], native['G'], native['r']], 'new_model_fits': 0})
    separated = a.sc.separation(np.eye(2), np.array([2.0, 0.0]))
    finite = a.sc.separation(np.array([[1.0, 0.0], [1.0, 1.0], [1.0, 2.0]]), np.array([2.0, 0.0, 3.0]))
    assert separated['detected'] and (not finite['detected'])
    a.jw(a.OUT / '04C_R2_R2_Core_Calibration.json', {'status': 'PASS', 'saved_objects_only': True, 'rows': rows, 'LP_synthetic_certification': 'PASS; free feasible direction and infeasible finite case', 'no_new_research_model_fit': True})
    a.md('04C_R2_R2_Static_Code_Review.md', '# 执行前静态方法核对\n\n本轮 NEW_INDEPENDENT_IMPLEMENTATION。独立核验代码路径并不代表外部专家审稿。\nStage04A_R3C、Stage04B/R1、Stage04C_A、Stage04C_R1 和 Stage04D_B 的相关源文件已静态读取；未导入其研究入口。\nstat_core_v1.py 是已验收 A-R3C 统计核心的字节一致副本。其 statsmodels GLM 使用显式满秩基类、QR WLS，无 predictor clip、无协方差 pinv。Objective 包含至多一个已解释的初始 IRLS overshoot；后续持续逆向步骤失败，门槛沿冻结规则。\naudit_v1.py 保留全部规定交互项及真实季度；仅规范化冗余 FE。原始源 pandas 重建与独立 stdlib CSV 重建分别核验 NDC/人口/报告配对，source hash 和 30 行 N/N_R1 差异另保存。\n所有目标使用结构 SVD、weighted SVD、全零 FE 及 free-direction 正式 LP。此次所有 MID5.5 模型结局正值，仍实际执行零集合规范化 LP；其约束 0<=-1 不可行，证实没有 Poisson 零结局分离。\n每模型 exposure/zero/tight 三次同规格求解，全 sandwich/CR1/t(G-1)。independent_qa_v1.py 为独立 Newton likelihood 与 einsum/add.at/solve 完整协方差路径，不调用 primary fit/covariance；没有相同函数重复充当独立优化。\nF1/F3 offset 保留，logN 的 ST 空间表示及预测均值等价另验；不能称独立人口控制效应。既有 C-A/A-R3C 保存对象仅校准协方差/输入/推断，不新增第八个研究模型。\n未发现冻结公式冲突。原环境身份仍 NOT_VERIFIABLE；已安装独立 venv 版本核验通过。没有安装、下载、网络访问或协议修改。')
    print('CALIBRATION PASS; zero new research fits', flush=True)
if __name__ == '__main__':
    run()
