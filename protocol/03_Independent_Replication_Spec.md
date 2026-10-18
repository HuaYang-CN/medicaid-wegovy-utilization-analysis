# 独立PPML复现与环境规格

审计日期 2026-10-12（Asia/Shanghai）。Stage03 仅统计设计审计与后续规格锁定，所有拟分析均 NOT_EXECUTED。原结果为 ORIGINAL_SAVED_RESULT / MATCHED_SAVED_OUTPUT，未独立复现。稿件身份 PROVISIONAL_CURRENT_VERSION，VERSION_AMBIGUOUS。

证据根目录：本项目 `03_audit_outputs/Stage01`、`Stage02`；历史源根为 `external_data`。下文 E01=Stage02/02_PPML_Code_Audit.md；E02=02_Missing_Zero_Suppression_Audit.md；E03=02_Enrollment_Definition_Audit.md；E04=02_Policy_Source_Audit.md及02_State_Policy_Adjudication.csv；E05=02_FFS_MCO_Consistency_Audit.md；E06=02_Current_Figure2_Source_Audit.md；E07=02_Original_Result_Lineage.md。证据等级 STATIC_CODE_VERIFIED / SOURCE_VERIFIED 只涉及代码或来源事实，不能替代科学有效性。原执行连接 INFERRED，版本可信度 MEDIUM_CONFIDENCE，确切运行版本 UNKNOWN。

当前环境 metadata preflight：bundled Python3.12.14，numpy2.3.5、pandas3.0.1；scipy、statsmodels、patsy、matplotlib NOT_INSTALLED。PATH未发现Rscript/R.exe/conda；不扩扫个人目录。原Python环境位置/精确版本锁 NOT_VERIFIABLE；不冒充已恢复。Stage03没有安装、下载或fit。

首选未来实现为Python statsmodels GLM family=Poisson、log link、显式dummy FE和offset（不加样本权重）。来源[GLM官方文档](https://www.statsmodels.org/stable/generated/statsmodels.genmod.generalized_linear_model.GLM.html)。备选为R fixest::fepois，[官方说明](https://lrberge.github.io/fixest/reference/feglm.html)。fixest自动remove perfect-fit/FE及小样本校正必须明确，不以默认当对齐。二者均需正式separation/目标可估证据，不认为GLM返回收敛即解决全零问题。

待批准环境计划：优先作者原环境只读导出python version/pip freeze/原run资料；若无法提供，项目内独立venv并冻结完整hash版本锁。候选Python3.12、numpy2.3.5、pandas3.0.1沿当前已检元信息；scipy/statmodels/patsy兼容版本须安装前由官方发行兼容核实并写独立environment lock，当前具体可安装版本 NOT_VERIFIABLE，不杜撰。最小依赖scipy+statsmodels及其patsy/packaging/dateutil等；画图另matplotlib。R备选R+fixest及依赖全记录。明确依赖安装/下载需作者另批，本阶段不执行命令；网页所见docs版本不是本机安装版本。

04A步骤：冻结源/processed/旧结果与审阅代码hash；对旧saved panel选择46、W/O、2023Q2–2025Q4、旧mid/offset/Q1编码，保持原requested1012 keys。不重跑历史build_panel/ACS联网脚本。独立构建X使用按字符串排序state:product基类、quarter基类、intercept、PA/PG/PAG，与历史L484–531一致；原请求全部列与实际rank分开保存。

独立实现与独立重写旧算法必须同row order、policy、产品、季度、y情景、offset、FE、分离有效样本及cluster。比较1为严格旧请求实现审计，若有限解不存在标REPLICATION_FAILED或EXTENDED_MLE_DIAGNOSTIC，不能无条件REPRODUCED_ORIGINAL_SPEC；比较2为共同separation有效样本独立斜率验证，label说明删行。不同sample的差异不能归solver。

冻结hash定义：row_key以state|calendar_quarter|analytic_brand（渠道模型另channel）排序后UTF8逐行newline SHA256；保留原请求顺序hash、排序集合hash及有效样本hash。data_hash另包括y/offset/policy十七位float稳定序列；X列names/reference/coding及X hash另保存。不可只key相同就称数值输入相同。

每run输出全parameters（含FE）、full covariance、cluster score、bread/meat/correction及G/n/effective-rank、solver history、rank谱/separation证书、predicted means、excluded rows/parameters和原因、warnings/failures、精确version、独立code hash。长期本地保存，反馈仅摘要，禁止凭据或大型raw打包。

容差预设：同规范化非分离目标β abs≤1e-6+1e-6|β_ref|；SE abs≤1e-6+1e-4|SE_ref|；同设协方差元素abs≤1e-8+1e-4|V_ref,ij|；μ相对max≤1e-6（小均值absolute≤1e-8）；都先过solver gate。核对历史保存DDD estimate/SE直接读取，Stage04才生成新IRR/CI/P。FE基准不同可映射，不能直接比不可识别常数。

协方差对齐有两层：旧校正使用nominal k的n−k与normal推断仅作为legacy comparison；新主CR1用有效rank并t(G−1)，不要求新CI/P匹配旧值。SE差异先统一sandwich/correction/有效样本，再比。统计校正合法差异不叫solver error。

失败定位顺序data hash→requested/effective keys→X编码/下阶项/rank→offset→separation处置→score/solver→bread/meat→finite correction→distribution。超容差保存差异，标具体原因或NOT_VERIFIABLE；不调初值/裁剪/样本追4.09。独立复现失败不一定阻止后续纠正描述，但须作者审阅失败后单批04B。


## 协议修订 v1.1，冻结审查后的最终规则

环境更正补充：PATH exact Python `external_resources/python.exe` 已以-I -B标准库元信息核验为3.13.5，numpy/pandas/scipy/statsmodels/matplotlib/patsy均NOT_INSTALLED。bundled3.12.14与其分开，原环境仍NOT_VERIFIABLE；此前仅PATH发现但未终结返回，现元信息完整。不扩大环境目录扫描或安装。

确定输入合同：旧04A面板为DATA/processed/state_quarter_brand.csv；分渠道为processed/state_quarter_brand_utilization.csv。源SDUD为Stage02/02_Source_File_Register.csv列明七年度文件，人口为raw/enrollment/cms_monthly_enrollment_2019_2025.csv，政策为三已索引快照及冻结Stage02裁决。精确现SHA已登记，04A再确认，不读未索引新历史文件。

源键=(state,year,quarter,11位ndc,utilization_type)，NDC三段作为字符串保留前导零，fileSHA/source_row_index仅lineage而非第二份处方。冻结版本以source register/hash指定，不依据mtime择最新；若出现跨文件修订同键或同版本重复，默认HARD STOP并登记，不自行去重/累加。明确官方修订版本与被替代版本时先审批固定一种版本，保留差异ledger。

产品映射冻结Stage02/02_NDC_Product_Mapping.csv与processed/ndc_brand_crosswalk.csv hash，使用已观察NDC/name/analytic_brand交叉核验，仅支持已提取记录；64个观察NDC不是历年完整目录。映射冲突/未映射保留UNMAPPED，主产品相关异常未定位前不聚合；不丢弃未知行，也不追认历史未返回NDC不存在。真实有效期/厂家全历史未知登记NOT_VERIFIABLE，不新造日期。

每源文件逐行partition raw→eligible(51边界/指定产品/窗口) +明示excluded(XX/PR/窗口等) +unmapped/invalid/unresolved-duplicate；各partition互斥且覆盖全部读入行。状态六类互斥且有source flag/数量/日期证据；suppressed数量未知，不等于invalid。按group/product/quarter/channel导出source presence、suppressed、missing和行覆盖核对。两套实现需分别从同冻结raw和映射规则生成ledger并比源覆盖/数量/状态，再比较聚合；不能只共享一张ledger验证自身。Stage03没有执行这些源重建。
