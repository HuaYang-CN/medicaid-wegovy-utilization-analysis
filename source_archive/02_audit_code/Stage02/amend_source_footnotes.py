"""Incorporate newly checked enrollment footnotes into current Stage02 drafts.
Original historical outputs and original issue columns other than authorized status untouched.
"""
from pathlib import Path
import csv, json
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '03_audit_outputs/Stage02'

def rows(p):
    with p.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def replace(p, old, new):
    s = p.read_text(encoding='utf-8')
    assert old in s, p
    s = s.replace(old, new)
    p.write_text(s, encoding='utf-8')
paragraph = '\n额外来源脚注QA确认，选定4284月份中374条total_medicaid_enrollment脚注非空，不同州存在范围或时间计数例外。主46州窗口内包括31条“includes limited-benefit”、77条“any time in month, not point-in-time”、6条缺部分full-benefit non-MAGI、25条retroactive以及RI1条系统缺失。retroactive本身不自动违反CMS定义；其余脚注表明实际各州数值不能一概宣称严格相同的综合福利/月末人口。02_Enrollment_Source_Footnote_QA.csv列374条去身份州月份诊断。代码忽略全部脚注，现有“月份齐全/数值完整”不能替代人口口径一致。后续需有证据的州级口径/历史修订或敏感性方案，不未经授权修值。此扩展纳入S02-001忽略脚注风险，不把每条脚注都定为错误。\n'
p = OUT / '02_Enrollment_Definition_Audit.md'
s = p.read_text(encoding='utf-8')
p.write_text(s + paragraph, encoding='utf-8')
replace(OUT / '02_Executive_Audit_Summary.md', 'Adult字段大量缺，FFS直接匹配人口缺。RI占位0需另处理。', 'Adult字段大量缺，FFS直接匹配人口缺。该字段目标定义与州实际脚注例外须分开；主窗31个月含limited-benefit、77个月为月内任何时点，RI占位0需另处理。')
replace(OUT / '02_SDUD_Source_Audit.md', '8个数据提取文件（含enrollment）的SDUD七项哈希已检查一致。', '8个数据提取文件（含enrollment）的行数与保存manifest哈希已检查一致。')
replace(OUT / '02_SDUD_Source_Audit.md', '64个观察NDC见02_NDC_Product_Mapping.csv，', '全部38375源行NDC均为11位数字且与三段拼接一致。64个观察NDC见02_NDC_Product_Mapping.csv，')
paths = [ROOT / '03_audit_outputs/Issue_Register.csv', OUT / '02_Stage02_Issue_Register_Snapshot.csv']
for p in paths:
    rs = rows(p)
    r = next((x for x in rs if x['Issue_ID'] == 'S02-001'))
    r['Issue_Description'] = 'Enrollment脚注未处理，RI缺失编码0纳入主窗口季度分母'
    r['Stage02_Evidence_Now'] += '；另外主窗31个月limited-benefit、77个月月内任时点population脚注未处理；实际州口径非完全一致'
    with p.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rs[0]))
        w.writeheader()
        w.writerows(rs)
for n in ['02_Issue_Status_Changes.csv', '02_P0_Resolution_Matrix.csv']:
    p = OUT / n
    rs = rows(p)
    r = next((x for x in rs if x['Issue_ID'] == 'S02-001'))
    r['Evidence_Now'] += '；主窗口其他population/time口径脚注见02_Enrollment_Source_Footnote_QA.csv，不能把字段目标定义当各州实际完全一致'
    with p.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rs[0]))
        w.writeheader()
        w.writerows(rs)
print('Stage02 enrollment footnote exceptions integrated; historical reports not edited')
