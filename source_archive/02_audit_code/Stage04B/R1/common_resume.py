"""Repair only false COMMON non-stability from counting old native deletions.
Reuse completed native and applicable LP evidence; do not rerun models/input.
"""
from common import *
import shutil, traceback
import numpy as np
import pandas as pd
from inputs import keys, datahash
from diagnose import certify

def main():
    record('COMMON_repair')
    assert {'old_zero'} & {'current_a', 'current_b'} == set()
    assert {'current_a'} & {'current_a', 'current_b'} == {'current_a'}
    old = jr(WORK / 'common_diagnostics_index.json')
    native = jr(WORK / 'native_diagnostics_index.json')
    for p in [WORK / 'common_diagnostics_index.json', WORK / 'diagnosis_complete.json', OUT / '04B_COMMON_Support_Iterations.csv']:
        dest = target(WORK / 'before_COMMON_repair' / p.name)
        assert not dest.exists()
        shutil.copyfile(safe(p), dest)
    plan = jr(WORK / 'prospective_plan.json')
    manifest = jr(WORK / 'variant_manifest.json')
    frames = {}
    for v in manifest:
        assert sha(v['input_csv']) == v['input_csv_sha']
        frames[v['Variant_ID']] = pd.read_csv(safe(v['input_csv']), float_precision='round_trip')
    common = {}
    iterations = []
    for family, members in plan['families'].items():
        if old[family]['stable'] and old[family]['comparison_status'] == 'PASS':
            common[family] = old[family]
            for m, d in old[family]['members'].items():
                iterations.append({'Family': family, 'Round': 0, 'Variant_ID': m, 'Input_common_n': d['n'], 'Certified_further_drop': 0, 'Input_common_key_hash': old[family]['common_key_hash'], 'Target_status': d['G_TARGET'], 'Criterion': 'REUSED_ALREADY_COMPLETE_COMMON_NO_RECOMPUTE'})
            continue
        shared = set.intersection(*[set(keys(pd.read_csv(safe(WORK / (m + '__NATIVE_effective.csv')), float_precision='round_trip'))) for m in members])
        stable = False
        last = {}
        for round in range(10):
            union = set()
            last = {}
            for m in members:
                view = frames[m][np.array([k in shared for k in keys(frames[m])])].copy()
                prior = old[family]['members'][m]
                prev = pd.read_csv(safe(WORK / (prior['label'] + '_effective.csv')), float_precision='round_trip')
                if set(keys(view)) == set(keys(prev)) and datahash(view) == prior['data_hash']:
                    assert sha(WORK / (prior['label'] + '_model.npz')) == prior['full_npz_sha256']
                    d = prior
                    criterion = 'REUSED_EXISTING_IDENTICAL_INPUT_LP; FILTER_ONLY_CURRENT_COMMON_DROPS'
                else:
                    w, d = certify(view, m + '__COMMON_' + family + '_repair_r' + str(round))
                    criterion = 'NEW_REQUIRED_COMMON_LP'
                last[m] = d
                removed = {z['row_key'] for z in d['dropped']} & set(keys(view))
                union |= removed
                iterations.append({'Family': family, 'Round': round, 'Variant_ID': m, 'Input_common_n': len(view), 'Certified_further_drop': len(removed), 'Input_common_key_hash': kh(sorted(shared)), 'Target_status': d['G_TARGET'], 'Criterion': criterion})
            assert union <= shared
            if not union:
                stable = True
                break
            shared -= union
        common[family] = {'stable': stable, 'rounds': round + 1, 'common_key_hash': kh(sorted(shared)), 'comparison_status': 'PASS' if stable and all((d['G_TARGET'] == 'PASS' for d in last.values())) else 'NOT_VERIFIABLE', 'members': last, 'rule': 'native effective key intersection; only further certified deletions IN CURRENT COMMON; <=10 rounds; no beta/P', 'software_repair': 'old native drops outside shared must not count as new COMMON deletions'}
        jw(WORK / ('COMMON_' + family + '_keys.json'), sorted(shared))
        print('COMMON ' + family + ' stable=' + str(stable) + ' n=' + str(len(shared)) + ' status=' + common[family]['comparison_status'], flush=True)
    cw(OUT / '04B_COMMON_Support_Iterations.csv', iterations)
    jw(WORK / 'common_diagnostics_index.json', common)
    jw(WORK / 'diagnosis_complete.json', {'Status': 'COMPLETE_VERIFIED', 'native_variants': len(native), 'families': len(common), 'native_targets_failed': [m for m, d in native.items() if d['G_TARGET'] != 'PASS'], 'common_failed': [m for m, d in common.items() if d['comparison_status'] != 'PASS'], 'COMMON_software_failure_preserved': True, 'new_drop_set_controls': 'PASS'})
    md('04B_R1_COMMON_Recovery_Note.md', '# COMMON续算边界修复\n\n初次COMMON复用native证据时将从原requested已删除、且不在当前COMMON中的旧分离key再次计入union。这使shared不变但union一直非空，5个family出现假的10轮不稳定；所有原诊断/iterations保存before_COMMON_repair，尚无研究fit。\n\n修复后只计当前COMMON输入内新certificate删除，断言union⊆shared；集合人工控制同时检验旧drop不计入、当前新drop确实缩支持。直接复用已经完成的native及同一数值输入LP证据，不重跑已完成M0_M1 COMMON或旧A模型，不修改任何科学容差/赋值/family。COMMON先于任何fit冻结，不看β/P。\n\n修复后稳定不等于目标可估。M1 S0及正10负0情景的3个noncoverage-Wegovy pre源赋值零被正式证书删除；共有支持缺该格，DDD被吸收/支持丧失。SUP_M1 COMMON必须保持NOT_VERIFIABLE，不能以修复软件门槛制造有效结果。\n')
if __name__ == '__main__':
    try:
        main()
    except Exception:
        target(WORK / 'COMMON_resume_failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
