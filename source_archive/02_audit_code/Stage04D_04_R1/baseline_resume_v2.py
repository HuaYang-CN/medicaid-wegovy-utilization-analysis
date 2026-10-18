"""Versioned baseline adapter repair. No model fit/data/spec/threshold change.
Preserves first failure; supplies copied raw validator's explicit hash contract.
"""
import audit_v1 as a

def run():
    assert (a.WORK / 'baseline_failure_v1.json').exists()
    assert not (a.OUT / '04D_04_Base_Model_Reconciliation.json').exists()
    preserve = a.WORK / 'baseline_attempt_v1'
    for p in [a.WORK / 'BASE_input.csv', a.OUT / '04D_04_Preserved_Population_Aliases.csv', a.WORK / 'baseline_failure_v1.json']:
        dest = preserve / p.name
        assert not dest.exists()
        a.target(dest).write_bytes(a.safe(p).read_bytes())
    raw = a.rc(a.BW / 'raw_NDC_model_ledger.csv')
    assigned = []
    for r in raw:
        value = 5.5 if r['suppressed'].lower() == 'true' else float(r['observed'])
        assigned.append('|'.join([r['source_file'], r['source_row'], r['state'], r['calendar_quarter'], r['ndc'], r['utilization_type'], a.f17(value)]))
    h = a.kh(assigned)
    expected = a.jr(a.R2 / '_working/input_gate.json')['source_assignment_hash']
    assert h == expected and len(raw) == 5988
    a.jw(a.WORK / 'input_gate.json', {'source_assignment_hash': h, 'source_ledger_SHA256': a.sha(a.BW / 'raw_NDC_model_ledger.csv'), 'expected_frozen_R2_hash': expected, 'contract_adaptation_only': True, 'base_model_not_fitted_or_changed': True})
    a.jw(a.WORK / 'baseline_resume_v2_plan.json', {'original_failure': 'copied source validator expected input_gate.json source-assignment contract; file not created by new baseline adapter', 'repair': 'derive contract hash from verified B source ledger and compare accepted R2, then independent raw reconstruction', 'data_model_offset_population_threshold_changes': False, 'failed_evidence_preserved': 'baseline_attempt_v1 and baseline_failure_v1.json', 'native_fits': 0, 'code_version': 'baseline_resume_v2.py'})
    a.baseline()
if __name__ == '__main__':
    run()
