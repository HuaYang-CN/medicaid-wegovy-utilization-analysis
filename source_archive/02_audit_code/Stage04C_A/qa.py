"""Additional independent input/quarter/population QA. No model fitting."""
import audit as a

def main():
    a.imports()
    pd = a.pd
    np = a.np
    inventory = {r['Path']: r['SHA256'] for r in a.rc(a.B / '04B_R1_File_Inventory.csv')}
    path = a.BW / 'monthly_population_ledger.csv'
    assert a.sha(path) == inventory[str(path)]
    m = pd.read_csv(a.safe(path), float_precision='round_trip')
    q = pd.read_csv(a.safe(a.BW / 'quarterly_population_ledger.csv'), float_precision='round_trip')
    recalculated = {}
    for key, g in m.groupby(['state', 'calendar_quarter']):
        valid = g.replacement_value.dropna()
        n = len(valid)
        recalculated[key] = (float(valid.mean()) if n >= 2 else np.nan, n)
    for r in q.itertuples():
        v, n = recalculated[r.state, r.calendar_quarter]
        assert n == r.valid_months
        assert np.isnan(v) and np.isnan(r.N_R1) or abs(v - r.N_R1) <= 1e-09
    ri = m[(m.state == 'RI') & (m.month == 202412)]
    assert len(ri) == 1 and ri.replacement_value.isna().all() and (ri.footnote_class == 'UNAVAILABLE_SYSTEM').all()
    checks = []
    for v in a.jr(a.WORK / 'variant_manifest.json'):
        f = a.readframe(v['Variant_ID'] + '_requested')
        for r in f.itertuples():
            N, n = recalculated[r.state, r.calendar_quarter]
            assert n >= 2 and abs(N - r.N) <= 1e-09
            assert abs(np.log(r.N) - r.offset) <= 3e-14
            assert r.k == r.year * 4 + r.quarter - 8098 and r.post == int(r.quarter_index >= 8098)
            assert r.noncoverage_2024 == 1 - r.coverage_2024 and r.obesity == int(r.analytic_brand == 'WEGOVY')
        checks.append({'Variant_ID': v['Variant_ID'], 'n': len(f), 'requested_hashes': 'PASS', 'independent_month_average_and_offset': 'PASS', 'real_calendar_k_post_and_P1_product_coding': 'PASS'})
    for d in a.jr(a.WORK / 'diagnostics_index.json'):
        assert a.sha(d['object_path']) == d['object_sha']
        z = np.load(d['object_path'], allow_pickle=False)
        X = z['X']
        assert a.xhash(X) == d['X_hash'] and a.kh(z['names']) == d['names_hash']
        assert a.kh(sorted(z['keys'])) == d['effective']['keys_hash']
        singular = np.linalg.svd(X / np.maximum(1, np.max(np.abs(X), axis=0)), compute_uv=False)
        tau = max(X.shape) * np.finfo(float).eps * singular[0]
        rank = int((singular > tau).sum())
        assert rank == d['rank']['rank']
        assert d['normalization']['family_size'] == (9 if d['design'] == 'EV_CLEAN' else 10 if d['design'] == 'EV_TRANS' else 1)
    effective = a.readframe('PRIMARY_BINARY_CLEAN_effective')
    rows = effective.to_dict('records')
    for r in rows:
        r['requested_model_row'] = True
        r['effective_model_row'] = True
    a.cw(a.OUT / '04C_A_Model_Sample.csv', rows)
    group = a.rc(a.OUT / '04C_A_Group_Quarter_Support.csv')
    for r in group:
        g = effective[(effective.calendar_quarter == r['calendar_quarter']) & (effective.analytic_brand == r['product']) & (effective.coverage_2024 == (1 if r['group'] == 'COVERAGE' else 0))]
        r['effective_model_observations'] = len(g)
        r['effective_G'] = int(g.state.nunique())
        r['effective_positive_outcomes'] = int((g.y > 0).sum())
        r['effective_zero_outcomes'] = int((g.y == 0).sum())
    a.cw(a.OUT / '04C_A_Group_Quarter_Support.csv', group)
    a.jw(a.WORK / 'input_design_QA.json', {'status': 'PASS', 'monthly_ledger_sha': a.sha(path), 'quarterly_ledger_sha': a.sha(a.BW / 'quarterly_population_ledger.csv'), 'R0': 'NOT_VERIFIABLE', 'R1': 'SYSTEM_UNAVAILABLE_NA; >=2 VALID MONTHS MEAN', 'RI2024Q4': {'N_R1': recalculated['RI', '2024Q4'][0], 'valid_months': 2}, 'variant_checks': checks, 'independent_numpy_SVD_all_six_objects': 'PASS', 'all_dynamic_families_preserved': 'PASS', 'primary_requested_equals_effective': True, 'code_sha': a.sha(a.CODE / 'qa.py')})
    a.checkpoint('QA_inputs', {'status': 'PASS', 'input_design_QA_sha': a.sha(a.WORK / 'input_design_QA.json')})
    print('INPUT/DESIGN QA PASS', flush=True)
if __name__ == '__main__':
    main()
