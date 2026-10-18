"""Newly authorized 04B source-level scenarios and R/M input ledgers."""
from common import *
import importlib, importlib.metadata as im, subprocess, traceback
import numpy as np
import pandas as pd
from stat_core import glm_fit, covariance, separation
STATES = set('AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())
COVER = set('CA DE KS MA MI MN MS NH PA RI VA WI'.split())
CHANGERS = set('MO SC TN UT NC'.split())
STABLE = STATES - CHANGERS
QUARTERS = [f'{y}Q{q}' for y in range(2023, 2026) for q in range(1, 5) if (y, q) >= (2023, 2)]

def keys(f):
    return (f.state.astype(str) + '|' + f.calendar_quarter.astype(str) + '|' + f.analytic_brand.astype(str)).tolist()

def datahash(f):
    cols = ['y', 'N', 'offset', 'coverage_2024', 'noncoverage_2024', 'obesity', 'post', 'quarter_index']
    return kh([k + '|' + '|'.join((f17(r[c]) for c in cols)) for k, (_, r) in zip(keys(f), f.iterrows())])

def environment():
    old = jr(A / '_working/environment_gate.json')
    assert old['G_ENV'] == 'PASS'
    assert sha(CODE / 'stat_core.py') == sha(ACODE / 'stat_core.py')
    installed = {d.metadata['Name'].lower().replace('_', '-'): d.version for d in im.distributions()}
    assert installed == old['installed'] and sys.version_info[:3] == (3, 13, 5) and (Path(sys.prefix) == VENV) and (sys.prefix != sys.base_prefix)
    assert 'include-system-site-packages = false' in safe(VENV / 'pyvenv.cfg').read_text(encoding='utf-8').lower()
    imports = {}
    for m in ['numpy', 'pandas', 'scipy', 'statsmodels.api', 'patsy', 'packaging', 'dateutil', 'formulaic', 'wrapt']:
        mod = importlib.import_module(m)
        assert Path(mod.__file__).is_relative_to(VENV)
        imports[m] = str(mod.__file__)
    r = subprocess.run([str(PY), '-I', '-B', '-m', 'pip', '--isolated', '--disable-pip-version-check', 'check'], capture_output=True, text=True)
    target(WORK / 'pip_check.log').write_text(r.stdout + r.stderr, encoding='utf-8')
    assert r.returncode == 0
    y = np.array([1.0, 3.0, 2.0, 6.0])
    X = np.ones((4, 1))
    g = glm_fit(y, X, np.zeros(4), np.zeros(1), 1e-12)
    assert g['solver_gate'] and abs(g['params'][0] - np.log(3)) < 1e-10
    c = covariance(X, y, np.full(4, 3.0), np.array(['a', 'a', 'b', 'b']))
    assert c['covariance_gate'] and abs(c['V'][0, 0] - 1 / 9) < 1e-12
    assert separation(np.eye(2), np.array([2.0, 0.0]))['detected']
    jw(WORK / 'environment_gate.json', {'G_ENV': 'PASS', 'installed': installed, 'imports': imports, 'pip_check_exit': r.returncode, 'stat_core_sha256': sha(CODE / 'stat_core.py'), 'prior_04A_gate': 'REUSED_VERIFIED_NO_MODEL_RERUN', 'new_artificial_API_checks': 'PASS', 'original_environment_identity': 'NOT_VERIFIABLE', 'startup_real_location_warning_root_cause': 'NOT_VERIFIABLE'})

def main():
    record('inputs')
    environment()
    for r in jr(WORK / 'protected_before.json'):
        assert sha(r['path']) == r['sha256']
    source_index = rc(ROOT / '03_audit_outputs/Stage02/02_Source_File_Register.csv')
    population_index = [r for r in source_index if 'enrollment' in r['Relative_Path'].lower()]
    jw(WORK / 'R0_source_search.json', {'indexed_population_candidates': population_index, 'R0': 'NOT_VERIFIABLE_NO_INDEXED_SAME_DEFINITION_OFFICIAL_RI_REVISION', 'scope': 'frozen source registry only; no network or directory expansion'})
    panel = pd.read_csv(safe(SRC / 'processed/state_quarter_brand.csv'))
    f = panel[panel.state.isin(STABLE) & panel.analytic_brand.isin(['WEGOVY', 'OZEMPIC']) & (panel.quarter_index >= 2023 * 4 + 2)].copy()
    assert len(f) == 1012 and (not f.duplicated(['state', 'calendar_quarter', 'analytic_brand']).any())
    assert set(f.calendar_quarter) == set(QUARTERS) and (f.quarter_index == f.year * 4 + f.quarter).all()
    assert (f.coverage_2024 == f.state.isin(COVER).astype(int)).all() and (f.noncoverage_2024 == 1 - f.coverage_2024).all()
    assert f.drop_duplicates('state').coverage_2024.sum() == 12 and f.state.nunique() == 46
    f['obesity'] = (f.analytic_brand == 'WEGOVY').astype(int)
    f['post'] = (f.quarter_index >= 2024 * 4 + 2).astype(int)
    ah = jr(A / '04A_R3C_Model_Input_Hashes.json')
    assert kh(keys(f)) == ah['requested_row_order_hash']
    e = pd.read_csv(safe(SRC / 'raw/enrollment/cms_monthly_enrollment_2019_2025.csv'), dtype=str, keep_default_na=False)
    e = e[(e.preliminary_or_updated == 'U') & (e.final_report == 'Y') & e.state_abbreviation.isin(STATES)].copy()
    assert not e.duplicated(['state_abbreviation', 'reporting_period']).any()
    e['raw_value'] = pd.to_numeric(e.total_medicaid_enrollment, errors='coerce')
    note = e.total_medicaid_enrollment__footnotes.str.strip()
    e['footnote_class'] = 'NONE_OR_OTHER_DOCUMENTED'
    e.loc[note.eq('Unable to Provide Data due to System Limitations'), 'footnote_class'] = 'UNAVAILABLE_SYSTEM'
    e.loc[note.str.contains('Does Not Include All Full-Benefit', regex=False), 'footnote_class'] = 'PARTIAL_POPULATION'
    e.loc[note.eq('Includes Limited-Benefit Enrollees'), 'footnote_class'] = 'LIMITED_BENEFIT_SCOPE'
    e.loc[note.str.contains('Any Time in Month', regex=False), 'footnote_class'] = 'ANYTIME_TIME_SCOPE'
    e.loc[note.eq('Includes Retroactive Enrollments'), 'footnote_class'] = 'RETROACTIVE_RETAINED'
    e['valid'] = np.isfinite(e.raw_value) & (e.raw_value >= 0) & e.footnote_class.ne('UNAVAILABLE_SYSTEM')
    e['replacement_value'] = e.raw_value.where(e.valid)
    e['calendar_quarter'] = e.reporting_period.str[:4] + 'Q' + ((e.reporting_period.str[4:].astype(int) - 1) // 3 + 1).astype(str)
    e['validity_reason'] = np.where(e.valid, 'R1_VALID_RETAINED', np.where(e.footnote_class.eq('UNAVAILABLE_SYSTEM'), 'SYSTEM_UNAVAILABLE_SET_NA', 'INVALID_RAW_VALUE_SET_NA'))
    e['official_replacement'] = 'NONE_R0_NOT_VERIFIABLE'
    e.rename(columns={'state_abbreviation': 'state', 'reporting_period': 'month'})[['state', 'month', 'calendar_quarter', 'raw_value', 'replacement_value', 'footnote_class', 'validity_reason', 'official_replacement']].to_csv(target(WORK / 'monthly_population_ledger.csv'), index=False, float_format='%.17g')
    q = e.groupby(['state_abbreviation', 'calendar_quarter']).agg(N_legacy=('raw_value', 'mean'), N_R1=('replacement_value', 'mean'), valid_months=('valid', 'sum'), raw_months=('raw_value', 'size'), partial_months=('footnote_class', lambda z: int((z == 'PARTIAL_POPULATION').sum())))
    q.loc[q.valid_months < 2, 'N_R1'] = np.nan
    q = q.reset_index().rename(columns={'state_abbreviation': 'state'})
    q.to_csv(target(WORK / 'quarterly_population_ledger.csv'), index=False, float_format='%.17g')
    f = f.merge(q, on=['state', 'calendar_quarter'], how='left', validate='many_to_one', sort=False)
    assert kh(keys(f)) == ah['requested_row_order_hash']
    assert np.isfinite(f.N_legacy).all() and np.all(np.abs(f.N_legacy - f.medicaid_enrollment) <= 1e-06)
    ri = q[(q.state == 'RI') & (q.calendar_quarter == '2024Q4')]
    assert len(ri) == 1 and ri.valid_months.iloc[0] == 2 and (ri.N_R1.iloc[0] > ri.N_legacy.iloc[0])
    cw(OUT / '04B_RI_Quarter_Correction.csv', ri.to_dict('records'))
    cw(OUT / '04B_Population_Affected_Quarters.csv', q[(q.valid_months < q.raw_months) | (q.partial_months > 0)].to_dict('records'))
    maprows = rc(ROOT / '03_audit_outputs/Stage02/02_NDC_Product_Mapping.csv')
    mapping = {r['NDC']: (r['Observed_Brands'], set(r['Observed_Product_Names'].split(';'))) for r in maprows}
    rr = []
    for year in [2023, 2024, 2025]:
        rel = f'raw/sdud/sdud_glp1_{year}.csv'
        r = pd.read_csv(safe(SRC / rel), dtype=str, keep_default_na=False)
        r['source_file'] = rel
        r['source_row'] = np.arange(1, len(r) + 1)
        r = r[r.state.isin(STABLE) & r.analytic_brand.isin(['WEGOVY', 'OZEMPIC'])].copy()
        r['quarter_index'] = r.year.astype(int) * 4 + r.quarter.astype(int)
        r = r[r.quarter_index >= 2023 * 4 + 2]
        assert r.ndc.str.fullmatch('\\d{11}').all() and r.utilization_type.isin(['FFSU', 'MCOU']).all()
        assert r.apply(lambda z: z.ndc in mapping and z.analytic_brand == mapping[z.ndc][0] and (z.product_name.strip() in mapping[z.ndc][1]), axis=1).all()
        rr.append(r)
    raw = pd.concat(rr, ignore_index=True)
    assert not raw.duplicated(['state', 'year', 'quarter', 'ndc', 'utilization_type']).any()
    assert raw.suppression_used.str.lower().isin(['true', 'false']).all()
    raw['suppressed'] = raw.suppression_used.str.lower().eq('true')
    raw['observed'] = pd.to_numeric(raw.number_of_prescriptions, errors='coerce')
    assert (np.isfinite(raw.loc[~raw.suppressed, 'observed']) & (raw.loc[~raw.suppressed, 'observed'] >= 0)).all()
    assert raw.loc[raw.suppressed, 'observed'].isna().all(), 'cannot silently overwrite an observed suppressed numeric value'
    raw['calendar_quarter'] = raw.year + 'Q' + raw.quarter
    raw['coverage_2024'] = raw.state.isin(COVER).astype(int)
    raw['obesity'] = (raw.analytic_brand == 'WEGOVY').astype(int)
    raw['post'] = (raw.quarter_index >= 2024 * 4 + 2).astype(int)
    raw['contrast_sign'] = (2 * (1 - raw.coverage_2024) - 1) * (2 * raw.obesity - 1) * (2 * raw.post - 1)
    assert set(raw.contrast_sign) == {-1, 1}
    raw[['source_file', 'source_row', 'state', 'year', 'quarter', 'calendar_quarter', 'ndc', 'utilization_type', 'analytic_brand', 'suppressed', 'observed', 'contrast_sign']].to_csv(target(WORK / 'raw_NDC_model_ledger.csv'), index=False)
    agg = raw.groupby(['state', 'calendar_quarter', 'analytic_brand', 'utilization_type']).agg(source_cells=('ndc', 'size'), suppressed_cells=('suppressed', 'sum'))
    pres = []
    for s in sorted(STABLE):
        for qq in QUARTERS:
            cells = [int(agg.loc[(s, qq, b, c), 'source_cells']) if (s, qq, b, c) in agg.index else 0 for b in ['OZEMPIC', 'WEGOVY'] for c in ['FFSU', 'MCOU']]
            pop = f[(f.state == s) & (f.calendar_quarter == qq)].iloc[0]
            valid = bool(np.isfinite(pop.N_R1) and pop.N_R1 > 0 and (pop.valid_months >= 2))
            pres.append({'state': s, 'calendar_quarter': qq, 'coverage_2024': int(s in COVER), 'pre_post': 'POST' if qq >= '2024Q2' else 'PRE', 'OZEMPIC_FFSU_source': cells[0], 'OZEMPIC_MCOU_source': cells[1], 'WEGOVY_FFSU_source': cells[2], 'WEGOVY_MCOU_source': cells[3], 'R1_valid_population': valid, 'M0_pair_requested': valid, 'M1_pair_reportable': bool(valid and all((v > 0 for v in cells))), 'exclusion_reason': 'NONE' if valid and all((v > 0 for v in cells)) else 'INVALID_QUARTER_POPULATION' if not valid else 'UNKNOWN_CHANNEL_MISSING; EXCLUDE_BOTH_PRODUCTS'})
    cw(OUT / '04B_M0_M1_Pair_Support.csv', pres)
    reportable = {(r['state'], r['calendar_quarter']) for r in pres if r['M1_pair_reportable']}
    scenarios = {'MID': 5.5, 'S0': 0.0, 'S10': 10.0, 'S11': 11.0, 'S25': 25.0, 'S50': 50.0, 'POS10_NEG0': None, 'POS0_NEG10': None}
    source_scenario = []
    ys = {}
    for scenario, value in scenarios.items():
        assigned = np.where(raw.contrast_sign > 0, 10.0, 0.0) if scenario == 'POS10_NEG0' else np.where(raw.contrast_sign > 0, 0.0, 10.0) if scenario == 'POS0_NEG10' else value
        z = raw.copy()
        z['y_cell'] = np.where(z.suppressed, assigned, z.observed)
        v = z.groupby(['state', 'calendar_quarter', 'analytic_brand']).y_cell.sum()
        ys[scenario] = v
        led = [f'{r.source_file}|{r.source_row}|{r.state}|{r.calendar_quarter}|{r.ndc}|{r.utilization_type}|{f17(r.y_cell)}' for r in z.itertuples()]
        source_scenario.append({'Scenario': scenario, 'Assignment': str(value) if value is not None else 'eight-cell triple contrast ±1; swapped0/10', 'Source_NDC_rows': len(z), 'Suppressed_NDC_rows': int(z.suppressed.sum()), 'Assigned_source_hash': kh(led), 'Strict_bound': 'NO'})
    cw(OUT / '04B_Source_Suppression_Scenarios.csv', source_scenario)
    mid = [float(ys['MID'].get((r.state, r.calendar_quarter, r.analytic_brand), 0)) for r in f.itertuples()]
    assert np.allclose(mid, f.rx_mid.to_numpy(), rtol=0, atol=1e-09)
    variants = [('04B-01', 'R3_M0_MID', 'R3', 'M0', 'MID'), ('04B-01', 'R1_M0_MID', 'R1', 'M0', 'MID'), ('04B-02', 'R2_M0_MID', 'R2', 'M0', 'MID'), ('04B-02', 'R1_PARTIAL_M0_MID', 'R1_PARTIAL', 'M0', 'MID'), ('04B-03', 'R1_M1_MID', 'R1', 'M1', 'MID')]
    variants += [('04B-04', f'R1_M0_{s}', 'R1', 'M0', s) for s in ['S0', 'S10']]
    variants += [('04B-04', f'R1_M1_{s}', 'R1', 'M1', s) for s in ['S0', 'S10']]
    variants += [('04B-05', f'R1_M1_{s}', 'R1', 'M1', s) for s in ['S11', 'S25', 'S50', 'POS10_NEG0', 'POS0_NEG10']]
    manifests = []
    for aid, vid, R, M, S in variants:
        vf = f.copy()
        vf['y'] = [float(ys[S].get((r.state, r.calendar_quarter, r.analytic_brand), 0)) for r in vf.itertuples()]
        vf['N'] = vf.N_legacy if R == 'R3' else vf.N_R1
        keep = np.isfinite(vf.N) & (vf.N > 0)
        if R == 'R2':
            keep &= ~((vf.state == 'RI') & (vf.calendar_quarter == '2024Q4'))
        if R == 'R1_PARTIAL':
            keep &= vf.partial_months.eq(0)
        if M == 'M1':
            keep &= np.array([(r.state, r.calendar_quarter) in reportable for r in vf.itertuples()])
        excluded = vf.loc[~keep, ['state', 'calendar_quarter', 'analytic_brand']].copy()
        excluded['reason'] = R + '_' + M + '_PRESET_INPUT_RULE'
        excluded.to_csv(target(WORK / (vid + '_input_exclusions.csv')), index=False)
        vf = vf[keep].copy()
        vf['offset'] = np.log(vf.N)
        assert np.isfinite(vf.y).all() and (vf.y >= 0).all() and np.isfinite(vf.offset).all()
        assert not vf.duplicated(['state', 'calendar_quarter', 'analytic_brand']).any()
        if M == 'M1':
            assert (vf.groupby(['state', 'calendar_quarter']).size() == 2).all()
        p = target(WORK / (vid + '_requested.csv'))
        vf.to_csv(p, index=False, float_format='%.17g')
        manifests.append({'Analysis_ID': aid, 'Variant_ID': vid, 'R': R, 'M': M, 'S': S, 'DATA_window': 'DATA-11', 'quarters': QUARTERS, 'P': 'P1_46_12_34', 'F': 'F0', 'requested_n': len(vf), 'requested_G': vf.state.nunique(), 'input_csv': str(p), 'input_csv_sha': sha(p), 'requested_keys_hash': kh(sorted(keys(vf))), 'requested_order_hash': kh(keys(vf)), 'requested_data_hash': datahash(vf), 'source_scenario_hash': next((r['Assigned_source_hash'] for r in source_scenario if r['Scenario'] == S)), 'population_ledger_sha': sha(WORK / 'quarterly_population_ledger.csv'), 'inherited_baseline': 'Stage04A_R3C VALID_EFFECTIVE_SAMPLE_RESULT', 'reuse_baseline': vid == 'R3_M0_MID', 'source_family': 'source/raw frozen SHA verified against A manifest'})
    jw(WORK / 'variant_manifest.json', manifests)
    jw(WORK / 'input_gate.json', {'G_DATA': 'PASS', 'variants': len(manifests), 'M1_reportable_pairs': len(reportable), 'M1_requested_n': 2 * len(reportable), 'RI_R0': 'NOT_VERIFIABLE', 'R1_fallback': 'AT_LEAST_TWO_VALID_MONTHS', 'raw_ndc_rows': len(raw), 'source_aggregation_legacy_match': True, 'source_sha': [{k: r[k] for k in ['Path', 'SHA256']} for r in rc(A / '04A_R3C_Input_Manifest.csv')], 'plan_sha': sha(WORK / 'prospective_plan.json'), 'variant_manifest_sha': sha(WORK / 'variant_manifest.json')})
    print('G_ENV=PASS; input ledgers/scenarios frozen; variants=' + str(len(manifests)) + '; M1 requested=' + str(2 * len(reportable)))
if __name__ == '__main__':
    try:
        main()
    except Exception:
        target(WORK / 'inputs_failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
