# 有限州簇与不平衡组推断

审计日期 2026-10-12（Asia/Shanghai）。Stage03 仅统计设计审计与后续规格锁定，所有拟分析均 NOT_EXECUTED。原结果为 ORIGINAL_SAVED_RESULT / MATCHED_SAVED_OUTPUT，未独立复现。稿件身份 PROVISIONAL_CURRENT_VERSION，VERSION_AMBIGUOUS。

证据根目录：本项目 `03_audit_outputs/Stage01`、`Stage02`；历史源根为 `external_data`。下文 E01=Stage02/02_PPML_Code_Audit.md；E02=02_Missing_Zero_Suppression_Audit.md；E03=02_Enrollment_Definition_Audit.md；E04=02_Policy_Source_Audit.md及02_State_Policy_Adjudication.csv；E05=02_FFS_MCO_Consistency_Audit.md；E06=02_Current_Figure2_Source_Audit.md；E07=02_Original_Result_Lineage.md。证据等级 STATIC_CODE_VERIFIED / SOURCE_VERIFIED 只涉及代码或来源事实，不能替代科学有效性。原执行连接 INFERRED，版本可信度 MEDIUM_CONFIDENCE，确切运行版本 UNKNOWN。

历史46州簇、12覆盖/34非覆盖；这是环境比较，没有随机赋值的12处理州。独立簇为州，不是1012行；4.09旧normal推断仅保存结果。时间共同冲击可跨州相关，州聚类假设不能用G=46自动保证。两产品不适合用product cluster；11季度亦不足机械两维聚类修复。

锁定新主关联推断为州聚类sandwich CR1，校正G/(G−1)×(n−1)/(n−r)，r为规范化有效设计rank，n为实际有效样本；scalar t(G−1)95%区间与双侧精确P。不是在12/34中挑小或大df；每run报告effective G与两组G。该t调整是保守实用选择而非有限样本精确保证。旧nominal k + normal只用于复现对照。

ESSENTIAL保留主DDD在CR1 normal、CR1 t(G−1)之间推断敏感性以及所有州leave-one-out系数/区间/score leverage；删一州只是影响度诊断，绝不据它选最终样本。联合事前Wald使用实际RVR'有效rank q，主F(q,G−1)近似；若无可估矩阵不能拼边际SE。报告共同时间冲击与簇独立限制。数据修正/分离后G可能少于46，严禁沿旧G。

RECOMMENDED wild cluster restricted score bootstrap为PPML非线性M-estimator方法门控方案，不能把OLS残差乘weights后直接拟Poisson当有效。以H0:β_DDD=0的restricted PPML、完整nuisance FE调整的有效cluster score/Hessian构造；验证约束solver、得分projection、studentization与test inversion。来源[Kline与Santos原论文工作版本](https://www.nber.org/papers/w16127)。未经软件/方法等价测试不将boottest/fwildclusterboot对OLS支持冒充PPML支持。

条件可执行时固定seed=20261012、9999次Rademacher州权重，一州内所有季/产品共同权重；Webb六点为第二敏感性，保存种子、算法版本、有效簇、reject counts与MonteCarlo误差。scalar CI通过null inversion，jointpre用对应多约束score方法；不从错误percentile或significance picking造CI。若实现无法验证，报告NOT_VERIFIABLE并保持CR1/t主及LOO，若强因果精度依赖未验证bootstrap则停因果结论，不自动切OLS。

设计检查包括两组簇、各簇信息/score及删簇后目标support、集中度、组间heterogeneity；两组任一<10有效簇预设CAUTION，<2或目标未识别HARD STOP。这是保守审计阈值，不是文献定理。LOO若任一方向逆转或β变化>0.5（log尺度审计阈值）触发解释审查与影响原因公开，不能自动删州“修复”。不以CI跨1本身为模型失败。保留不同推断结果而不选择更显著者。


## 协议修订 v1.1，冻结审查后的最终规则

联合约束统一：保存原R行数/rank及每行可估性；仅纯代数冗余且能证明与原H0等价才用预先保存的独立行变换去冗余。对原独立q个假设，要求RVR'数值rank=q且正方差，才F(q,G−1)近似。独立约束cov奇异/不可估→原joint NOT_VERIFIABLE，禁止通过减q或pinv称原H0通过。可估子空间检验若另批报告必须新H0与新标签，不作原joint支持。

EV-CLEAN full family为2 clean leads+7post=9个非参考DDD；EV-TRANS为前述9+Q1 transition=10。各family分别Bonferroni双侧95%同时区间，临界t_{G−1}(1−0.05/(2m))，m固定9或10；同时也保留逐点95%。若任一目标不估，完整family同时区间NOT_VERIFIABLE，不删点缩family。不同赋值/FE情景各完整报告，不把其中显著点挑作共同验证；bootstrap max-t未验证不临时替代Bonferroni。

趋势功效最小锁：clean lead k=(-4,-3)，ref k=-2；给定每季log差异斜率d∈{0,±0.10,±0.25}，h_d=(-2d,-d)。使用clean lead 2×2V与λ=h_d'V^{-1}h_d、α=0.05，报告noncentral-F(2,G−1,λ)对主F拒绝域的plug-in近似功效；仅当V完整可估，不拼边际SE。它是估计V条件下的可检测性，不是实证功效保证。post偏离另定义δ_k=d(k+2)与β_k−δ_k情景，相对Q4累积、保持同V仅是假定偏离已知的外推展示，不当稳健因果置信界。Stage03未计算任何λ/功效/效果。


G_BOOT输出补锁：仅验证后的restricted PPML有效nuisance-adjusted score及其studentized绝对统计量T才适用；两侧按|T*|≥|Tobs|（等号计尾），p=(1+尾部复制数)/(9999+1)。同seed/同州权重矩阵复用于null inversion，Rademacher主、Webb敏感均全报。任一复制非finite/算法失败不静默剔除或补新的seed；该bootstrap输出FAIL/NOT_VERIFIABLE并保留失败数，CR1/t不替换。

条件方法通过后scalar confidence set以p>0.05为接受，初始β0∈[-8,8]、步长0.01，若边缘仍接受按2倍扩至最多[-64,64]，边界搜索二分tol1e-4/max50步并保存全部restricted fit诊断。不连通接受集逐段报告，不强造单区间；超过搜索边界标未界定/NOT_VERIFIABLE，不假称有限。MonteCarlo SE按sqrt[p(1−p)/10000]，不是模型SE。以上输出约定不证明本地PPML bootstrap实现有效，实际G_BOOT仍NOT_VERIFIABLE，代码/方法独立审阅通过前不能计算或承诺bootstrap CI。
