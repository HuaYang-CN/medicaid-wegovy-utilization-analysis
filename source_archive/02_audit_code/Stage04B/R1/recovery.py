"""Readonly initial Stage04B evidence, source protection and prospective R1 plan."""
from common import *
import zipfile, io
from collections import Counter

def main():
    record('recovery_before_models')
    assert not (WORK / 'recovery_before.json').exists()
    mandatory = [ROOT / 'AGENTS.md', ROOT / 'PROJECT_CHARTER.md', REG]
    mandatory += [ROOT / '03_audit_outputs/Stage03' / n for n in ['03_Stage04_Protocol_Lock.csv', '03_Stage04_Execution_Plan.md', '03_Missingness_Suppression_Protocol.md', '03_RI_Enrollment_Correction_Plan.md', '03_PPML_Separation_Convergence_Protocol.md', '03_Stage04_Decision_Gates.md']]
    mandatory += [A / ('04A_R3C_' + n) for n in ['Executive_Report.md', 'Independent_PPML_Results.csv', 'Model_Gates.csv', 'Separation_Diagnostics.md', 'Model_Input_Hashes.json', 'Quality_Assurance.md']]
    jw(WORK / 'mandatory_intake.json', [{'path': str(p), 'sha256': sha(p), 'characters_read': len(safe(p).read_text(encoding='utf-8-sig'))} for p in mandatory])
    rows = []
    found = []
    skips = []
    for sub in ['02_audit_code', '03_audit_outputs', 'feedback']:
        for base, dirs, files in os.walk(safe(ROOT / sub), followlinks=False):
            for d in dirs[:]:
                q = Path(base) / d
                if getattr(q.lstat(), 'st_file_attributes', 0) & 1024:
                    dirs.remove(d)
                    skips.append(str(q))
            for name in files:
                p = Path(base) / name
                if '04b' not in str(p.relative_to(ROOT)).lower() or p.is_relative_to(CODE) or p.is_relative_to(OUT):
                    continue
                if getattr(p.lstat(), 'st_file_attributes', 0) & 1024:
                    skips.append(str(p))
                    continue
                digest = sha(p)
                found.append({'path': str(p), 'sha256': digest})
                role = 'PRIOR_STAGE_READINESS_ONLY' if 'Readiness' in name else 'OLD_04B_ARCHIVE'
                text = safe(p).read_text(encoding='utf-8-sig') if p.suffix == '.md' else ''
                rows.append({'Path': str(p), 'Bytes': p.stat().st_size, 'SHA256': digest, 'Source': 'PRE_EXISTING_PROJECT', 'Content_check': 'Readiness document; no 04B fit/checkpoint record' if text else 'ZIP member and CRC audited separately', 'Role': role, 'Run_status': 'NOT_EXECUTED_04B_EVIDENCE' if role.startswith('PRIOR') else 'PARTIAL_ARCHIVE'})
    oldzip = ROOT / 'feedback/Medicaid_Wegovy_Stage04B_Feedback.zip'
    with zipfile.ZipFile(safe(oldzip)) as z:
        assert z.testzip() is None
        info = [{'name': i.filename, 'bytes': i.file_size, 'crc32': i.CRC} for i in z.infolist()]
        assert z.namelist() == ['Issue_Register.csv']
        b = z.read('Issue_Register.csv')
        assert b == safe(REG).read_bytes()
        rows.append({'Path': str(oldzip) + '::Issue_Register.csv', 'Bytes': len(b), 'SHA256': hashlib.sha256(b).hexdigest(), 'Source': 'OLD_ZIP_MEMBER', 'Content_check': '45 IDs; bytes identical disk register; no Stage04B results, code or checkpoints', 'Role': 'REGISTER_SNAPSHOT_ONLY', 'Run_status': 'PARTIAL'})
    directory_evidence = {'Stage04B_output_before': 'ABSENT', 'Stage04B_R1_output_before': 'ABSENT', 'Stage04B_code_before': 'ABSENT', 'Stage04_entries': len(list(safe(ROOT / '03_audit_outputs/Stage04').iterdir())), 'old_model_runs_recovered': 0, 'old_B0_B6_definition': 'NOT_FOUND_IN_AUTHORIZED_LOCAL_EVIDENCE', 'mtime_used_for_success': False, 'old_zip_members': info, 'old_zip_crc': 'PASS', 'old_register_disk_bytes_match': True, 'reparse_skipped': skips, 'scope': 'project code/output/feedback Stage04B name discovery and explicit Stage04 placeholder; no personal or history rescan'}
    assert directory_evidence['Stage04_entries'] == 0
    jw(WORK / 'recovery_before.json', directory_evidence)
    cw(OUT / '04B_R1_File_Inventory.csv', rows)
    jw(WORK / 'issue_baseline.json', rc(REG))
    protected = {str(p): sha(p) for p in mandatory if p != REG}
    protected.update({r['path']: r['sha256'] for r in found})
    for r in rc(A / '04A_R3C_Input_Manifest.csv'):
        assert sha(r['Path']) == r['SHA256']
        protected[r['Path']] = r['SHA256']
    for p in [ACODE / 'stat_core.py', A / '_working/environment_gate.json', A / '04A_R3C_Requirements_Lock.txt', A / '_working/exposure_start_fit.npz', A / '_working/exposure_start_covariance.npz', A / '_working/exposure_start_solver.json', A / '_working/exposure_start_covariance_diagnostics.json', A / '_working/effective_model.npz', A / '_working/requested_model.npz', A / '_working/solver_gate.json', A / '_working/package_verification.json']:
        protected[str(p)] = sha(p)
    jw(WORK / 'protected_before.json', [{'path': p, 'sha256': v} for p, v in protected.items()])
    lock = [r for r in rc(ROOT / '03_audit_outputs/Stage03/03_Stage04_Protocol_Lock.csv') if r['Analysis_ID'].startswith('04B-')]
    assert len(lock) == 6
    jw(WORK / 'formal_04B_lock.json', lock)
    jw(WORK / 'prospective_plan.json', {'old_checkpoints': 'No local B0–B6 definition; no retrospective completion invented', 'R1_steps': ['RECOVERY', 'ENV_INPUT', '04B-01', '04B-02', '04B-03', '04B-04', '04B-05', 'COMMON_SUPPORT', 'QA_PACKAGE'], 'source_protocol': 'Stage03 v1.1 + explicit current user Stage04B-R1 authorization', 'period': 'DATA-11 including2024Q1', 'policy': 'P1 fixed46,12/34', 'model': 'F0; log total Medicaid enrollment; state-product FE, quarter FE, PA,PG,DDD', 'R0': 'NOT_VERIFIABLE_NO_FROZEN_OFFICIAL_REVISION; use R1 without network', 'donor': 'NOT_EXECUTED; prior optional authorization/conditions not found; not main analysis', 'families': {'POP_RI': ['R3_M0_MID', 'R1_M0_MID'], 'R2_vs_R1': ['R1_M0_MID', 'R2_M0_MID'], 'PARTIAL_vs_R1': ['R1_M0_MID', 'R1_PARTIAL_M0_MID'], 'M0_M1': ['R1_M0_MID', 'R1_M1_MID'], 'SUP_M0': ['R1_M0_S0', 'R1_M0_MID', 'R1_M0_S10'], 'SUP_M1': ['R1_M1_S0', 'R1_M1_MID', 'R1_M1_S10', 'R1_M1_S11', 'R1_M1_S25', 'R1_M1_S50', 'R1_M1_POS10_NEG0', 'R1_M1_POS0_NEG10']}, 'COMMON_rule': 'native certified keys intersection; union certified further separated keys; iterate at most10 before any fitting; no P or beta criteria'})
    md('04B_R1_Recovery_Audit.md', '# Stage04B-R1 初始恢复取证\n\n2026-10-13 Asia/Shanghai。限定本项目Stage04B相关名称、明确目录及反馈档案，跳过reparse；未扫描个人目录或重新盘点DATA。原标准Stage04B输出/代码目录未见，Stage04占位目录空。发现11个旧阶段04B readiness及其解压副本，全部只是准备状态，无04B模型运行证据；另发现旧Stage04B ZIP，CRC通过，唯一成员Issue_Register.csv与磁盘逐字节匹配，只有45项登记。没有从ZIP单独推断缺失，结论来自目录/代码/日志/缓存名称取证的合并证据。\n\n在授权本地范围未找到旧Analysis_ID/Variant_ID运行或B0–B6正式定义。旧计算完成状态NOT_VERIFIABLE，不能造历史COMPLETE记录。标准交付物缺失被确认，本轮只执行当前明确授权且Stage03覆盖的04B-01至05必要任务。所有执行记录将标本轮新执行，不称恢复了不存在的旧结果。OPTIONAL donor未见此前授权/前提，保持NOT_EXECUTED。\n\n权威文件及源输入字节保护见本地protected_before；原基准是1001有效支持VALID_EFFECTIVE_SAMPLE_RESULT，完整1012有限FE不成立。本轮没有执行04C/04D/04E，也不改稿。\n')
    print('RECOVERY: no local old04B model/code/checkpoint; oldZIP register-only verified; formal missing tasks eligible for R1 resume')
if __name__ == '__main__':
    main()
