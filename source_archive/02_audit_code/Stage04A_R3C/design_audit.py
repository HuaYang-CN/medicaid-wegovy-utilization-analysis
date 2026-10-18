"""C4 independent exact requested design and certified separation support."""
from common import *
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import traceback
import numpy as np
import pandas as pd
from stat_core import rank_info, target_estimable, separation, validate
from input_audit import keys, f17

def array_hash(a):
    return th(str(a.shape) + '|' + str(a.dtype) + '|' + ','.join((f17(v) for v in a.ravel())))

def main(record_stage='C4_design'):
    assert jr(WORK / 'environment_gate.json')['G_ENV'] == 'PASS' and jr(WORK / 'data_gate.json')['G_DATA'] == 'PASS'
    record(record_stage)
    f = pd.read_csv(safe(WORK / 'requested_input.csv'), float_precision='round_trip')
    h = jr(OUT / '04A_R3C_Model_Input_Hashes.json')
    assert kh(keys(f)) == h['requested_row_order_hash']
    assert kh([k + '|' + '|'.join((f17(r[c]) for c in h['data_fields'])) for k, (_, r) in zip(keys(f), f.iterrows())]) == h['requested_data_hash']
    sb = (f.state + ':' + f.analytic_brand).to_numpy()
    quarter = f.calendar_quarter.to_numpy()
    sc = sorted(set(sb))
    qc = sorted(set(quarter))
    names = ['Intercept'] + ['StateBrand[' + s + ']' for s in sc[1:]] + ['Quarter[' + q + ']' for q in qc[1:]] + ['Post×ObesityBrand', 'Post×Noncoverage', 'DDD']
    X = np.column_stack([np.ones(len(f))] + [(sb == s).astype(float) for s in sc[1:]] + [(quarter == q).astype(float) for q in qc[1:]] + [f.post * f.obesity, f.post * f.noncoverage_2024, f.post * f.obesity * f.noncoverage_2024])
    y = f.rx_mid.to_numpy(float)
    off = f.offset.to_numpy(float)
    cl = f.state.to_numpy(str)
    rk = np.array(keys(f))
    validate(y, X, off)
    assert X.shape == (1012, 105) and sc[0] == 'AK:OZEMPIC' and (qc[0] == '2023Q2')
    info = rank_info(X)
    estimable = target_estimable(X, names.index('DDD'))
    assert estimable, 'DDD absorbed requested'
    h.update(requested_X_hash=array_hash(X), requested_X_names_hash=kh(names), requested_model_input_hash=th(h['requested_data_hash'] + array_hash(X) + kh(names)), column_order=names, reference_state_brand=sc[0], reference_quarter=qc[0], X_serialization='shape|dtype|flatten C order .17g comma')
    np.savez_compressed(target(WORK / 'requested_model.npz'), X=X, y=y, offset=off, clusters=cl, keys=rk, names=np.array(names))
    allzero = f.groupby(['state', 'analytic_brand']).rx_mid.agg(['sum', 'size'])
    az = allzero[allzero['sum'] == 0]
    cw(OUT / '04A_R3C_All_Zero_Groups.csv', az.reset_index().to_dict('records'), ['state', 'analytic_brand', 'sum', 'size'])
    keep = np.ones(len(f), bool)
    columns = np.ones(X.shape[1], bool)
    certs = []
    dropped = []
    rounds = []
    for step in range(10):
        idx = np.flatnonzero(keep)
        ci = np.flatnonzero(columns)
        Xe = X[idx][:, ci]
        ye = y[idx]
        s = separation(Xe, ye)
        rounds.append({'round': step, 'n': len(idx), 'k': len(ci), 'detected': s['detected'], 'status': s['status']})
        if not s['detected']:
            break
        for j, v in zip(ci, s['direction_original']):
            certs.append({'Round': step, 'Column': names[j], 'Direction_original': v, 'Direction_scaled': s['direction_scaled'][list(ci).index(j)], 'Positive_equality_max_abs': s['positive_equality_max_abs'], 'Zero_inequality_max': s['zero_inequality_max'], 'Normalization_sum': s['normalization_sum'], 'LP_status': s['status']})
        np.savez_compressed(target(WORK / f'separation_round_{step}.npz'), direction=s['direction_original'], margins=s['margins'], rows=idx, columns=ci)
        affected = idx[s['affected']]
        assert len(affected) > 0 and (y[affected] == 0).all()
        for i in affected:
            dropped.append({'Requested_row': int(i), 'Row_key': rk[i], 'y': y[i], 'Reason': 'CERTIFIED_SEPARATED_ZERO', 'LP_round': step, 'Margin': s['margins'][list(idx).index(i)]})
        keep[affected] = False
        zero = np.all(X[keep] == 0, axis=0)
        assert not zero[names.index('DDD')]
        columns &= ~zero
    else:
        raise RuntimeError('separation iterative certificate limit')
    idx = np.flatnonzero(keep)
    ci = np.flatnonzero(columns)
    Xe = X[idx][:, ci]
    ye = y[idx]
    oe = off[idx]
    ce = cl[idx]
    ne = [names[i] for i in ci]
    eff = rank_info(Xe)
    target_ok = target_estimable(Xe, ne.index('DDD'))
    assert target_ok and eff['rank'] == len(ne), 'effective support unidentified'
    assert eff['rank_tau_0_1'] == eff['rank'] == eff['rank_tau_10'], 'rank threshold unstable'
    assert not rounds[-1]['detected'] and len(np.unique(ce)) > 1
    np.savez_compressed(target(WORK / 'effective_model.npz'), X=Xe, y=ye, offset=oe, clusters=ce, keys=rk[idx], names=np.array(ne), requested_rows=idx, requested_columns=ci)
    dropped_params = [{'Column': names[j], 'Reason': 'EXACT_ZERO_COLUMN_AFTER_CERTIFIED_ROW_REMOVAL'} for j in np.flatnonzero(~columns)]
    cw(OUT / '04A_R3C_Separated_Rows.csv', dropped, ['Requested_row', 'Row_key', 'y', 'Reason', 'LP_round', 'Margin'])
    cw(OUT / '04A_R3C_Dropped_Parameters.csv', dropped_params, ['Column', 'Reason'])
    cw(OUT / '04A_R3C_Separation_Certificate.csv', certs, ['Round', 'Column', 'Direction_original', 'Direction_scaled', 'Positive_equality_max_abs', 'Zero_inequality_max', 'Normalization_sum', 'LP_status'])
    diag = []
    for label, r in [('REQUESTED', info), ('EFFECTIVE', eff)]:
        for i, v in enumerate(r['spectrum']):
            diag.append({'Sample': label, 'Singular_index': i + 1, 'Singular_value': v, 'n': r['n'], 'k': r['k'], 'Effective_rank': r['rank'], 'Threshold': r['threshold'], 'Rank_tau_0_1': r['rank_tau_0_1'], 'Rank_tau_10': r['rank_tau_10'], 'Condition_identified': r['condition_identified']})
    cw(OUT / '04A_R3C_Rank_Diagnostics.csv', diag)
    records = []
    for label, mask, r in [('REQUESTED', np.ones(len(f), bool), info), ('EFFECTIVE', keep, eff)]:
        a = f.loc[mask]
        records.append({'Sample': label, 'n': len(a), 'G': a.state.nunique(), 'coverage_states': a[a.coverage_2024 == 1].state.nunique(), 'noncoverage_states': a[a.noncoverage_2024 == 1].state.nunique(), 'quarters': a.calendar_quarter.nunique(), 'k': r['k'], 'rank': r['rank'], 'row_key_hash': kh(sorted(keys(a))), 'row_order_hash': kh(keys(a)), 'dropped_rows': int((~mask).sum())})
    cw(OUT / '04A_R3C_Requested_vs_Effective_Sample.csv', records)
    h.update(effective_n=len(idx), effective_G=len(np.unique(ce)), effective_row_key_hash=kh(sorted(rk[idx])), effective_row_order_hash=kh(rk[idx]), effective_sample_hash=kh(sorted(rk[idx])), effective_X_hash=array_hash(Xe), effective_names_hash=kh(ne), effective_data_hash=kh([lines for i, lines in enumerate([k + '|' + '|'.join((f17(r[c]) for c in h['data_fields'])) for k, (_, r) in zip(keys(f), f.iterrows())]) if keep[i]]))
    h['effective_model_input_hash'] = th(h['effective_data_hash'] + h['effective_X_hash'] + h['effective_names_hash'])
    h['requested_full_npz_sha256'] = sha(WORK / 'requested_model.npz')
    h['effective_full_npz_sha256'] = sha(WORK / 'effective_model.npz')
    jw(OUT / '04A_R3C_Model_Input_Hashes.json', h)
    summary = {'G_TARGET': 'PASS', 'requested_rank': info['rank'], 'effective_rank': eff['rank'], 'requested_k': X.shape[1], 'effective_k': Xe.shape[1], 'requested_n': len(y), 'effective_n': len(ye), 'effective_G': len(np.unique(ce)), 'full_finite_FE_MLE': not bool(dropped), 'separated_rows': len(dropped), 'dropped_columns': dropped_params, 'target_estimable_requested': estimable, 'target_estimable_effective': target_ok, 'LP_rounds': rounds, 'sample_scope': 'CERTIFIED_SEPARATION_EFFECTIVE_SUPPORT' if dropped else 'ORIGINAL_REQUESTED_SUPPORT', 'candidate_result_label': 'VALID_EFFECTIVE_SAMPLE_RESULT' if dropped else 'REPRODUCED_ORIGINAL_SPEC', 'candidate_label_requires': 'G_SOLVER/G_COV and locked consistency gates PASS'}
    jw(WORK / 'design_gate.json', summary)
    md('04A_R3C_Design_Matrix_Audit.md', f"# C4 DDD矩阵\n\n原样规范化，Intercept、字符串排序state:brand虚拟项、quarter虚拟项、Post×ObesityBrand、Post×Noncoverage、DDD。参考{sc[0]}与{qc[0]}，post从2024Q2，2024Q1保留pre。产品/组/组×产品固定项由state-product FE吸收，post由季度FE吸收；时间变动下阶项完整包含。无额外权重，仅log季度月均Medicaid offset。列次序与X数值hash公开。\n\n请求n1012、名义k105、实际rank{info['rank']}；effective n{len(ye)}、k{len(ne)}、rank{eff['rank']}、G{len(np.unique(ce))}。两者采用列尺度c=max(1,maxabsX)、SVD tau=max(n,k)eps*smax，0.1/10tau敏感及谱均保存。DDD删除列后rank递减1，目标在两支持上可估；G_TARGET=PASS。完整rank不保证有限MLE。\n\n仅删除正式LP证书确定的{len(dropped)}个零观察；随之{len(dropped_params)}个精确零列代数删除，参数理由与名单公开。不是修正missing源、选择显著模型或删除AK全州；effective仍有AK-Ozempic。研究模型尚未fit。\n")
    md('04A_R3C_Separation_Diagnostics.md', f'# 正式PPML分离\n\n请求支持全零state-product组见All_Zero_Groups。LP使用FREE d、Xpositive d=0、Xzero d≤0、sum Xzero d≤−1，HiGHS primal/dual1e-9；证书核验残差≤1e-8。列尺度与rank尺度相同；方向、正支撑最大绝对残差、零约束最大值、normalization sum见Certificate，全行margin本地保存。\n\n迭代记录{rounds}。正式证书删除{len(dropped)}零观察，末轮不可行证明当前有限样本未检出分离。完整FE有限MLE存在={not bool(dropped)}。AK-Wegovy旧缺源全零FE可趋−∞，完整1012行不能标有限MLE复现；DDD是否有效仍须G_SOLVER/G_COV，不直接否定或认可原4.09。\n\n仅将margin<−1e-8的零行作为certified separated；逐行key/原因/hash和保留州簇见Separated_Rows及Requested_vs_Effective_Sample。无clip、无pinv、未变原源零/RI/抑制/渠道/政策设定。\n')
    print(summary)
if __name__ == '__main__':
    try:
        main('C4_design_repair')
    except Exception:
        target(WORK / 'C4_failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        jw(WORK / 'design_gate_failure.json', {'G_TARGET': 'FAIL', 'error': 'see C4_failure.txt'})
        raise
