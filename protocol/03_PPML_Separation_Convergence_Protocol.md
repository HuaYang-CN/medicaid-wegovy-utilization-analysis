# PPML分离、秩及收敛验收

审计日期 2026-10-12（Asia/Shanghai）。Stage03 仅统计设计审计与后续规格锁定，所有拟分析均 NOT_EXECUTED。原结果为 ORIGINAL_SAVED_RESULT / MATCHED_SAVED_OUTPUT，未独立复现。稿件身份 PROVISIONAL_CURRENT_VERSION，VERSION_AMBIGUOUS。

证据根目录：本项目 `03_audit_outputs/Stage01`、`Stage02`；历史源根为 `external_data`。下文 E01=Stage02/02_PPML_Code_Audit.md；E02=02_Missing_Zero_Suppression_Audit.md；E03=02_Enrollment_Definition_Audit.md；E04=02_Policy_Source_Audit.md及02_State_Policy_Adjudication.csv；E05=02_FFS_MCO_Consistency_Audit.md；E06=02_Current_Figure2_Source_Audit.md；E07=02_Original_Result_Lineage.md。证据等级 STATIC_CODE_VERIFIED / SOURCE_VERIFIED 只涉及代码或来源事实，不能替代科学有效性。原执行连接 INFERRED，版本可信度 MEDIUM_CONFIDENCE，确切运行版本 UNKNOWN。

E01静态原算法200迭代、eta[-25,25]裁剪、pinv、参数步长停止、达上限仍输出，未保存实际执行诊断。主AK-Wegovy全零源缺失组已确认，不等于观测真实零；在历史饱和state-product FE规格，令该FE→−∞使该组μ→0、log拟似然向边界改善，完整FE有限最优不能假定。DDD斜率可能在其余支持上有限可估，不能据全零直接断言4.09不可信。

分离与矩阵秩是不同条件。全部X线性满秩不排除Poisson separation；正结局子样本支持也要检查。针对零集合，可用经验证的线性规划寻找d使X_positive d=0，X_zero d≤0且至少一项严格负（例如sum(X_zero d)≤−1可规范化），存在则有分离方向。offset固定有限不改变此方向条件。算法与容差须单元验证；仅全零FE扫描不足检出其他组合分离。理论参考[Correia等原作者说明](https://github.com/sergiocorreia/ppmlhdfe/blob/master/guides/nonexistence_primer.md)。

| 诊断 | 锁定验收/失败 |
|---|---|
| Input/overlap | keys唯一，y≥0且finite，offset finite positive N；前后/两组/两产品对目标列有支持，否则HARD STOP |
| Separation | 全零FE和正式组合检测，保存separation certificate/算法/tolerance；无检测为NOT_VERIFIABLE。分离行处置前后名单公开 |
| Rank | 基类规范化后X以SVD τ=max(n,k)×machine epsilon×最大奇异值给effective rank；τ×0.1/10敏感；记录谱、条件数；DDD在其余列空间外，否则HARD STOP。名义冗余FE按规范化处理，不任意删目标项 |
| Solver | converged flag且≤1000迭代；达到上限=FAIL。IRLS/line search，初值两套与tol tightening；不用clip制造有限解 |
| Score | 列尺度归一x_j后max_j |Σx_j(y−μ)|/(1+Σ|x_j|μ)≤1e-8；记录原始score向量与缩放。不能只看β步长 |
| Objective | 连续5步相对deviance/loglik变化≤1e-10，非finite或未解释持续逆向步=FAIL；记录轨迹与line-search；tol1e-12复核 |
| Predicted means | 有限非负，非分离有效样本μ>0；不得出现overflow/人为裁剪；边界μ=0只另标extended-MLE，不冒充有限FE |
| Stability | 可识别DDD在两初值、收紧tol的差异≤1e-6；超则停止解释，不以最接近4.09解为准 |
| Covariance | finite/symmetric relative tolerance1e-10、scaled PSD负特征仅≤1e-10数值级可记录；目标variance>0；sandwich完整保存；不clamp负方差掩盖问题 |
| Dropping | 逐行/参数reason、前后样本hash/n/G/组/季及estimable terms；目标对比不估则FAIL |
| Warnings | 保存全部warning/error、未收敛/分离/奇异警告逐项解释，不仅软件有结果即PASS |

完整CR协方差秩≤G−1，参数超过46时整体singular可能是正常cluster结构，不要求全矩阵positive definite；目标和联合检验RVR'必须具有对应正秩。bread可识别子空间若数值奇异不能用无说明pinv替诊断。条件数>1e12为CAUTION，目标不稳为FAIL。

原样本AK边界处理与数据修正排除需分开：04A保持1012请求样本、记录extended boundary；仅删除经正式证书证明的separated行以检验剩余斜率，标签effective-estimation sample，保存请求/有效两个hash及解释。不能标“相同样本独立复现”而不说明删除。04B M1缺源规则可能删除AK全部双产品季度，这是报告子总体变化，非数值删零，不能混为等价处置。

原算法不得未经审查执行或import。Stage04独立重写原有限迭代求解仅用于实现审计，任何FAILED run保留，无法验证原4.09即报告失败，不直接覆盖旧值。


## 协议修订 v1.1，冻结审查后的最终规则

尺度锁：c_j=max(1,max_i|X_ij|)，Xscaled_j=X_j/c_j；结构rank用规范化Xscaled的SVD门槛max(n,k)εσmax。weighted Z=diag(sqrtμ)Xscaled另按同式给rank/condition，要求在结构可估空间rank=r，不能把weighted信息丢失当纯dummy冗余。条件数用该空间σmax/σmin；bread实现映回原系数规范化。LP d各项free（不使用默认nonnegative bounds），zero normalization约束按上述证书，保存feasible direction及残差。

Objective主用Poisson deviance，单步relative=|D_new−D_old|/(1+|D_old|)，仍要求末5步≤1e-10及scaled score≤1e-8；loglik为支持性保存，不另挑较宽松指标。协方差symmetry范数比||V−V'||2/max(||V||2,ε)≤1e-10；PSD λmin(Vsym)≥−1e-10 max(||Vsym||2,ε)，仅数值级负特征保留说明，任何目标方差≤0仍FAIL，不裁为0。μ跨实现逐元素|μa−μb|≤1e-8+1e-6|μref|，无“小均值”任意分段阈值。合法参数SE和cov容差沿原条款。
