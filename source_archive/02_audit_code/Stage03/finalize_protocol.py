"""Post-freeze synthesis, deterministic protocol amendments, no models."""
from reports_ab import ROOT, OUT, HEADER
from preflight import digest
import csv, json

def readcsv(p):
    with p.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def putcsv(p, rows):
    with p.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def append(name, text):
    p = OUT / name
    p.write_text(p.read_text(encoding='utf-8') + '\n\n## 协议修订 v1.1，冻结审查后的最终规则\n\n' + text.strip() + '\n', encoding='utf-8')

def main():
    reviews = [OUT / f'_working/Reviewer{i}_Frozen.md' for i in (1, 2, 3)]
    freeze = {p.name: digest(p) for p in reviews}
    assert all((p.stat().st_size > 500 for p in reviews))
    (OUT / '_working/reviewer_freeze_hashes.json').write_text(json.dumps(freeze, indent=2), encoding='utf-8')
    inputs = json.loads((OUT / '_working/review_packet_hashes.json').read_text(encoding='utf-8'))
    assert all((digest(ROOT / p) == h for p, h in inputs.items()))
    support = '\n最终规则优先于v1中“完整可报告总体”简写。M1仅是冻结提取内的reportable matched cells，不证明CMS真实上报完整。定义V_st为R0/R1季度人口有效指示；C_stpu为该提取中有≥1条可映射合法源行且所有该产品渠道行状态可解释，或有官方该渠道不适用/真实零依据。R_st=V_st×∏_{p∈{W,O},u∈{FFSU,MCOU}}C_stpu。未知缺源、未映射、非法值或未决重复不能C=1。\n\n04C-01主β是指定P1、赋值情景、R_st=1并排Q1的有限观察集合上PPML条件均值投影，不是固定“始终可报告州”ATT。各期S_gt可变化，输出组季名单与前后共同州；不假称missing at random。若作因果解释，还需事件世界报告选择R^1/R^0稳定或新识别方法，此证据不足，维持B。\n\n同支持比较先锁数据规则再执行，不按β/P选择：以主R_st清洁窗口为BASE；在FE或suppression等同一科学family内先按正式separation证书得到各native有效键，COMMON为各成员键交集，再在COMMON重验每模型目标support/分离。若需要进一步剔除，用已预设certificate删除键的并集迭代至不再变，保存每步理由，最多10轮，未稳定则COMMON比较NOT_VERIFIABLE。同时保留native与COMMON各run；共同样本无法估时不能声称同一目标稳健。COMMON不得因效应或显著性删行。\n\n04C-02必须输出EV-CLEAN（排Q1、refQ4）在主BASE/相同effective support上的动态与cleanpre联合；EV-TRANS（保留Q1单独交互）另列native，非主同sample验证。04C-06的51/P2变化是不同目标总体比较，不能声称相同estimand复现；原46与扩充51也另给共有46子集结果而不删扩充结果。组季观察组成是证据，不证明选择无偏。\n'
    append('03_Missingness_Suppression_Protocol.md', support)
    append('03_Estimand_Definition.md', support)
    append('03_Independent_Replication_Spec.md', '\n环境更正补充：PATH exact Python `external_resources/python.exe` 已以-I -B标准库元信息核验为3.13.5，numpy/pandas/scipy/statsmodels/matplotlib/patsy均NOT_INSTALLED。bundled3.12.14与其分开，原环境仍NOT_VERIFIABLE；此前仅PATH发现但未终结返回，现元信息完整。不扩大环境目录扫描或安装。\n\n确定输入合同：旧04A面板为DATA/processed/state_quarter_brand.csv；分渠道为processed/state_quarter_brand_utilization.csv。源SDUD为Stage02/02_Source_File_Register.csv列明七年度文件，人口为raw/enrollment/cms_monthly_enrollment_2019_2025.csv，政策为三已索引快照及冻结Stage02裁决。精确现SHA已登记，04A再确认，不读未索引新历史文件。\n\n源键=(state,year,quarter,11位ndc,utilization_type)，ND C三段作为字符串保留前导零，fileSHA/source_row_index仅lineage而非第二份处方。冻结版本以source register/hash指定，不依据mtime择最新；若出现跨文件修订同键或同版本重复，默认HARD STOP并登记，不自行去重/累加。明确官方修订版本与被替代版本时先审批固定一种版本，保留差异ledger。\n\n产品映射冻结Stage02/02_NDC_Product_Mapping.csv与processed/ndc_brand_crosswalk.csv hash，使用已观察NDC/name/analytic_brand交叉核验，仅支持已提取记录；64个观察NDC不是历年完整目录。映射冲突/未映射保留UNMAPPED，主产品相关异常未定位前不聚合；不丢弃未知行，也不追认历史未返回NDC不存在。真实有效期/厂家全历史未知登记NOT_VERIFIABLE，不新造日期。\n\n每源文件逐行partition raw→eligible(51边界/指定产品/窗口) +明示excluded(XX/PR/窗口等) +unmapped/invalid/unresolved-duplicate；各partition互斥且覆盖全部读入行。状态六类互斥且有source flag/数量/日期证据；suppressed数量未知，不等于invalid。按group/product/quarter/channel导出source presence、suppressed、missing和行覆盖核对。两套实现需分别从同冻结raw和映射规则生成ledger并比源覆盖/数量/状态，再比较聚合；不能只共享一张ledger验证自身。Stage03没有执行这些源重建。\n')
    append('03_Policy_Exposure_Strategy.md', '\nP2裁决字典固定为2024-03-07有效的“Wegovy肥胖用途、常规FFS成人福利”环境，G=1为明确该用途不覆盖；不是GLP1类别、CVD或所有MCO暴露。COVERED_ROUTINE与COVERED_ROUTINE_RESTRICTED（二者覆盖组）要求文件明确Wegovy该用途可通过常规申请/PA获得覆盖，PA/BMI/step therapy限制另存，不当不覆盖。EXCLUDED_OBESITY明确该用途排除才G=1；EXCEPTION_ONLY（个案特殊许可且不能证明常规福利）、产品不明class-only、冲突、日期不足保持UNKNOWN不入二组。覆盖不是全民无条件用药，适用人群仍另标。\n\n日期判据先看官方生效/撤销且覆盖基准日的产品PDL/PA和更正文件，再看dated official bulletin；公告未来计划不代有效期，survey/发表/下载日不代生效日。两个官方来源冲突且无更正优先证据=UNKNOWN，不能按有利组别挑文件。逐州输出policy dictionary rule_ID、product/indication/channel/population、restriction、valid_from/to、source/hash/location、adjudication_reason。P2证据可得子总体和排未知本身有选择限制，不是可靠全51重分类。P1原分类不回写。\n')
    lag = '\n唯一lag敏感性编码EL-1：Q1排除；2023Q2/Q3/Q4为pre（参考Q4）；E_t=1仅2024Q2；L_t=1自2024Q3至2025Q4。公式logμ=logN+α_sp+λ_t+θ_EA E A+θ_EG E G+β_E E A G+θ_LA L A+θ_LG L G+β_L L A G。E与L纯时间项被quarter FE吸收，两组/两产品下阶项全部保留。FFSU/MCOU共享EL-1，但原paid/dispense字段不变。\n\n“Q3 late锚”最终只指上述L，不另将Q2当pre。没有独立Q3 binary recoding方案，不能重复计为另一次验证。若未来想排Q2另做延迟窗口须新版本先批，不自动执行。β_E与β_L是预设early/late关联，不代表测得真实行政延迟。\n'
    append('03_Event_Time_Adjudication.md', lag)
    append('03_FFS_MCO_Design_Protocol.md', lag)
    joint = "\n联合约束统一：保存原R行数/rank及每行可估性；仅纯代数冗余且能证明与原H0等价才用预先保存的独立行变换去冗余。对原独立q个假设，要求RVR'数值rank=q且正方差，才F(q,G−1)近似。独立约束cov奇异/不可估→原joint NOT_VERIFIABLE，禁止通过减q或pinv称原H0通过。可估子空间检验若另批报告必须新H0与新标签，不作原joint支持。\n\nEV-CLEAN full family为2 clean leads+7post=9个非参考DDD；EV-TRANS为前述9+Q1 transition=10。各family分别Bonferroni双侧95%同时区间，临界t_{G−1}(1−0.05/(2m))，m固定9或10；同时也保留逐点95%。若任一目标不估，完整family同时区间NOT_VERIFIABLE，不删点缩family。不同赋值/FE情景各完整报告，不把其中显著点挑作共同验证；bootstrap max-t未验证不临时替代Bonferroni。\n\n趋势功效最小锁：clean lead k=(-4,-3)，ref k=-2；给定每季log差异斜率d∈{0,±0.10,±0.25}，h_d=(-2d,-d)。使用clean lead 2×2V与λ=h_d'V^{-1}h_d、α=0.05，报告noncentral-F(2,G−1,λ)对主F拒绝域的plug-in近似功效；仅当V完整可估，不拼边际SE。它是估计V条件下的可检测性，不是实证功效保证。post偏离另定义δ_k=d(k+2)与β_k−δ_k情景，相对Q4累积、保持同V仅是假定偏离已知的外推展示，不当稳健因果置信界。Stage03未计算任何λ/功效/效果。\n"
    append('03_Parallel_Trend_Protocol.md', joint)
    append('03_Cluster_Inference_Plan.md', joint + '\n\nG_BOOT输出补锁：仅验证后的restricted PPML有效nuisance-adjusted score及其studentized绝对统计量T才适用；两侧按|T*|≥|Tobs|（等号计尾），p=(1+尾部复制数)/(9999+1)。同seed/同州权重矩阵复用于null inversion，Rademacher主、Webb敏感均全报。任一复制非finite/算法失败不静默剔除或补新的seed；该bootstrap输出FAIL/NOT_VERIFIABLE并保留失败数，CR1/t不替换。\n\n条件方法通过后scalar confidence set以p>0.05为接受，初始β0∈[-8,8]、步长0.01，若边缘仍接受按2倍扩至最多[-64,64]，边界搜索二分tol1e-4/max50步并保存全部restricted fit诊断。不连通接受集逐段报告，不强造单区间；超过搜索边界标未界定/NOT_VERIFIABLE，不假称有限。MonteCarlo SE按sqrt[p(1−p)/10000]，不是模型SE。以上输出约定不证明本地PPML bootstrap实现有效，实际G_BOOT仍NOT_VERIFIABLE，代码/方法独立审阅通过前不能计算或承诺bootstrap CI。\n')
    append('03_PPML_Separation_Convergence_Protocol.md', "\n尺度锁：c_j=max(1,max_i|X_ij|)，Xscaled_j=X_j/c_j；结构rank用规范化Xscaled的SVD门槛max(n,k)εσmax。weighted Z=diag(sqrtμ)Xscaled另按同式给rank/condition，要求在结构可估空间rank=r，不能把weighted信息丢失当纯dummy冗余。条件数用该空间σmax/σmin；bread实现映回原系数规范化。LP d各项free（不使用默认nonnegative bounds），zero normalization约束按上述证书，保存feasible direction及残差。\n\nObjective主用Poisson deviance，单步relative=|D_new−D_old|/(1+|D_old|)，仍要求末5步≤1e-10及scaled score≤1e-8；loglik为支持性保存，不另挑较宽松指标。协方差symmetry范数比||V−V'||2/max(||V||2,ε)≤1e-10；PSD λmin(Vsym)≥−1e-10 max(||Vsym||2,ε)，仅数值级负特征保留说明，任何目标方差≤0仍FAIL，不裁为0。μ跨实现逐元素|μa−μb|≤1e-8+1e-6|μref|，无“小均值”任意分段阈值。合法参数SE和cov容差沿原条款。\n")
    append('03_Figure2_Reconstruction_Spec.md', '\n新图caption用“按历史稳定环境规则选定的46辖区”，附July固定标签及后续class-change排除、全窗实际稳定性NOT_VERIFIABLE，不把stable-policy简写当事实。F2-L11历史假设与F2-R11修正/strict-request/observed-support都覆盖完整11季且保留Q1作为描述点；F2-M10是主模型same-support的10季、Q1明确gap，不自动把模型窗口套原图重建。每Variant_ID单独requested/included州集、日期集合及baseline hash；unknown full46点NA。\n')
    upgrade = '\n当前Stage04所有结果始终默认B关联；A不属于已锁可自动进入分支。任何强解释升级须另行授权版本化识别审查，并先指定实际裁决责任人、记录证据与反对理由，不声称本次外部专家已参与。数值PASS、P1-51差别小、负控阴性或诊断数量均不自动升级。\n\n| 目标 | 必需来源/假设 | 诊断能支持但不能证明 | UNKNOWN处理/审批 |\n|---|---|---|---|\n| P1/P1-51条件关联 | July身份、选择/报告样本、有效数值 | 组成/时间/FE/情景 | 不做因果升级，保持B |\n| P2固定事件前环境的四项FDA事件效应差异 | dated P2；无事件乘法差异趋势；报告选择跨世界稳定；无差异同期冲击/提前反应 | cleanpre/窗口/供给和PA史/渠道 | 任一核心unknown保持B；须另审固定总体与反事实 |\n| Wegovy事件效应两组差异 | 上行全部+Ozempic两组事件效应相消的独立依据 | 合计利用/替代产品只能挑战，不证明相消 | 无相消依据不得省略τ_O，另批目标声明 |\n| 州覆盖政策实施效果 | P3产品用途渠道确切有效日期、政策变化识别设计、选择与内生处理/异质性规则 | 动态描述/同日变化不是随机处理 | 当前未锁可拟合设计，另方案授权；不能用FDA DDD代替 |\n\n患者access/equity效果需新资格/唯一患者/需求/拒付数据，不属于上述升级。所有升级责任与证据判断应在新强主张发表前单独形成记录，不能从结果大小倒推。当前P2/P3史缺失及报告机制不足保持NOT_VERIFIABLE。\n'
    append('03_Research_Design_Adjudication.md', upgrade)
    append('03_Stage04_Decision_Gates.md', upgrade)
    append('03_Stage04_Execution_Plan.md', '\n所有04B主要组件诊断均采用原11季（DATA-11）；04B-04/05不在该子阶段自动套clean窗口。clean再应用在04C主BASE的预设情景（DATA-C10），作为已经锁定的窗口×数据组合敏感性，全部报告而非选择。每Variant_ID写Analysis_ID/variant、exact季度集合、source/scenario/R/M/FE/support hashes和inherited baseline。04E的F2-L11/R11/M10按专项图条款，不等同模型default Period。\n\n审查修订合同已补齐reportability/共同支持、源键和映射、P2字典、EL-1完整下阶项、联合原H0、Bonferroni family、数值尺度和因果目标审批。原v1和三份冻结报告都保留；无统计数值执行。\n')
    assumptions = readcsv(OUT / '03_Causal_Assumption_Register.csv')
    desc = {'CA01': '差异平行趋势未获充分支持，潜在偏倚未验证', 'CA02': '比较产品差异事件溢出可能无法相消', 'CA03': 'Q1部分事件与提前响应风险', 'CA04': '完整事件前政策史未验证', 'CA05': '未来筛样可能改变反事实总体', 'CA06': '已确认渠道时钟/范围不完全匹配，影响未验', 'CA07': '缺源报告机制未验证，R跨事件世界稳定未证', 'CA08': '已确认共同隐匿值不能构成secondary严格界', 'CA09': '已确认RI分母占位零及州脚注口径风险', 'CA10': '有限解/目标可估及实际协方差未验证', 'CA11': '有限簇不平衡与跨州依赖风险', 'CA12': '已确认处方测量不能直接识别患者公平'}
    for r in assumptions:
        r['Issue_Statement'] = desc[r['Assumption_ID']]
        r['Status_Semantics'] = 'Status is ISSUE status, not assumption satisfied'
        r['Assumption_Support'] = 'NOT_VERIFIABLE for full scientific assumption; see Issue_Statement'
    putcsv(OUT / '03_Causal_Assumption_Register.csv', assumptions)
    lock = readcsv(OUT / '03_Stage04_Protocol_Lock.csv')
    for r in lock:
        if r['Analysis_ID'] not in ['04A-01', '04X-01']:
            r['Dataset'] = 'DATA/processed/state_quarter_brand.csv; channel=processed/state_quarter_brand_utilization.csv; Stage02 source register indexed raw SDUD/enrollment/policy; v1.1源合同及04A exact hashes'
        if r['Analysis_ID'] in ['04B-04', '04B-05']:
            r['Period'] = 'DATA-11：2023Q2–2025Q4含Q1，隔离数据情景；clean DATA-C10组合仅在04C全部另标'
        if r['Analysis_ID'] == '04C-02':
            r['Period'] = 'EV-CLEAN排Q1/ref2023Q4主同支持；EV-TRANS保Q1单独、同ref独立native；k0=2024Q2'
            r['Expected_Output'] += '；v1.1原独立q约束cov必须fullrank；Bonferroni9/10点family；COMMON/native支持分列'
        if r['Analysis_ID'] in ['04C-03', '04D-02']:
            r['Fixed_Effects'] = 'SP+quarter；EL-1 EA/EG/EAG及LA/LG/LAG全部下阶；Q2early/Q3late；Q2永不pre'
            r['Model'] = 'PPML EL-1 early/late完整公式；固定窗另F0；没有独立Q3 recode验证'
        if r['Analysis_ID'] == '04E-01':
            r['Period'] = 'F2-L11/R11完整2023Q2–2025Q4含Q1；F2-M10主same-support排Q1且gap'
        if r['Analysis_ID'] == '04C-06':
            r['Exposure'] += '；P2最终字典Wegovy obesity routine FFS adult，exception-only/日期冲突unknown'
        if r['Analysis_ID'] == '04C-01':
            r['Estimand'] = '给定P1/M1/R_st=1及clean窗口的有限观测集合PPML投影；非固定always-reportable ATT'
        if r['Analysis_ID'] in ['04C-01', '04C-02', '04C-05', '04C-06']:
            r['Data_Handling'] += '；v1.1 COMMON/native成对支撑规则；不同population不当同目标复现'
    putcsv(OUT / '03_Stage04_Protocol_Lock.csv', lock)
    priority = readcsv(OUT / '03_Stage04_Analysis_Priority.csv')
    by = {r['Analysis_ID']: r for r in lock}
    for r in priority:
        r['Scientific_Rationale'] = by[r['Analysis_ID']]['Scientific_Question'] + '；' + by[r['Analysis_ID']]['Estimand']
    putcsv(OUT / '03_Stage04_Analysis_Priority.csv', priority)
    issues = readcsv(ROOT / '03_audit_outputs/Issue_Register.csv')
    fields = list(issues[0])
    changes = readcsv(OUT / '03_Issue_Status_Changes.csv')
    new = [('S03-001', 'Reporting support and source contract', '提取可报告配对投影、COMMON/native与raw映射实现一致性待验证', 'R1-M1；R3-M2', '未知报告选择影响及源版本/映射实现仍未执行', '04B源合同/共同支持ledger；04C同支持比较；04E独立raw链'), ('S03-002', 'Policy/time/causal upgrade decision', 'P2字典、EL-1下阶项与目标专属强解释裁决实现待验证', 'R1-M2；R2-M1/M2/M3', '原政策全史/实际lag/反事实支持仍NOT_VERIFIABLE', '04C/04D按v1.1编码；任何A升级另行版本审查'), ('S03-003', 'Numerical/output diagnostic contract', '联合H0秩、数值尺度/时间variant/同时区间及bootstrap方法实现待验证', 'R3-M1/m1/m2/m3；R1-m1', '实际solver/cov/bootstrap适用与功效未执行', '04A数值gate代码审阅；04C原约束joint/Bonferroni；G_BOOT验证')]
    for id, domain, description, evidence, uncertainty, test in new:
        assert id not in {r['Issue_ID'] for r in issues}
        r = {k: '' for k in fields}
        r.update(Issue_ID=id, Stage='Stage03', Domain=domain, Severity='P1', Status='CONFIRMED', File='Stage03 reviewed_protocol_v1 and final v1.1', Location=evidence, Evidence='冻结独立审查确认v1细则不足；v1.1已补文本，实际实现未验证', Issue_Description=description, Scientific_Impact='可复现性/解释风险，原效果方向大小未验证', Confidence='HIGH_CONFIDENCE', Required_Verification=test, Recommended_Action=test, Why_Problem=uncertainty, Needs_New_Analysis='Stage04 authorized implementation verification', Revision_Type='TYPE B; TYPE C', Priority='P1', Next_Stage='Stage04 separately approved', Reviewer_Local_ID=evidence, Stage03_Decision='v1.1补锁；PLAN_IMPLEMENTATION_PENDING，未标RESOLVED', Current_Evidence='已补确定规则，冻结旧版和独立反对意见保留', Remaining_Uncertainty=uncertainty, Stage04_Required_Test=test, Acceptance_Criterion='实现者按最终规则产生同一mask/编码/原H0与输出；各数值gate实际通过', Scientific_Claim_Restriction='不把方案补齐当成结果有效或因果已证', Stage03_Date='2026-10-12')
        issues.append(r)
        changes.append(dict(Issue_ID=id, Old_Status='NOT_APPLICABLE_NEW', New_Status='CONFIRMED', Old_Severity='NOT_APPLICABLE_NEW', New_Severity='P1', Change_Type='NEW_ISSUE', Reason='独立审查确认的协议实现风险；文本补齐但执行验证未做', Evidence=evidence, Date='2026-10-12'))
    putcsv(ROOT / '03_audit_outputs/Issue_Register.csv', issues)
    putcsv(OUT / '03_Issue_Register_Snapshot.csv', issues)
    putcsv(OUT / '03_Issue_Status_Changes.csv', changes)
    synthesis = '\n## Cross-review synthesis，三报告冻结后主审计综合\n\n三者均支持当前B关联解释和单独审批04A准备，没有新增Blocking Yes；这不是数值或因果PASS。\n\n| 综合键 | 独立实际来源 | 最终处理与边界 |\n|---|---|---|\n| 因果目标升级规则 | R1-M2、R2-M3 | 共识；目标专属表及另批版本审查，P1/P1-51/negative不自动升级 |\n| 假设Status语义 | R1-m2、R2-m1 | 共识；CSV加Issue_Statement/Status_Semantics，状态表示问题确认，不是假设成立 |\n| 观察/源支撑 | R1-M1、R3-M2关注连接不同层 | 部分重叠，保留不同问题层；R_st投影、COMMON/native及原源partition/mapping合同 |\n| 滞后/政策字典 | R2-M1/M2 | 单审查者具体意见；EL-1完整下阶及P2产品用途/限制/冲突字典 |\n| 联合/数值/输出方法 | R3-M1/m1/m3 | 单审查者具体意见；原独立约束fullrank，尺度与Bonferroni9/10族、bootstrap输出门控 |\n| 窗口与功效 | R3-m2、R1-m1，各不同层 | DATA-11/C10、F2-L11/R11/M10和h_d/V近似功效/外推区别 |\n\n所有冻结报告没有回改；正式v1.1增补确定规则，旧v1字节已归档。没有把已形成计划当历史科学问题RESOLVED。新增S03-001/002/003均P1 CONFIRMED，描述待执行实现一致性，原42和10P0完全保留。\n\n## Forensic consistency，主审计独立层\n\nAUD-01 aggregation_ambiguity，源R_st与same-support原不足；按v1.1明确提取内投影及COMMON/不同总体标签。实际选择偏倚not_assessable，不冒充算出偏倚。\n\nAUD-02 confirmed_internal_error，原联合奇异规则与有效q规则冲突（R3-M1）；最终原独立约束必须rank=q，纯代数冗余须证明等价，不能pinv/减q替原H0。\n\nAUD-03 confirmed_internal_error，04B/04E锁表Period继承default与专项window不一致（R3-m2）；最终Variant_ID/日期集合纠正，未执行任何模型或率。\n\nAUD-04 passed bounded，4.09在全部报告均历史MATCHED_SAVED_OUTPUT；原/修正/敏感与失败标签分开。未复算IRR/CI/P、group率或Gini，所有算术科学核验not_assessable。\n\nAUD-05 passed bounded，术语checker两warning：MATCHED_SAVED_OUTPUT是证据级，ORIGINAL_SAVED_RESULT是产物身份，允许并存；0.1 rank阈值倍率与0.10趋势斜率为不同量，不误改数字。无数值精度矛盾。\n\nAUD-06 provenance_gap，原exact run/environment/Figure2生成链未恢复；新PATH3.13.5仅元信息，无分析依赖，不能替手稿3.12环境。科学未知继续保留。\n\n此层未反馈给reviewer，也不将单个审查意见或主审计发现冒称三方共识。原数据缺陷影响、复现/因果/临床有效仍未验证。Nature新颖性、二区分区或接收判断不由本包确立。\n'
    report = '# Stage03独立反对意见及冻结后综合\n\n' + HEADER + '\n三份报告在独立隔离上下文形成，各只读同29文件包和预指定emphasis；不是真实外部专家参与。以下原文保持冻结。\n\n'
    report += '\n\n'.join((p.read_text(encoding='utf-8') for p in reviews)) + synthesis
    (OUT / '03_Independent_Reviewer_Challenges.md').write_text(report, encoding='utf-8')
    amendment = {'version': 'v1.1', 'reviewer_hashes': freeze, 'initial_packet': inputs, 'amended_files': {p.name: digest(p) for p in OUT.glob('03_*.md')}, 'changes': 'only Stage03 protocol and authorized global register; reviewed v1 preserved', 'models_executed': False}
    (OUT / '_working/protocol_amendment_record.json').write_text(json.dumps(amendment, indent=2), encoding='utf-8')
    p = OUT / '_working/execution_log.md'
    p.write_text(p.read_text(encoding='utf-8').replace('Four A documents and five B documents/one assumptions CSV', 'Three A Markdown reports/one assumptions CSV and five B Markdown reports') + '\nPost-freeze finalize_protocol.py completed: v1.1 rules and synthesis only; 3 new P1 implementation risks. No historical P0 status changed.\n', encoding='utf-8')
    print('Final protocol v1.1 saved; three frozen reviews preserved; issue register 45 rows, original 42 unchanged.')
if __name__ == '__main__':
    main()
