"""Preserve a diagnosed floating serialization mismatch; restore exact baseline
and keep unchanged population quarters byte-identical before new research fits.
No old or new model fit, no source/ledger/scenario recomputation.
"""
from common import *
import shutil
import numpy as np
import pandas as pd
from inputs import keys, datahash
record('baseline_input_repair')
error = jr(WORK / 'baseline_input_alignment.json')
assert error['y_exact_match'] and error['requested_key_match'] and (not error['offset_exact_match'])
assert error['max_offset_abs_difference'] <= 1e-12
ah = jr(A / '04A_R3C_Model_Input_Hashes.json')
ap = A / '_working/requested_input.csv'
af = pd.read_csv(safe(ap), float_precision='round_trip')
assert kh(keys(af)) == ah['requested_row_order_hash']
assert kh([k + '|' + '|'.join((f17(r[c]) for c in ah['data_fields'])) for k, (_, r) in zip(keys(af), af.iterrows())]) == ah['requested_data_hash']
old = jr(WORK / 'variant_manifest.json')
back = WORK / 'before_baseline_repair'
for p in [WORK / 'variant_manifest.json', WORK / 'input_gate.json', WORK / 'baseline_input_alignment.json', CODE / 'diagnose.py', CODE / 'inputs.py']:
    dest = target(back / p.name)
    assert not dest.exists()
    shutil.copyfile(safe(p), dest)
for p in WORK.glob('R3_M0_MID__NATIVE*'):
    dest = target(back / p.name)
    assert not dest.exists()
    shutil.copyfile(safe(p), dest)
lookup = {k: (r.medicaid_enrollment, r.offset) for k, r in zip(keys(af), af.itertuples())}
for v in old:
    p = Path(v['input_csv'])
    dest = target(back / p.name)
    assert not dest.exists()
    shutil.copyfile(safe(p), dest)
    f = pd.read_csv(safe(p), float_precision='round_trip')
    baselineN = np.array([lookup[k][0] for k in keys(f)])
    baselineOff = np.array([lookup[k][1] for k in keys(f)])
    if v['R'] == 'R3':
        f['N'] = baselineN
        f['offset'] = baselineOff
    else:
        unchanged = (f.valid_months == f.raw_months).to_numpy()
        f.loc[unchanged, 'N'] = baselineN[unchanged]
        f['offset'] = np.log(f.N)
        sameN = f.N.to_numpy() == baselineN
        f.loc[sameN, 'offset'] = baselineOff[sameN]
    f.to_csv(target(p), index=False, float_format='%.17g')
    v['input_csv_sha'] = sha(p)
    v['requested_data_hash'] = datahash(f)
    v['numeric_preservation'] = 'exact archived historical N/offset on unchanged quarters; only unavailable-month quarters recomputed under R1'
jw(WORK / 'variant_manifest.json', old)
gate = jr(WORK / 'input_gate.json')
gate['variant_manifest_sha'] = sha(WORK / 'variant_manifest.json')
gate['baseline_serialization_repair'] = 'documented; inputs/source/scenarios/math rules unchanged'
jw(WORK / 'input_gate.json', gate)
protect = jr(WORK / 'protected_before.json')
protect.append({'path': str(ap), 'sha256': sha(ap)})
jw(WORK / 'protected_before.json', protect)
md('04B_R1_Baseline_Serialization_Note.md', '# 原基准精确复用及人口组件隔离\n\n首次新增input将所有历史季度均值重新进行浮点序列化，原R3基准y/key相同但offset最大差1.7763568394002505e-15；严格array对齐门槛阻止复用，未运行研究fit。原失败日志、代码和14个派生输入均保留before_baseline_repair。\n\n修复只恢复Stage04A已冻结requested_input中精确N/offset；先重验该文件原数值17g hash及keys。R3直接沿用它；R1/R2/partial只对存在不可用月的季度重算，其他季度保留旧字段的精确数值，避免浮点序列化被错误归为人口修正效果。所有source/NDC/人口ledger、R/M/S科学规则和预设family不变。RI R1仍使用两个有效月平均，非官方R0；原字段不写回。没有重新计算旧A模型或选择接近4.09的参数。\n\n正式诊断接续将直接复用A分离证书与有效模型档案，不重复已验证的基准LP计算。新增情景各自仍正式诊断和完整求解验收。\n')
print('exact baseline input restored; unavailable-quarter-only component change; no fits')
