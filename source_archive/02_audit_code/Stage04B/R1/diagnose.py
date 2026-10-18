"""Before any new research fit, freeze native and COMMON certified support."""
from common import *
import traceback, shutil
import numpy as np
import pandas as pd
from stat_core import rank_info, target_estimable, separation, validate
from inputs import keys, datahash, QUARTERS, COVER

def xhash(X):
    return th(str(X.shape) + '|' + str(X.dtype) + '|' + ','.join((f17(v) for v in X.ravel())))

def build(f):
    sb = (f.state + ':' + f.analytic_brand).to_numpy()
    qs = f.calendar_quarter.to_numpy()
    sc = sorted(set(sb))
    qc = sorted(set(qs))
    assert sc and qc
    names = ['Intercept'] + ['StateBrand[' + s + ']' for s in sc[1:]] + ['Quarter[' + q + ']' for q in qc[1:]] + ['Post×ObesityBrand', 'Post×Noncoverage', 'DDD']
    X = np.column_stack([np.ones(len(f))] + [(sb == s).astype(float) for s in sc[1:]] + [(qs == q).astype(float) for q in qc[1:]] + [(f.post * f.obesity).to_numpy(float), (f.post * f.noncoverage_2024).to_numpy(float), (f.post * f.obesity * f.noncoverage_2024).to_numpy(float)])
    return (X, names, {'reference_state_brand': sc[0], 'reference_quarter': qc[0]})

def smallrank(r):
    return {k: v for k, v in r.items() if k not in {'scale', 'spectrum'}}

def reused_A(f, label):
    ah = jr(A / '04A_R3C_Model_Input_Hashes.json')
    ar = np.load(safe(A / '_working/requested_model.npz'))
    ae = np.load(safe(A / '_working/effective_model.npz'))
    assert sha(A / '_working/requested_model.npz') == ah['requested_full_npz_sha256'] and sha(A / '_working/effective_model.npz') == ah['effective_full_npz_sha256']
    X, names, ref = build(f)
    aligned = {'y_exact_match': np.array_equal(f.y.to_numpy(float), ar['y']), 'offset_exact_match': np.array_equal(f.offset.to_numpy(float), ar['offset']), 'requested_key_match': np.array_equal(np.array(keys(f)), ar['keys']), 'requested_X_names_clusters_match': np.array_equal(X, ar['X']) and names == ar['names'].tolist() and np.array_equal(f.state.to_numpy(str), ar['clusters'])}
    assert all(aligned.values()), 'baseline full input differs; do not reuse'
    w = f[np.array([k in set(ae['keys']) for k in keys(f)])].copy()
    Xe, ne, nref = build(w)
    aligned['effective_hash_match'] = kh(sorted(keys(w))) == ah['effective_sample_hash']
    aligned['effective_X_names_clusters_match'] = np.array_equal(Xe, ae['X']) and ne == ae['names'].tolist() and np.array_equal(w.state.to_numpy(str), ae['clusters'])
    assert all(aligned.values()) and datahash(w) == ah['effective_data_hash']
    jw(WORK / 'baseline_input_alignment_verified.json', aligned)
    p = target(WORK / (label + '_effective.csv'))
    w.to_csv(p, index=False, float_format='%.17g')
    shutil.copyfile(safe(A / '_working/effective_model.npz'), target(WORK / (label + '_model.npz')))
    rr = next((r for r in rc(A / '04A_R3C_Rank_Diagnostics.csv') if r['Sample'] == 'EFFECTIVE'))
    rank = {'n': 1001, 'k': 104, 'rank': 104, 'threshold': float(rr['Threshold']), 'rank_tau_0_1': int(rr['Rank_tau_0_1']), 'rank_tau_10': int(rr['Rank_tau_10']), 'condition_identified': float(rr['Condition_identified'])}
    support = w.groupby(['coverage_2024', 'obesity', 'post']).agg(n=('y', 'size'), positive_y=('y', lambda z: int((z > 0).sum())), states=('state', 'nunique')).reset_index()
    ag = jr(A / '_working/design_gate.json')
    assert ag['G_TARGET'] == 'PASS'
    d = {'label': label, 'n': 1001, 'G': 46, 'coverage_G': 12, 'noncoverage_G': 34, 'rank': rank, 'target_estimable': True, 'G_TARGET': 'PASS', 'row_key_hash': ah['effective_sample_hash'], 'row_order_hash': kh(keys(w)), 'data_hash': datahash(w), 'X_hash': xhash(Xe), 'names_hash': kh(ne), 'model_input_hash': th(datahash(w) + xhash(Xe) + kh(ne)), 'full_npz_sha256': sha(WORK / (label + '_model.npz')), 'effective_csv_sha256': sha(p), 'normalization': nref, 'LP_rounds': ag['LP_rounds'], 'dropped': [{'row_key': r['Row_key'], 'round': int(r['LP_round']), 'reason': r['Reason'], 'margin': float(r['Margin'])} for r in rc(A / '04A_R3C_Separated_Rows.csv')], 'support': support.to_dict('records'), 'condition_caution': False, 'group_cluster_caution': False, 'verification': 'REUSED_COMPLETE_A_CERTIFICATE_ARCHIVE; NO_NEW_BASELINE_LP_OR_FIT'}
    assert d['model_input_hash'] == ah['effective_model_input_hash']
    jw(WORK / (label + '_diagnostics.json'), d)
    return (w, d)

def certify(f, label):
    assert f.index.is_unique and len(keys(f)) == len(set(keys(f)))
    work = f.copy()
    rounds = []
    certrows = []
    dropped = []
    for round in range(10):
        X, names, ref = build(work)
        y = work.y.to_numpy(float)
        validate(y, X, work.offset.to_numpy(float))
        r = rank_info(X)
        s = separation(X, y)
        rounds.append({'round': round, 'n': len(work), 'k': X.shape[1], 'rank': r['rank'], 'LP_status': s['status'], 'detected': s['detected']})
        if not s['detected']:
            break
        np.savez_compressed(target(WORK / (label + f'_LP{round}.npz')), direction=s['direction_original'], margins=s['margins'], keys=np.array(keys(work)), names=np.array(names))
        for name, ds, do in zip(names, s['direction_scaled'], s['direction_original']):
            certrows.append({'Run_support': label, 'Round': round, 'Column': name, 'Direction_original': do, 'Direction_scaled': ds, 'Positive_equality_max_abs': s['positive_equality_max_abs'], 'Zero_inequality_max': s['zero_inequality_max'], 'Normalization_sum': s['normalization_sum']})
        affected = work.index[s['affected']]
        assert len(affected) > 0 and (work.loc[affected, 'y'] == 0).all()
        for ix in affected:
            dropped.append({'row_key': keys(work.loc[[ix]])[0], 'round': round, 'reason': 'CERTIFIED_SEPARATED_ZERO', 'margin': float(s['margins'][list(work.index).index(ix)])})
        work = work.drop(index=affected)
        if len(work) == 0:
            raise RuntimeError('all support separated')
    else:
        raise RuntimeError('native separation did not stabilize within10')
    X, names, ref = build(work)
    r = rank_info(X)
    target_ok = target_estimable(X, names.index('DDD'))
    support = work.groupby(['coverage_2024', 'obesity', 'post']).agg(n=('y', 'size'), positive_y=('y', lambda z: int((z > 0).sum())), states=('state', 'nunique')).reset_index()
    coverageG = work[work.coverage_2024 == 1].state.nunique()
    noncoverageG = work[work.coverage_2024 == 0].state.nunique()
    target_ok = bool(target_ok and len(support) == 8 and (coverageG >= 2) and (noncoverageG >= 2) and (r['rank'] == X.shape[1]) and (r['rank'] == r['rank_tau_0_1'] == r['rank_tau_10']))
    p = target(WORK / (label + '_effective.csv'))
    work.to_csv(p, index=False, float_format='%.17g')
    np.savez_compressed(target(WORK / (label + '_model.npz')), X=X, y=work.y.to_numpy(float), offset=work.offset.to_numpy(float), clusters=work.state.to_numpy(str), keys=np.array(keys(work)), names=np.array(names))
    summary = {'label': label, 'n': len(work), 'G': work.state.nunique(), 'coverage_G': work[work.coverage_2024 == 1].state.nunique(), 'noncoverage_G': work[work.coverage_2024 == 0].state.nunique(), 'rank': smallrank(r), 'target_estimable': target_ok, 'G_TARGET': 'PASS' if target_ok else 'FAIL', 'row_key_hash': kh(sorted(keys(work))), 'row_order_hash': kh(keys(work)), 'data_hash': datahash(work), 'X_hash': xhash(X), 'names_hash': kh(names), 'model_input_hash': th(datahash(work) + xhash(X) + kh(names)), 'full_npz_sha256': sha(WORK / (label + '_model.npz')), 'effective_csv_sha256': sha(p), 'normalization': ref, 'LP_rounds': rounds, 'dropped': dropped, 'support': support.to_dict('records'), 'condition_caution': r['condition_identified'] > 1000000000000.0, 'group_cluster_caution': bool(work[work.coverage_2024 == 1].state.nunique() < 10 or work[work.coverage_2024 == 0].state.nunique() < 10)}
    np.savez_compressed(target(WORK / (label + '_rank.npz')), spectrum=r['spectrum'], scale=r['scale'])
    jw(WORK / (label + '_diagnostics.json'), summary)
    cw(WORK / (label + '_certificate.csv'), certrows, ['Run_support', 'Round', 'Column', 'Direction_original', 'Direction_scaled', 'Positive_equality_max_abs', 'Zero_inequality_max', 'Normalization_sum'])
    return (work, summary)

def main():
    assert jr(WORK / 'environment_gate.json')['G_ENV'] == 'PASS' and jr(WORK / 'input_gate.json')['G_DATA'] == 'PASS'
    record('diagnose_resume')
    manifest = jr(WORK / 'variant_manifest.json')
    frames = {}
    native = {}
    for v in manifest:
        assert sha(v['input_csv']) == v['input_csv_sha']
        f = pd.read_csv(safe(v['input_csv']), float_precision='round_trip')
        assert datahash(f) == v['requested_data_hash'] and kh(keys(f)) == v['requested_order_hash']
        frames[v['Variant_ID']] = f
        work, d = reused_A(f, v['Variant_ID'] + '__NATIVE') if v['reuse_baseline'] else certify(f, v['Variant_ID'] + '__NATIVE')
        native[v['Variant_ID']] = d
        print(v['Variant_ID'] + ' native n=' + str(d['n']) + ' G=' + str(d['G']) + ' target=' + d['G_TARGET'], flush=True)
    jw(WORK / 'native_diagnostics_index.json', native)
    plan = jr(WORK / 'prospective_plan.json')
    common = {}
    iterations = []
    for family, members in plan['families'].items():
        keysets = [set(keys(pd.read_csv(safe(WORK / (m + '__NATIVE_effective.csv')), float_precision='round_trip'))) for m in members]
        shared = set.intersection(*keysets)
        stable = False
        last = {}
        for round in range(10):
            union = set()
            last = {}
            for m in members:
                f = frames[m]
                view = f[np.array([k in shared for k in keys(f)])].copy()
                if len(view) == 0:
                    raise RuntimeError('empty COMMON ' + family)
                if set(keys(view)) == set(keys(pd.read_csv(safe(WORK / (m + '__NATIVE_effective.csv')), float_precision='round_trip'))):
                    d = native[m]
                    assert datahash(view) == d['data_hash']
                else:
                    w, d = certify(view, m + '__COMMON_' + family + '_r' + str(round))
                last[m] = d
                removed = {z['row_key'] for z in d['dropped']} & set(keys(view))
                union |= removed
                iterations.append({'Family': family, 'Round': round, 'Variant_ID': m, 'Input_common_n': len(view), 'Certified_further_drop': len(removed), 'Input_common_key_hash': kh(sorted(shared)), 'Target_status': d['G_TARGET'], 'Criterion': 'ONLY_INTERSECTION_AND_LP_CERTIFICATE'})
            assert union <= shared, 'only current COMMON keys can be further deleted'
            if not union:
                stable = True
                break
            shared -= union
        common[family] = {'stable': stable, 'rounds': round + 1, 'common_key_hash': kh(sorted(shared)), 'comparison_status': 'PASS' if stable and all((d['G_TARGET'] == 'PASS' for d in last.values())) else 'NOT_VERIFIABLE', 'members': last, 'rule': 'intersection native effective keys + further LP certificate deletion union; <=10 rounds; no beta or P'}
        jw(WORK / ('COMMON_' + family + '_keys.json'), sorted(shared))
        print('COMMON ' + family + ' stable=' + str(stable) + ' n=' + str(len(shared)) + ' status=' + common[family]['comparison_status'], flush=True)
    cw(OUT / '04B_COMMON_Support_Iterations.csv', iterations)
    jw(WORK / 'common_diagnostics_index.json', common)
    jw(WORK / 'diagnosis_complete.json', {'Status': 'COMPLETE_VERIFIED', 'native_variants': len(native), 'families': len(common), 'native_targets_failed': [m for m, d in native.items() if d['G_TARGET'] != 'PASS'], 'common_failed': [m for m, d in common.items() if d['comparison_status'] != 'PASS'], 'comparison_status_not_success_proof': 'fitting/solver/covariance still not executed'})
if __name__ == '__main__':
    try:
        main()
    except Exception:
        target(WORK / 'diagnose_failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
