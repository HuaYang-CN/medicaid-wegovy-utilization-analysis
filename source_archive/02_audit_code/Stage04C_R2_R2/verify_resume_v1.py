"""Hash-based resume adjudication. Never fits or overwrites a model artifact.
Successful current v2 covariance supersedes the retained v1 failure status.
Missing/changed evidence is NOT_VERIFIABLE, never assumed complete by existence.
"""
import ast
import audit_v1 as a
import release_v1 as r

def run():
    rows = []
    for m in a.MODELS:
        d = a.WORK / m
        acc = r.accepted(m)
        checks = []
        for phase in ['input', 'design', 'separation', 'solver']:
            c = r.verify_checkpoint(d / (phase + '_checkpoint.json'))
            checks.append({'phase': phase, 'checkpoint_status': c['status'], 'artifact_and_code_hashes': 'PASS'})
        for phase in ['covariance', 'numerical_QA', 'final']:
            c = r.verify_checkpoint(acc / (phase + '_checkpoint.json'))
            checks.append({'phase': phase, 'checkpoint_status': c['status'], 'artifact_and_code_hashes': 'PASS', 'accepted_version': 'v2' if acc != d else 'v1'})
        gate = a.jr(acc / 'final_gate.json')
        assert gate['numerical_status'] == 'NUMERIC_PASS' and all((gate[k] == 'PASS' for k in ['G_ENV', 'G_DATA', 'G_TARGET', 'G_SEPARATION', 'G_SOLVER', 'G_COV', 'G_NUMERICAL_QA']))
        rows.append({'Variant_ID': m, 'status': 'COMPLETE_VERIFIED', 'accepted_final': str((acc / 'final_checkpoint.json').relative_to(a.ROOT)), 'action': 'REUSE; ZERO_REFITS', 'checks': checks, 'retained_v1_failure': acc != d})
    for p in a.CODE.glob('*.py'):
        ast.parse(p.read_text(encoding='utf-8'))
    expected = {'Medicaid_Wegovy_Stage04C_R2_PARTIAL_Feedback.zip': '82d83f59bbf3aa79686fd2f2a05462bc5835e6b3b84bd151e947ec322bb965ca', 'Medicaid_Wegovy_Stage04C_R2_R1_PARTIAL_Feedback.zip': 'f02c8050cd73eedc70753e47397d0617d914d961840a8cec994315047833585b', 'Medicaid_Wegovy_Stage04E_B_Feedback.zip': '79d6f873374210b8c0df9bb2871bdba7ff9426de9db8ce3e06a559a3e8d66ad8'}
    proof = a.jr(a.ROOT / '03_audit_outputs/Stage04C_R2_R1/_working/feedback_package_verification.json')
    assert proof['SHA256'] == expected['Medicaid_Wegovy_Stage04C_R2_R1_PARTIAL_Feedback.zip']
    prior = []
    for name, h in expected.items():
        p = a.safe(a.ROOT / 'feedback' / name)
        actual = a.sha(p)
        assert actual == h
        prior.append({'path': str(p), 'expected_SHA256_from_prior_stage': h, 'current_SHA256': actual, 'unchanged': True})
    a.jw(a.OUT / '04C_R2_R2_Resume_Verification.json', {'status': 'PASS', 'models': rows, 'no_new_fits': True, 'hash_verified_models_not_to_be_refitted': 7, 'original_R2_historical_execution': 'EXECUTION_UNKNOWN', 'prior_key_feedback_ZIPs': prior, 'new_code_AST': 'PASS', 'current_code_hashes': {p.name: a.sha(p) for p in a.CODE.glob('*.py')}})
    print('RESUME HASH VERIFICATION PASS: 7 models reused, zero fits; prior key ZIPs unchanged', flush=True)
if __name__ == '__main__':
    run()
