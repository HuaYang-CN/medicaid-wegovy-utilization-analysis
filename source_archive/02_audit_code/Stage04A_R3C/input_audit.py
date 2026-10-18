"""C3 frozen saved-panel replication and independent raw component reconciliation.
Never imports historical code or rebuilds ancillary ACS/cost/policy pipeline.
"""
from common import *
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import math, re, traceback
from collections import Counter, defaultdict
import numpy as np
import pandas as pd
STATES = set('AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())
COVER = set('CA DE KS MA MI MN MS NH PA RI VA WI'.split())
CHANGERS = set('MO SC TN UT NC'.split())
BRANDS = {'WEGOVY', 'OZEMPIC'}
METRICS = ['rx_lower', 'rx_mid', 'rx_upper', 'suppressed_cells', 'source_cells']

def keys(f):
    return (f.state.astype(str) + '|' + f.calendar_quarter.astype(str) + '|' + f.analytic_brand.astype(str)).tolist()

def f17(v):
    return format(float(v), '.17g')

def main():
    assert jr(WORK / 'environment_gate.json')['G_ENV'] == 'PASS'
    record('C3_input')
    protected = jr(WORK / 'key_protection_before.json')
    relevant = [r for r in protected if Path(r['path']).is_relative_to(SRC) or 'Stage02' in r['path']]
    manifest = []
    for r in relevant:
        actual = sha(r['path'])
        assert actual == r['sha256'], 'input bytes changed'
        manifest.append({'Path': r['path'], 'SHA256': actual, 'Role': 'FROZEN_SOURCE_OR_STAGE02', 'Readonly': 'YES'})
    cw(OUT / '04A_R3C_Input_Manifest.csv', manifest)
    panel = pd.read_csv(safe(SRC / 'processed/state_quarter_brand.csv'))
    frame = panel[panel.analytic_brand.isin(BRANDS) & (panel.quarter_index >= 2023 * 4 + 2) & (panel.stable_policy_sample == 1)].dropna(subset=['medicaid_enrollment']).copy()
    frame['source_panel_row'] = frame.index + 1
    assert len(frame) == 1012 and frame.state.nunique() == 46 and (frame.calendar_quarter.nunique() == 11)
    assert set(frame.calendar_quarter) == {f'{y}Q{q}' for y in range(2023, 2026) for q in range(1, 5) if (y, q) >= (2023, 2)}
    assert set(frame.state) == STATES - CHANGERS and set(frame.analytic_brand) == BRANDS
    assert not frame.duplicated(['state', 'calendar_quarter', 'analytic_brand']).any()
    assert np.isfinite(frame.rx_mid).all() and (frame.rx_mid >= 0).all()
    assert np.isfinite(frame.medicaid_enrollment).all() and (frame.medicaid_enrollment > 0).all()
    assert (frame.quarter_index == frame.year * 4 + frame.quarter).all()
    assert (frame.calendar_quarter == frame.year.astype(str) + 'Q' + frame.quarter.astype(str)).all()
    assert (frame.coverage_2024 == frame.state.isin(COVER).astype(int)).all()
    assert (frame.noncoverage_2024 == 1 - frame.coverage_2024).all()
    assert (frame.policy_changer_2024_2025 == 0).all()
    state = frame.drop_duplicates('state')
    assert int(state.coverage_2024.sum()) == 12 and int(state.noncoverage_2024.sum()) == 34
    assert (frame.groupby('state').size() == 22).all()
    frame['obesity'] = (frame.analytic_brand == 'WEGOVY').astype(int)
    frame['post'] = (frame.quarter_index >= 2024 * 4 + 2).astype(int)
    frame['offset'] = np.log(frame.medicaid_enrollment)
    rowkeys = keys(frame)
    numeric_cols = ['rx_mid', 'medicaid_enrollment', 'offset', 'coverage_2024', 'noncoverage_2024', 'obesity', 'post', 'quarter_index']
    lines = [k + '|' + '|'.join((f17(row[c]) for c in numeric_cols)) for k, (_, row) in zip(rowkeys, frame.iterrows())]
    h = {'requested_n': len(frame), 'requested_G': 46, 'requested_row_key_hash': kh(sorted(rowkeys)), 'requested_row_order_hash': kh(rowkeys), 'requested_sample_hash': kh(sorted(rowkeys)), 'requested_data_hash': kh(lines), 'data_fields': numeric_cols, 'serialization': 'UTF8 newline; numeric .17g; original saved-panel row order', 'scope': 'SAVED_PANEL_REPLICATION', 'input_file_hash': sha(SRC / 'processed/state_quarter_brand.csv')}
    jw(OUT / '04A_R3C_Model_Input_Hashes.json', h)
    frame.to_csv(target(WORK / 'requested_input.csv'), index=False, float_format='%.17g')
    checks = [{'Check': 'requested_rows', 'Observed': 1012, 'Expected': 1012, 'Status': 'PASS'}, {'Check': 'states_coverage_noncoverage', 'Observed': '46/12/34', 'Expected': '46/12/34', 'Status': 'PASS'}, {'Check': 'quarters_products', 'Observed': '11 / WEGOVY,OZEMPIC', 'Expected': '2023Q2–2025Q4 / two', 'Status': 'PASS'}, {'Check': 'duplicates_nonfinite_negative_invalid_offset', 'Observed': 0, 'Expected': 0, 'Status': 'PASS'}, {'Check': '2024Q1 retained_as_pre', 'Observed': len(frame[frame.calendar_quarter == '2024Q1']), 'Expected': 92, 'Status': 'PASS'}]
    cw(OUT / '04A_R3C_Sample_Key_Audit.csv', checks)
    saved = rc(SRC / 'analysis/ddd_model_results.csv')
    old = [r for r in saved if r['term'] == 'DDD' and r['pair'] == 'Wegovy vs Ozempic' and (r['scenario'] == 'mid') and r['model'].startswith('PPML')]
    assert len(old) == 1
    jw(WORK / 'original_saved_result.json', old[0])
    mapping = rc(ROOT / '03_audit_outputs/Stage02/02_NDC_Product_Mapping.csv')
    mapped = {r['NDC']: (r['Observed_Brands'], set(r['Observed_Product_Names'].split(';'))) for r in mapping}
    assert len(mapped) == len(mapping) and all((r['Conflict'] == 'False' for r in mapping))
    cross = rc(SRC / 'processed/ndc_brand_crosswalk.csv')
    for r in cross:
        assert r['ndc'] in mapped and r['analytic_brand'] == mapped[r['ndc']][0] and (r['product_name'].strip() in mapped[r['ndc']][1])
    raw = []
    counter = Counter()
    for year in range(2019, 2026):
        rel = f'raw/sdud/sdud_glp1_{year}.csv'
        for ix, r in enumerate(rc(SRC / rel), 1):
            key = (r['state'], r['year'], r['quarter'], r['ndc'], r['utilization_type'])
            counter[key] += 1
            raw.append((rel, ix, r, key))
    ledger = []
    agg = defaultdict(lambda: np.zeros(5))
    counts = defaultdict(Counter)
    anomalies = []
    for rel, ix, r, key in raw:
        try:
            year = int(r['year'])
            q = int(r['quarter'])
            ndc = r['ndc']
            chan = r['utilization_type']
            sup = r['suppression_used'].lower() == 'true'
            value = float(r['number_of_prescriptions']) if r['number_of_prescriptions'] else None
            valid = 1 <= q <= 4 and 2019 <= year <= 2025 and (re.fullmatch('\\d{11}', ndc) is not None) and (chan in {'FFSU', 'MCOU'}) and (r['suppression_used'].lower() in {'true', 'false'}) and (sup or (value is not None and math.isfinite(value) and (value >= 0)))
        except (ValueError, TypeError):
            valid = False
            year = 0
            q = 0
            sup = False
            value = None
        mapped_ok = r['ndc'] in mapped and r['analytic_brand'] == mapped[r['ndc']][0] and (r['product_name'].strip() in mapped[r['ndc']][1])
        if not valid:
            part = 'INVALID'
        elif counter[key] > 1:
            part = 'UNRESOLVED_DUPLICATE'
        elif not mapped_ok:
            part = 'UNMAPPED'
        elif r['state'] not in STATES:
            part = 'EXCLUDED_STATE'
        elif r['analytic_brand'] not in BRANDS:
            part = 'EXCLUDED_PRODUCT'
        elif year * 4 + q < 2023 * 4 + 2:
            part = 'EXCLUDED_WINDOW'
        else:
            part = 'ELIGIBLE'
        counts[rel][part] += 1
        status = 'SUPPRESSED' if sup else 'OBSERVED_ZERO' if value == 0 else 'OBSERVED_POSITIVE'
        lower = 0.0 if sup and value is None else value or 0.0
        mid = 5.5 if sup else value or 0.0
        upper = 10.0 if sup else value or 0.0
        line = f'{rel}|{ix}|' + '|'.join(key) + f'|{part}|{status}|{f17(lower)}|{f17(mid)}|{f17(upper)}'
        ledger.append(line)
        if part == 'ELIGIBLE':
            agg[r['state'], f'{year}Q{q}', r['analytic_brand'], r['utilization_type']] += np.array([lower, mid, upper, int(sup), 1])
        if part in {'INVALID', 'UNMAPPED', 'UNRESOLVED_DUPLICATE'}:
            anomalies.append({'file': rel, 'row': ix, 'reason': part})
    jw(WORK / 'source_ledger_A.json', {'ledger_hash': kh(ledger), 'rows': len(ledger), 'anomalies': anomalies})
    mf = pd.read_csv(safe(ROOT / '03_audit_outputs/Stage02/02_NDC_Product_Mapping.csv'), dtype=str, keep_default_na=False)
    bf = []
    for year in range(2019, 2026):
        rel = f'raw/sdud/sdud_glp1_{year}.csv'
        b = pd.read_csv(safe(SRC / rel), dtype=str, keep_default_na=False)
        b['file'] = rel
        b['row'] = np.arange(1, len(b) + 1)
        bf.append(b)
    b = pd.concat(bf, ignore_index=True)
    dup = b.duplicated(['state', 'year', 'quarter', 'ndc', 'utilization_type'], keep=False)
    b['yy'] = pd.to_numeric(b.year, errors='coerce')
    b['qq'] = pd.to_numeric(b.quarter, errors='coerce')
    b['v'] = pd.to_numeric(b.number_of_prescriptions, errors='coerce')
    b['s'] = b.suppression_used.str.lower().eq('true')
    valid = b.yy.between(2019, 2025) & b.qq.between(1, 4) & (b.yy == np.floor(b.yy)) & (b.qq == np.floor(b.qq)) & b.ndc.str.fullmatch('\\d{11}') & b.utilization_type.isin(['FFSU', 'MCOU']) & b.suppression_used.str.lower().isin(['true', 'false']) & (b.s | np.isfinite(b.v) & (b.v >= 0))
    mbr = dict(zip(mf.NDC, mf.Observed_Brands))
    mnm = dict(zip(mf.NDC, mf.Observed_Product_Names))
    mapok = b.apply(lambda r: r.ndc in mbr and r.analytic_brand == mbr[r.ndc] and (r.product_name.strip() in mnm[r.ndc].split(';')), axis=1)
    b['part'] = np.select([~valid, dup, ~mapok, ~b.state.isin(STATES), ~b.analytic_brand.isin(BRANDS), b.yy * 4 + b.qq < 2023 * 4 + 2], ['INVALID', 'UNRESOLVED_DUPLICATE', 'UNMAPPED', 'EXCLUDED_STATE', 'EXCLUDED_PRODUCT', 'EXCLUDED_WINDOW'], default='ELIGIBLE')
    b['lower'] = b.v.fillna(0)
    b['mid'] = np.where(b.s, 5.5, b.v.fillna(0))
    b['upper'] = np.where(b.s, 10.0, b.v.fillna(0))
    b['status'] = np.where(b.s, 'SUPPRESSED', np.where(b.v == 0, 'OBSERVED_ZERO', 'OBSERVED_POSITIVE'))
    ledger_b = [f'{r.file}|{r.row}|{r.state}|{r.year}|{r.quarter}|{r.ndc}|{r.utilization_type}|{r.part}|{r.status}|{f17(r.lower)}|{f17(r.mid)}|{f17(r.upper)}' for r in b.itertuples()]
    assert kh(ledger) == kh(ledger_b) and len(ledger) == len(b), 'independent raw ledgers disagree'
    b['cal'] = b.year + 'Q' + b.quarter
    b['suppressed_cells'] = b.s.astype(int)
    b['source_cells'] = 1
    ba = b[b.part == 'ELIGIBLE'].groupby(['state', 'cal', 'analytic_brand', 'utilization_type'])[['lower', 'mid', 'upper', 'suppressed_cells', 'source_cells']].sum()
    assert len(ba) == len(agg)
    for k, v in agg.items():
        assert np.allclose(v, ba.loc[k].to_numpy(float), rtol=0, atol=1e-09)
    partitions = [{'File': rel, 'Partition': part, 'Rows': n, 'Mutually_Exclusive': 'YES', 'Covers_All_Rows': 'YES'} for rel, c in counts.items() for part, n in sorted(c.items())]
    cw(OUT / '04A_R3C_Source_Partition_Audit.csv', partitions)
    assert not anomalies, 'source invalid/unmapped/duplicate rows require adjudication'
    pu = pd.read_csv(safe(SRC / 'processed/state_quarter_brand_utilization.csv'))
    pu = pu[pu.state.isin(STATES) & pu.analytic_brand.isin(BRANDS) & (pu.quarter_index >= 2023 * 4 + 2)]
    assert len(pu) == 51 * 11 * 2 * 2 and (not pu.duplicated(['state', 'calendar_quarter', 'analytic_brand', 'utilization_type']).any())
    expected_quarters = {f'{y}Q{q}' for y in range(2023, 2026) for q in range(1, 5) if (y, q) >= (2023, 2)}
    expected_grid = {(s, q, p, c) for s in STATES for q in expected_quarters for p in BRANDS for c in ['FFSU', 'MCOU']}
    assert set(zip(pu.state, pu.calendar_quarter, pu.analytic_brand, pu.utilization_type)) == expected_grid
    assert (pu.quarter_index == pu.year * 4 + pu.quarter).all()
    assert (pu.calendar_quarter == pu.year.astype(str) + 'Q' + pu.quarter.astype(str)).all()
    cells = []
    for r in pu.itertuples():
        k = (r.state, r.calendar_quarter, r.analytic_brand, r.utilization_type)
        a = agg.get(k, np.zeros(5))
        assert np.allclose(a, [getattr(r, c) for c in METRICS], rtol=0, atol=1e-09), 'channel numerator mismatch'
        presence = 'MISSING_SOURCE_RECORD' if a[4] == 0 else 'SUPPRESSED' if a[3] == a[4] else 'MIXED_OBSERVED_SUPPRESSED' if a[3] else 'OBSERVED_ZERO' if a[1] == 0 else 'OBSERVED_POSITIVE'
        cells.append({'state': r.state, 'quarter': r.calendar_quarter, 'brand': r.analytic_brand, 'channel': r.utilization_type, 'source_status': presence, 'source_cells': int(a[4]), 'suppressed_cells': int(a[3]), 'rx_mid': a[1], 'stable_sample': int(r.state not in CHANGERS)})
    cw(WORK / 'source_presence_channel.csv', cells)
    for r in frame.itertuples():
        a = sum((agg.get((r.state, r.calendar_quarter, r.analytic_brand, c), np.zeros(5)) for c in ['FFSU', 'MCOU']), np.zeros(5))
        assert np.allclose(a, [getattr(r, c) for c in METRICS], rtol=0, atol=1e-09), 'combined numerator mismatch'
    enrol = rc(SRC / 'raw/enrollment/cms_monthly_enrollment_2019_2025.csv')
    monthly = defaultdict(list)
    mk = []
    ri = []
    for r in enrol:
        if r['preliminary_or_updated'] == 'U' and r['final_report'] == 'Y' and (r['state_abbreviation'] in STATES):
            p = r['reporting_period']
            key = (r['state_abbreviation'], p)
            mk.append(key)
            q = (int(p[4:]) - 1) // 3 + 1
            monthly[r['state_abbreviation'], p[:4] + 'Q' + str(q)].append(float(r['total_medicaid_enrollment']))
            if key == ('RI', '202412'):
                ri.append(float(r['total_medicaid_enrollment']))
    assert len(mk) == len(set(mk)) and ri == [0.0]
    differences = []
    month_audit = []
    for (s, q), a in frame.groupby(['state', 'calendar_quarter']):
        values = monthly.get((s, q), [])
        assert values and np.isfinite(values).all() and (np.asarray(values) >= 0).all(), 'monthly component missing/invalid'
        assert a.medicaid_enrollment.nunique() == 1
        diff = abs(float(a.medicaid_enrollment.iloc[0]) - float(np.mean(values)))
        assert math.isfinite(diff) and diff <= 1e-06, 'monthly mean mismatch'
        differences.append(diff)
        month_audit.append({'state': s, 'quarter': q, 'numeric_months': len(values), 'positive_months': int((np.asarray(values) > 0).sum()), 'original_mean': np.mean(values), 'absolute_difference': diff})
    maxdiff = max(differences)
    cw(OUT / '04A_R3C_Enrollment_Component_Audit.csv', month_audit)
    cp = pd.DataFrame(cells)
    cp = cp[cp.stable_sample == 1]
    missing_channels = int((cp.source_cells == 0).sum())
    missing_combined = int((frame.source_cells == 0).sum())
    summary = {'G_DATA': 'PASS', 'scope': 'SAVED_PANEL_REPLICATION', 'raw_to_panel': 'NUMERATOR_OFFSET_COMPONENTS_RECONCILED_NOT_FULL_BUILD', 'raw_rows': len(raw), 'raw_ledger_hash_A': kh(ledger), 'raw_ledger_hash_B': kh(ledger_b), 'independent_ledgers_match': True, 'source_anomalies': 0, 'source_channel_cells_compared': len(pu), 'combined_requested_compared': len(frame), 'missing_requested_channels': missing_channels, 'missing_requested_combined': missing_combined, 'RI_202412_original_zero_retained': True, 'enrollment_max_abs_difference': maxdiff, 'old_result': old[0], 'requested_hashes': h, 'source_completeness_truth': 'NOT_VERIFIABLE'}
    jw(WORK / 'data_gate.json', summary)
    cw(OUT / '04A_R3C_Source_Presence_Summary.csv', cp.groupby(['brand', 'channel', 'source_status']).agg(cells=('state', 'size'), source_rows=('source_cells', 'sum'), suppressed_rows=('suppressed_cells', 'sum')).reset_index().to_dict('records'))
    md('04A_R3C_Data_Gate.md', f"# C3 输入与来源门槛\n\nG_DATA=PASS，仅表示历史设定可重算。1012行、46辖区、12/34、11季、两产品、唯一键和正有限offset通过；保留原面板顺序、2024Q1为pre、July固定组及5个排除州。hash见Model_Input_Hashes。当前保存结果直接冻结β={old[0]['estimate']}、SE={old[0]['std_error']}，历史代码只静态读，不import。代码到保存输出运行连接仍INFERRED，确切原run版本NOT_VERIFIABLE。\n\n两套实现分别从7个冻结raw和映射读取，共{len(raw)}行；互斥partition覆盖全部行，ledger hash及逐渠道数值匹配，无invalid/unmapped/unresolved duplicate。核对51辖区×11季×2产品×2渠道={len(pu)}单元及1012合并观察的lower/mid/upper、suppressed/source_cells均匹配。仅使用观察NDC/name/brand的冻结映射，不声称完整历史目录或有效期得到验证。\n\n主样本缺源渠道{missing_channels}，合并缺源{missing_combined}，旧0均保留；缺源不是OBSERVED_ZERO。主窗口产品已获批，STRUCTURAL_NOT_ON_MARKET不适用；其他未知源机制NOT_VERIFIABLE。逐渠道状态由source presence与数量确定，未改变原y。\n\n独立月均核对offset，最大绝对差{maxdiff:.17g}；RI202412占位0照旧纳入。FFSU+MCOU、suppression midpoint5.5不变，5.5不是已证明真实数量或严格边界。标签SAVED_PANEL_REPLICATION；raw→panel只复核模型所需分子和offset组件，没有重建ACS/cost/历史政策运行链，不能声称完整RAW_TO_PANEL_REPRODUCTION或真实源完备性。以上尚无研究模型fit，不解决RI/漏报/政策时序/渠道/因果及公平构念P0。\n")
    print('G_DATA=PASS; requested1012 frozen; independent raw ledgers match')
if __name__ == '__main__':
    try:
        main()
    except Exception:
        target(WORK / 'C3_failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        jw(WORK / 'data_gate_failure.json', {'G_DATA': 'FAIL', 'error': 'see C3_failure.txt'})
        raise
