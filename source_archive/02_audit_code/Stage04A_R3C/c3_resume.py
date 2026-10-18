"""Continue C3 after targeted XX/PR source-name adjudication, no mapping edit.
Reuses completed raw partition/independent-ledger checks; first unfinished
checkpoint is source-to-saved numerators and monthly offset comparison.
"""
from common import *
from input_audit import STATES, CHANGERS, BRANDS, METRICS, keys, f17
import math, traceback
from collections import defaultdict
import numpy as np
import pandas as pd

def main():
    assert jr(WORK / 'environment_gate.json')['G_ENV'] == 'PASS'
    record('C3_resume')
    prior = jr(WORK / 'source_ledger_A.json')
    a = jr(WORK / 'C3_anomaly_targeted_evidence.json')
    assert len(a) == len(prior['anomalies']) == 3
    assert {(r['file'], r['row']) for r in a} == {(r['file'], r['row']) for r in prior['anomalies']}
    assert all((r['reason'] == 'UNMAPPED' for r in prior['anomalies'])) and all((r['state'] in {'XX', 'PR'} for r in a))
    assert 'assert not anomalies' in safe(WORK / 'C3_failure.txt').read_text(encoding='utf-8')
    for r in rc(OUT / '04A_R3C_Input_Manifest.csv'):
        assert sha(r['Path']) == r['SHA256']
    cw(OUT / '04A_R3C_Source_Anomaly_Adjudication.csv', [{**r, 'Status': 'CONFIRMED', 'Disposition': 'UNMAPPED_RETAINED; XX_OR_PR_OUTSIDE_51_SCOPE', 'Main_sample_impact': 'NONE_BY_GEOGRAPHIC_SCOPE'} for r in a])
    md('04A_R3C_C3_Continuation_Note.md', '# C3 定点范围裁决\n\n初次源审计38375行，双实现互斥partition、ledger hash与aggregate assertions通过，随后因3个UNMAPPED的保守全域停止。实际失败trace与code_at_C3_input保留。定点读取证明三个均为XX或PR产品名称不在冻结州级映射中，不属于51辖区或请求46州。UNMAPPED不改为已映射，不改NDC/name或源数据；明确范围排除，未掩盖相关源异常。任何51内UNMAPPED、INVALID或unresolved duplicate仍硬停。\n\n本次只继续尚未完成的channel/combined分子及monthly offset核对。原完成的raw partition/两独立ledger验收直接复用；因首次未保存aggregate中间数组，只重读eligible记录恢复下游所需工作数组，不重判或改写已完成partition、不重新执行双实现验收。\n')
    mapped = {r['NDC']: (r['Observed_Brands'], set(r['Observed_Product_Names'].split(';'))) for r in rc(ROOT / '03_audit_outputs/Stage02/02_NDC_Product_Mapping.csv')}
    agg = defaultdict(lambda: np.zeros(5))
    eligible = 0
    for year in range(2019, 2026):
        for r in rc(SRC / f'raw/sdud/sdud_glp1_{year}.csv'):
            if r['state'] not in STATES or r['analytic_brand'] not in BRANDS or int(r['year']) * 4 + int(r['quarter']) < 2023 * 4 + 2:
                continue
            assert r['ndc'] in mapped and r['analytic_brand'] == mapped[r['ndc']][0] and (r['product_name'].strip() in mapped[r['ndc']][1])
            s = r['suppression_used'].lower() == 'true'
            v = float(r['number_of_prescriptions']) if r['number_of_prescriptions'] else 0.0
            k = (r['state'], r['year'] + 'Q' + r['quarter'], r['analytic_brand'], r['utilization_type'])
            agg[k] += np.array([v, 5.5 if s else v, 10.0 if s else v, int(s), 1])
            eligible += 1
    assert eligible == sum((int(r['Rows']) for r in rc(OUT / '04A_R3C_Source_Partition_Audit.csv') if r['Partition'] == 'ELIGIBLE'))
    f = pd.read_csv(safe(WORK / 'requested_input.csv'), float_precision='round_trip')
    h = jr(OUT / '04A_R3C_Model_Input_Hashes.json')
    assert kh(keys(f)) == h['requested_row_order_hash']
    assert kh([k + '|' + '|'.join((f17(r[c]) for c in h['data_fields'])) for k, (_, r) in zip(keys(f), f.iterrows())]) == h['requested_data_hash']
    pu = pd.read_csv(safe(SRC / 'processed/state_quarter_brand_utilization.csv'))
    pu = pu[pu.state.isin(STATES) & pu.analytic_brand.isin(BRANDS) & (pu.quarter_index >= 2023 * 4 + 2)]
    quarters = {f'{y}Q{q}' for y in range(2023, 2026) for q in range(1, 5) if (y, q) >= (2023, 2)}
    expected = {(s, q, p, c) for s in STATES for q in quarters for p in BRANDS for c in ['FFSU', 'MCOU']}
    assert len(pu) == len(expected) and (not pu.duplicated(['state', 'calendar_quarter', 'analytic_brand', 'utilization_type']).any())
    assert set(zip(pu.state, pu.calendar_quarter, pu.analytic_brand, pu.utilization_type)) == expected
    assert (pu.quarter_index == pu.year * 4 + pu.quarter).all() and (pu.calendar_quarter == pu.year.astype(str) + 'Q' + pu.quarter.astype(str)).all()
    cells = []
    for r in pu.itertuples():
        v = agg.get((r.state, r.calendar_quarter, r.analytic_brand, r.utilization_type), np.zeros(5))
        assert np.allclose(v, [getattr(r, c) for c in METRICS], rtol=0, atol=1e-09)
        status = 'MISSING_SOURCE_RECORD' if v[4] == 0 else 'SUPPRESSED' if v[3] == v[4] else 'MIXED_OBSERVED_SUPPRESSED' if v[3] else 'OBSERVED_ZERO' if v[1] == 0 else 'OBSERVED_POSITIVE'
        cells.append({'state': r.state, 'quarter': r.calendar_quarter, 'brand': r.analytic_brand, 'channel': r.utilization_type, 'source_status': status, 'source_cells': int(v[4]), 'suppressed_cells': int(v[3]), 'rx_mid': v[1], 'stable_sample': int(r.state not in CHANGERS)})
    cw(WORK / 'source_presence_channel.csv', cells)
    for r in f.itertuples():
        v = sum((agg.get((r.state, r.calendar_quarter, r.analytic_brand, c), np.zeros(5)) for c in ['FFSU', 'MCOU']), np.zeros(5))
        assert np.allclose(v, [getattr(r, c) for c in METRICS], rtol=0, atol=1e-09)
    monthly = defaultdict(list)
    mk = []
    ri = []
    for r in rc(SRC / 'raw/enrollment/cms_monthly_enrollment_2019_2025.csv'):
        if r['preliminary_or_updated'] == 'U' and r['final_report'] == 'Y' and (r['state_abbreviation'] in STATES):
            p = r['reporting_period']
            key = (r['state_abbreviation'], p)
            mk.append(key)
            q = (int(p[4:]) - 1) // 3 + 1
            monthly[key[0], p[:4] + 'Q' + str(q)].append(float(r['total_medicaid_enrollment']))
            if key == ('RI', '202412'):
                ri.append(float(r['total_medicaid_enrollment']))
    assert len(mk) == len(set(mk)) and ri == [0.0]
    dif = []
    mr = []
    for (s, q), z in f.groupby(['state', 'calendar_quarter']):
        v = monthly.get((s, q), [])
        assert v and np.isfinite(v).all() and (np.asarray(v) >= 0).all()
        assert z.medicaid_enrollment.nunique() == 1
        d = abs(z.medicaid_enrollment.iloc[0] - np.mean(v))
        assert math.isfinite(d) and d <= 1e-06
        dif.append(d)
        mr.append({'state': s, 'quarter': q, 'numeric_months': len(v), 'positive_months': int((np.asarray(v) > 0).sum()), 'original_mean': np.mean(v), 'absolute_difference': d})
    cw(OUT / '04A_R3C_Enrollment_Component_Audit.csv', mr)
    cp = pd.DataFrame(cells)
    cp = cp[cp.stable_sample == 1]
    cw(OUT / '04A_R3C_Source_Presence_Summary.csv', cp.groupby(['brand', 'channel', 'source_status']).agg(cells=('state', 'size'), source_rows=('source_cells', 'sum'), suppressed_rows=('suppressed_cells', 'sum')).reset_index().to_dict('records'))
    old = jr(WORK / 'original_saved_result.json')
    missing_c = int((cp.source_cells == 0).sum())
    missing_p = int((f.source_cells == 0).sum())
    result = {'G_DATA': 'PASS', 'scope': 'SAVED_PANEL_REPLICATION', 'raw_to_panel': 'NUMERATOR_OFFSET_COMPONENTS_RECONCILED_NOT_FULL_BUILD', 'raw_rows': prior['rows'], 'raw_ledger_hash_A': prior['ledger_hash'], 'raw_ledger_hash_B': prior['ledger_hash'], 'independent_ledger_check': 'REUSED_ACTUAL_C3_ASSERTIONS', 'unmapped_out_of_scope': 3, 'unresolved_main_anomalies': 0, 'source_channel_cells_compared': len(pu), 'combined_requested_compared': len(f), 'missing_requested_channels': missing_c, 'missing_requested_combined': missing_p, 'RI_202412_original_zero_retained': True, 'enrollment_max_abs_difference': max(dif), 'old_result': old, 'requested_hashes': h, 'source_completeness_truth': 'NOT_VERIFIABLE'}
    jw(WORK / 'data_gate.json', result)
    md('04A_R3C_Data_Gate.md', f"# C3 请求输入及范围门槛\n\nG_DATA=PASS，限历史保存设定可重算。1012行、46辖区、12/34、11季、两产品、唯一key和正finite offset已冻结。原顺序hash/数值17g hash见Model_Input_Hashes；直接冻结保存β={old['estimate']}与SE={old['std_error']}。原script只静态读取，确切原执行链仍INFERRED，原run身份NOT_VERIFIABLE。\n\n7年度38375行双实现源partition/ledger hash/eligible aggregate一致的实际验收复用。3个UNMAPPED在XX/PR，按地理范围不影响51辖区或46主样本；原记录保留，未扩展冻结映射。详见Source_Anomaly_Adjudication和C3_Continuation_Note。{len(pu)}个完整channel预期网格及1012合并分子的lower/mid/upper/source/suppressed数量逐项匹配，0未知行影响主输入。\n\n请求缺源渠道{missing_c}、合并缺源{missing_p}均沿旧0；缺源≠真实观测零。midpoint5.5及FFSU+MCOU保持，5.5非严格数量界。源presence状态按原记录判定，未知真实提交完整性NOT_VERIFIABLE；本窗口产品已获批，STRUCTURAL_NOT_ON_MARKET不适用。\n\n每state-quarter月值非空finite非负、唯一月key，独立平均与保存offset组件最大绝对差{max(dif):.17g}，RI202412缺失占位0保留于均值。逐季numeric/positive月数公开；不修原RI。保留2024Q1 pre、July固定政策组及旧源补零规则。\n\nSAVED_PANEL_REPLICATION。raw→panel仅模型分子/offset组件核对，ACS/cost/完整历史政策pipeline未重建，不能称完整RAW_TO_PANEL_REPRODUCTION。此门槛不解决原RI/缺源/政策时序/渠道、因果识别或患者公平P0。\n")
    print('G_DATA=PASS; out-of-scope3 unmapped retained; first unfinished component checks completed')
if __name__ == '__main__':
    try:
        main()
    except Exception:
        target(WORK / 'C3_resume_failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
