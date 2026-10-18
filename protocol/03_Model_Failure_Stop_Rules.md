# 数据、识别与求解停止规则

审计日期 2026-10-12（Asia/Shanghai）。Stage03 仅统计设计审计与后续规格锁定，所有拟分析均 NOT_EXECUTED。原结果为 ORIGINAL_SAVED_RESULT / MATCHED_SAVED_OUTPUT，未独立复现。稿件身份 PROVISIONAL_CURRENT_VERSION，VERSION_AMBIGUOUS。

证据根目录：本项目 `03_audit_outputs/Stage01`、`Stage02`；历史源根为 `external_data`。下文 E01=Stage02/02_PPML_Code_Audit.md；E02=02_Missing_Zero_Suppression_Audit.md；E03=02_Enrollment_Definition_Audit.md；E04=02_Policy_Source_Audit.md及02_State_Policy_Adjudication.csv；E05=02_FFS_MCO_Consistency_Audit.md；E06=02_Current_Figure2_Source_Audit.md；E07=02_Original_Result_Lineage.md。证据等级 STATIC_CODE_VERIFIED / SOURCE_VERIFIED 只涉及代码或来源事实，不能替代科学有效性。原执行连接 INFERRED，版本可信度 MEDIUM_CONFIDENCE，确切运行版本 UNKNOWN。

| 类别 | 触发及范围 | 处理 |
|---|---|---|
| HARD STOP 所有目标数值解释 | nonfinite/非法offset；DDD被吸收/无重叠；非分离有效样本无法可靠收敛；目标variance非法；来源/样本hash不一致未解释 | 保存失败对象，暂停该模型；不可输出有效IRR或主要结论，定位原因，作者审阅 |
| HARD STOP 全46目标 | 未知缺源导致无法定义全46结局且无可验证机制，主要量对未经支持插补高度依赖 | 全46真实率/效应NOT_VERIFIABLE；允许可报告子总体有界描述，明示新estimand |
| HARD STOP 因果主张 | 核心事件前政策无法合理定义；未来选择缺证；比较产品差异冲击未排；识别假设没有足够支持 | 保留关联定位，不是以jointP>.05升级；如坚持因果须重大设计重建 |
| HARD STOP 原复现成功标签 | finite原FE解不存在/原run未知且重写未复现，或独立same-spec超容差未定位 | REPLICATION_FAILED/NOT_VERIFIABLE，原4.09不改；可另报告有效support诊断 |
| CAUTION 数据修正根本变化 | 原vscorrected目标β方向反转或abs logβ变化>0.5、主要解释需改（预设审计阈值，非定理） | 停止锁定原科学结论，保留两者，检查data/sample差异；不要求更显著方案 |
| CAUTION 统计支持 | cleanpre仅3季度/2lead；任一组<10有效簇；LOO重要；宽CI；jointpre显示不相容 | 报告低功效/弱支持及有限簇，限制强因果；不能删除异常州或阴性 |
| CAUTION 支撑变化 | separated observations被正规识别删除、rank规范化、缺源配对删除 | 记录原/有效样本、estimable space；若目标保留可继续有界结果；不是自动全模型无效 |
| ACCEPTABLE LIMITATION 有界关联 | 处方重复、全龄total population、渠道贡献率、未测患者资格、生态政策环境 | 正确标名/范围；若升级患者/公平因果结论即HARD STOP |

每模型gate输出PASS/FAIL/NOT_VERIFIABLE为诊断标签，问题登记仍仅CONFIRMED/SUSPECTED/NOT_VERIFIABLE/RESOLVED。没有运行本阶段gate。正负/显著不显著均不是选择模型的通行证。硬停止指对应目标，非禁止保存失败、准备修正或透明描述；下一子阶段另批，不跨过作者审阅。
