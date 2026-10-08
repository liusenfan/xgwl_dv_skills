# 测试点大纲与 Sheet 职责

本大纲适用于新建全量计划；局部分析声明范围，不能冒充全量覆盖。先理解设计的模式和业务，再从下面六个角度完成分解。Sheet 是评审分类，不是六个互不关联的验证阶段。

## 1. 三类 TP、六个主 Sheet

| TP 类别 | Sheet 名（固定拼写与顺序） | 主验证目标 | 应包含的内容 |
|---|---|---|---|
| base | Register Access | 寄存器访问语义正确 | 设计规定的复位值、读写属性、掩码、只读/写一清零等副作用、地址译码及保留位访问行为；未知规则不能由字段名字推断 |
| base | Config Space | 配置对业务的作用正确 | 工作模式、静态参数、配置选择/提交/生效、有效范围与边界、配置改变引起的业务效果；说明配置对象、字段及使用它的业务 |
| base | Dynamic Input | 输入接口及运行期输入语义正确 | 请求、数据、控制、ACK、资源返回等输入的字段、合法值、边界、握手、时序、连续输入及反压响应；动态请求寄存器也按本次目标区分访问测试和输入功能测试 |
| base | Performance | 性能承诺及公开性能度量正确 | 负载、测量起止事件、单位、吞吐/延迟/利用率及设计定义的计数语义；仅计数器读写不等于性能验证 |
| 探索 | Cross | 有关联或约束的功能交互正确 | 配置×输入、业务×资源、并发业务、事件顺序等有设计依据的关系；写交叉 item、各自取值、合法组合约束、交互风险和预期 |
| scenario | Scenario | 在黑盒边界下完整分析业务场景 | 按模式→业务通路→结果不同的分支组织；启动、输出、完成、退出/恢复形成闭环，含最小合法业务、代表任务链及适用异常/恢复 |

**base 四类是系统级验证的必查范围。** 每类必须有适用性结论和设计来源：有需求则完整列点；资料欠缺则写 `规格待补充`，保留已知目标；确实不适用须给设计依据。不能用平台未实现、不会激励、无法准确 check 解释空白。性能阈值缺失不等于性能不适用：保留已知性能目标并关联问题，不臆造合格线；完全没有可识别目标时记录资料缺口，不制造空 TP。

`Scenario - vfmacc.vv` 统一为 `Scenario`；具体指令、模式和业务放在子分类或描述。参考工作簿该页实际是围绕一条指令的参数/关联 TP 分析表，不能原样复制后当作 DUT 的完整场景分析。新计划的 Scenario 每行仍是一个独立主目标；必要时在场景补充中引用相关 base/Cross TP，保留约束关系。

## 2. 分类与粒度

- 按**本行主目标**确定唯一主 Sheet；同一 TP 不在多张主表重复计数。其他关系在描述、覆盖维度或补充中引用 TP_ID。
- Register Access 证明“读写/复位是否符合属性”，Config Space 证明“配置是否使业务按规定运行”，Dynamic Input 证明“运行期输入如何被接收和处理”，Scenario 证明“这条业务如何完整完成”。同一字段出现在多类中不等于重复，主目标相同的行才需去重。
- 允许寄存器/字段按独立访问属性或功能语义列点；同构寄存器、等价字段和取值可归组为维度。不能为了压缩点数删除复位、读写、副作用等独立要求，也不能机械展开每个 bit/值。
- Cross 不做无条件笛卡尔积，不把任意两个参数同时出现当作交叉目标。设计要求明确的交互属于必须验证的目标，“探索”不表示可因难以构造而省略。设计没有规定的猜想标为分析问题，不补造预期。
- Scenario 的完整业务不能被 base/Cross 检查齐全所替代；场景有配置不等于归 Config Space，有多个字段不等于归 Cross。
- 所有主表都保留必要激励：配置和值/约束、发起接口与字段、推进步骤、预期、结束条件；未知项标 `需要 check`，与覆盖度量类型无关。

例：TS 的任务属性读回归 Register Access，任务配置提交及效果归 Config Space，Trigger/ACK/Credit 输入合同归 Dynamic Input，明确的发射吞吐目标归 Performance，业务与资源竞争归 Cross，Normal/Special 的单 Task、搬入/搬出、Bypass、Reduce 完整流程归 Scenario。具体内容仍须以本次 TS 设计为准。

## 3. 两张 missing-input 表

### Scenario missing-input：设计问题台账

分析 DUT 详设的矛盾、冲突、欠定义和疑似不合理之处，范围可涉及全部六类 TP。记录来源章节及差异、受影响参数/场景、具体问题、缺少内容、需要设计方给出的结论及受影响 TP_ID。对“疑似不合理”写清设计约束和推导，不把验证者偏好当成设计错误。

工作 Markdown 的 `## 规格缺口` 为唯一维护源，使用以下表头：

`issue_id | issue_status | affected_parameter | scenario_context | unresolved_item | missing_content | completion_condition | source | affected_tp_ids`

- `issue_id` 唯一；`issue_status` 为 `open` 或 `resolved`。resolved 行须保留已确认结论及来源，不能仅为隐藏阻塞而关单。
- `source` 写具体文档版本/章节及冲突双方；多个 `affected_tp_ids` 用英文逗号分隔，纯问题填 `-`。
- 纯问题不计入 TP 总数；有明确设计目标的 TP 留在所属主 Sheet，不能搬到问题表后不计数。
- 平台实现/检查能力不足写能力交接，与设计问题分开；不能据平台缺口将规格标成冲突。

### lifecycle missing-input：按 TP 展开的定稿阻塞视图

这里的 lifecycle 指**测试点文档状态**，不是 DUT 的运行生命周期。参考表包含 draft 的 Config Space、Dynamic Input、Cross TP 及其缺失规格和解除条件。

新输出由 open 设计问题的 `affected_tp_ids` 自动展开，列为：

`affected_tp_id | lifecycle_status | missing_content | completion_or_unblock_condition | issue_id`

同一问题可影响多个 TP，同一 TP 可关联多个问题；它们是关联记录，不产生新 TP。问题正文只在 Scenario missing-input 维护，生成此视图避免两边结论漂移。主表受 open 问题影响的 TP 状态为 draft；未关联问题也不会自动变成 complete。默认全部为 draft，已评审状态通过 `## 测试点状态` 的 `TP_ID | lifecycle_status` 表记录，允许 draft/reviewed/complete；reviewed/complete 须有实际评审依据。**complete 仅表示计划内容定稿，不表示仿真通过或验证覆盖完成。** open 问题与 reviewed/complete 冲突时先修订状态，不能静默掩盖问题。

没有问题时保留这两张表的表头，在 Plan Notes 中说明“本次未识别到设计缺口（不代表规格无缺陷）”；不制造占位测试点。实际业务的创建、完成、退休、复用等运行生命周期测试仍归 Scenario 或具有独立交互目标的 Cross。

## 4. 新计划与旧计划

新计划使用模板中的 `> 分类体系：base-cross-scenario`。第一字段“测试需求”填写六个主 Sheet 名之一，L1–L3 承接原业务模式/场景层级；Excel 按固定顺序生成六个主 Sheet、两张问题表和 Plan Notes，空主题仅保留表头，适用性说明放 Plan Notes。Markdown/HTML 采用相同分类及同一规格问题源。

旧计划原样导出保持原分类；没有此标记时工具走兼容路径，不自动猜测中文主题属于哪类。获授权迁移时逐点按主目标归类、保留 TP_ID/用户修改/真实用例关联、记录原分类映射；不能只改 Sheet 名。历史局部示例只展示粒度和字段，不是新版完整大纲；新大纲示例见 [classified_st_tp.md](../examples/classified_st_tp.md)。
