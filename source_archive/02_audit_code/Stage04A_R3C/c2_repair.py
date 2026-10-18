"""Repair only failed C2 artificial wrapper test, reuse unchanged passed checks."""
from common import *
record('C2_repair')
md('04A_R3C_C2_Implementation_Note.md', '# C2 实现判定更正\n\n2026-10-13 Asia/Shanghai。先于任何研究输入解析或研究fit固定。\n\n首次C2人工微型wrapper失败及代码原件保留在_working/C2_failed_*与stat_core_C2_failed.py。诊断发现β=log(3)、score=1.37e-16、末五步relative=3.60e-13、原生converged均通过；原生IRLS第一步D14.865376→17.977825，随后下降至4.498681。旧wrapper把任何逆向一步都FAIL，严于Stage03“非finite或未解释持续逆向步”规定。\n\n经独立代码审查采用窄分支EXPLAINED_SINGLE_INITIAL_OVERSHOOT。仅允许唯一实质逆向步位于第一更新，其余步按原1e-10数值级非增；仍保存monotonic_objective=False与正步幅度。中后期或重复逆向、nonfinite仍FAIL。末五步≤1e-10、score≤1e-8、有限均值、原生converged、迭代<1000等全部不变。不是放宽科学容差，不挑选接近原IRR的求解结果。仅重验失败wrapper并新增这一窄分支拒绝控制；其余18项复用原实际通过证据。\n')
import numpy as np
from stat_core import glm_fit, objective_assessment
r = glm_fit(np.array([1.0, 3.0, 2.0, 6.0]), np.ones((4, 1)), np.zeros(4), np.zeros(1), 1e-12)

def clean(v):
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, dict):
        return {k: clean(w) for k, w in v.items()}
    if isinstance(v, list):
        return [clean(w) for w in v]
    return v
jw(WORK / 'C2_solver_micro_repair.json', clean(r))
assert r['solver_gate'] and abs(r['params'][0] - np.log(3)) < 1e-10
assert np.allclose(r['mu'], 3.0, rtol=1e-10) and len(r['history']) >= 6
assert r['last_five_deviance_relative_max'] <= 1e-10
assert not r['monotonic_objective'] and r['objective_explanation'] == 'EXPLAINED_SINGLE_INITIAL_OVERSHOOT'

def obj(dev):
    return objective_assessment([{'deviance': v} for v in dev])
assert obj([4.0, 5.0, 3.0, 2.0])['objective_gate']
assert not obj([4.0, 3.0, 5.0, 2.0])['objective_gate']
assert not obj([4.0, 5.0, 6.0, 2.0])['objective_gate']
assert not obj([4.0, float('nan'), 2.0])['objective_gate']
tests = rc(WORK / 'C2_failed_Test_Results.csv')
for t in tests:
    if t['Test'] == 'audit_solver_history_gate':
        t.update(Status='PASS', Evidence='C2 repair actual beta=log3, score=' + str(r['normalized_score']) + '; 10 native iterations; explained unique first overshoot; prior FAIL preserved')
    else:
        assert t['Status'] == 'PASS'
        t['Evidence'] = 'REUSED_C2_PASS; ' + t['Evidence']
tests.append({'Test': 'objective_exception_rejection_controls', 'Status': 'PASS', 'Evidence': 'unique first only; later/repeated/nonfinite rejected; locked 1e-10 unchanged'})
gate = jr(WORK / 'C2_failed_environment_gate.json')
gate.update(G_ENV='PASS', failed_tests=[], test_count=len(tests), prior_failure_preserved=True, repair_note='04A_R3C_C2_Implementation_Note.md')
cw(OUT / '04A_R3C_Environment_Test_Results.csv', tests)
jw(WORK / 'environment_gate.json', gate)
md('04A_R3C_Environment_Validation.md', f"# C2 软件功能验收\n\n{DATE}。G_ENV=PASS。初次19项中18通过，1项wrapper历史判定失败；该FAIL、代码和完整微型轨迹均保留。只重验失败项并增加异常分支拒绝控制，现在20项均具实际PASS证据，未重复已通过检查。\n\n9个库实际导入位于项目venv。NumPy精确矩阵积、SVD、HiGHS自由负值解、Poisson解析解及offset、解析两簇CR1、rank及free-parameter separation、非法输入/variance均通过。实际wrapperβ=log3、score={r['normalized_score']:.17g}、末五步relative={r['last_five_deviance_relative_max']:.17g}通过。首步overshoot按事先固定的窄分支解释，monotonic=False照实保留。见C2_Implementation_Note；不使用研究数据验收。\n\n安装实际集合=14批准稳定发行包+pip，pip check及freeze通过，wrapt2.0.1。原历史环境身份和启动real-location warning根因仍NOT_VERIFIABLE。环境通过不代表研究数值复现通过。原先240秒安装中断亦保留，resume命令exit0才支持安装成功。\n")
print('G_ENV=PASS; repaired failed artificial test only; original FAIL retained')
