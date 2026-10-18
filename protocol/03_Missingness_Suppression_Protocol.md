# 缺源与隐匿的预设处理

审计日期 2026-10-12（Asia/Shanghai）。Stage03 仅统计设计审计与后续规格锁定，所有拟分析均 NOT_EXECUTED。原结果为 ORIGINAL_SAVED_RESULT / MATCHED_SAVED_OUTPUT，未独立复现。稿件身份 PROVISIONAL_CURRENT_VERSION，VERSION_AMBIGUOUS。

证据根目录：本项目 `03_audit_outputs/Stage01`、`Stage02`；历史源根为 `external_data`。下文 E01=Stage02/02_PPML_Code_Audit.md；E02=02_Missing_Zero_Suppression_Audit.md；E03=02_Enrollment_Definition_Audit.md；E04=02_Policy_Source_Audit.md及02_State_Policy_Adjudication.csv；E05=02_FFS_MCO_Consistency_Audit.md；E06=02_Current_Figure2_Source_Audit.md；E07=02_Original_Result_Lineage.md。证据等级 STATIC_CODE_VERIFIED / SOURCE_VERIFIED 只涉及代码或来源事实，不能替代科学有效性。原执行连接 INFERRED，版本可信度 MEDIUM_CONFIDENCE，确切运行版本 UNKNOWN。

E02数值沿用：36503州级源行，9989 suppressed；主563渠道缺源单元；89合并Wegovy观察两渠道均缺源；AK-Wegovy11季缺源。这些层级不得相加或把563当模型行。六状态源级单独记录，合并指标可含多个状态，不能用一个“0”覆盖原因。

| 状态 | 判据 | 未来处理 |
|---|---|---|
| OBSERVED_POSITIVE | 来源存在、未隐匿且数量>0 | 保留观察值 |
| OBSERVED_ZERO | 来源存在未隐匿且明确0，或官方确认该单元真实零并保留依据 | 保留零；本冻结源Stage02观察此类0行，不将缺源追认为observed |
| SUPPRESSED | 来源存在且CMS隐匿标记 | 数量未知；单独情景，不与缺源相加赋同机制 |
| MISSING_SOURCE_RECORD | 理应可能上市的channel网格无源 | NA；报告原因待核，不fill0作为事实 |
| STRUCTURAL_NOT_ON_MARKET | 可靠批准/商业上市证据覆盖整季度 | 对FDA主窗口不得凭首次州记录判结构零；整季上市前可排除非在市目标 |
| UNKNOWN | 状态/日期/渠道可报告性无法判定 | NA及拒绝全总体推断 |

主缺源策略M1：未证实可报告无利用的渠道缺源保持missing。只有双产品各渠道都有可解释的报告状态（positive、observedzero或suppressed；官方证明该州季渠道不适用/零报也可有独立依据）才形成完整合并产品。若任一产品有未解释渠道缺源，排该state-quarter两个产品的组合观察，保留配对支持。不要只删Wegovy留Ozempic；不排整州以求显著。结果只能代表可报告配对观察子总体，缺失非随机时不代表原46完整总体，complete-pair并非缺失机制修复。实际可用n/簇/组/季度在04B展示，不预造。

主分析仅指定的suppression中点5.5为历史一致的操作性假设，不称unbiased、官方实际数或可验证均值。原M0全部缺源0只保留复现/假设情景；支持M2为官方逐单元确认零后扩充，资料不足不执行扩充；M3按可报告子样本与原零情景比较并给选择限制。若无法形成组×产品×前后支持或关键效应完全依赖未知机制，暂停全46主量，退回已观察利用描述。

SUPPRESSED共同值0/5.5/10各赋源NDC行，再聚合，均保留全部结果。CMS secondary suppression使部分真实值可能>10，不能称strict count bounds或IRR bounds。主中点处理仍残留secondary风险，不以共同情景方向一致宣称解决。

额外固定stress grid在04B：未知隐匿行共同11、25、50，标签UNSUPPORTED_SECONDARY_STRESS（选择11反映超过原10，25/50为审计假设，无已证最大值）；两种组×产品×pre/post差异赋值，背景行5.5，差异对比符号为G×A×P三阶八格正格赋10/负格0以及交换0/10；各项独立保留，不称最小最大效应或secondary完整范围。缺源missing不直接套这些源行suppression值。

缺源最差情景没有来源支持上限，因此无有限数学最差界。可做假设性state-product缺源值0、同组同产品同季已观察渠道中位数、以及其中位数2倍作为OPTIONAL stress，明确基于被观察机制/选择、不是真实插补或正式上下界；若donor不存在不插补。无来源不能将其作为修正主结果。不得用推测隐匿或未知缺源得出“所有合理情况均稳健”。

保留source_row_key、NDC、channel、flag、status、scenario、missing原因、可报告性依据和aggregation ledger；Figure2组率如果有未知渠道，完整46点为NOT_VERIFIABLE，不能只sum非缺失分子配全部人口。完整配对支持下图另标样本变化。来源核实优先于模型复杂化。


## 协议修订 v1.1，冻结审查后的最终规则

最终规则优先于v1中“完整可报告总体”简写。M1仅是冻结提取内的reportable matched cells，不证明CMS真实上报完整。定义V_st为R0/R1季度人口有效指示；C_stpu为该提取中有≥1条可映射合法源行且所有该产品渠道行状态可解释，或有官方该渠道不适用/真实零依据。R_st=V_st×∏_{p∈{W,O},u∈{FFSU,MCOU}}C_stpu。未知缺源、未映射、非法值或未决重复不能C=1。

04C-01主β是指定P1、赋值情景、R_st=1并排Q1的有限观察集合上PPML条件均值投影，不是固定“始终可报告州”ATT。各期S_gt可变化，输出组季名单与前后共同州；不假称missing at random。若作因果解释，还需事件世界报告选择R^1/R^0稳定或新识别方法，此证据不足，维持B。

同支持比较先锁数据规则再执行，不按β/P选择：以主R_st清洁窗口为BASE；在FE或suppression等同一科学family内先按正式separation证书得到各native有效键，COMMON为各成员键交集，再在COMMON重验每模型目标support/分离。若需要进一步剔除，用已预设certificate删除键的并集迭代至不再变，保存每步理由，最多10轮，未稳定则COMMON比较NOT_VERIFIABLE。同时保留native与COMMON各run；共同样本无法估时不能声称同一目标稳健。COMMON不得因效应或显著性删行。

04C-02必须输出EV-CLEAN（排Q1、refQ4）在主BASE/相同effective support上的动态与cleanpre联合；EV-TRANS（保留Q1单独交互）另列native，非主同sample验证。04C-06的51/P2变化是不同目标总体比较，不能声称相同estimand复现；原46与扩充51也另给共有46子集结果而不删扩充结果。组季观察组成是证据，不证明选择无偏。
