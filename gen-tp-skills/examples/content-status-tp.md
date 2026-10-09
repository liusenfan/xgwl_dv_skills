# Demo 内容完整性：complete 与 draft

> 技能：gen-tp-skills
> 设计版本：demo-status-1
> 分类体系：base-cross-scenario
> 状态口径：内容完整性
> 总测试点数：2

## 验证边界与依据

依据 [content-status-spec.md](content-status-spec.md)，仅分析输出背压及连续传输性能。DUT 为单槽传输模块，外部驱动输入、out_ready 和 rst，观察公开接口。驱动、checker 和覆盖采样均未实现，不影响定义完整的功能点标 complete；本例没有人工评审或执行结论。

## 场景组织

业务骨架为接受输入→等待输出接收→输出完成。扫描以下基础对象后细化背压专项；全模块 Scenario 及复位专项不在本次范围，不能据这两个 TP 声称全量分析完成。

## base 适用性

| category | disposition | basis |
|---|---|---|
| Register Access | 不适用 | S1 明确无配置寄存器 |
| Config Space | 不适用 | S1 明确无需配置 |
| Dynamic Input | 有测试点 | S2 规定 out_ready 的保持与恢复行为 |
| Performance | 有测试点 | S3 规定负载和测量窗口，阈值欠定义 |

## 基础与关系检查

| 对象/关系 | 来源ID | TP/检查项/维度或处置 |
|---|---|---|
| out_ready 与 out_valid/out_data 的保持关系 | R2 | demo_backpressure：背压保持、恢复及单次完成 |
| 连续请求与持续可接收条件 | R3 | demo_throughput：测量窗口及计数；阈值见 Q1 |
| rst、输入握手及槽位初始条件 | R1 | 两点共用 CFG-IDLE；复位功能专项不在本次范围 |

## 测试点统计

| 测试需求 | 测试点数量 |
|---|---|
| Dynamic Input | 1 |
| Performance | 1 |
| 合计 | 2 |

## 测试点汇总表

| 测试需求 | 测试子需求(L1) | 测试子需求(L2) | 测试子需求(L3) | 测试点名 | 测试点描述 | 需求ID(s) | 关联用例名称 | 功能覆盖率描述(Optional) | 直接用例激励描述(Optional) | 环境检查说明 | 度量测试点覆盖 | 标签 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Dynamic Input | 背压恢复 | - | - | demo_backpressure | 输出受背压时 valid/data 保持，解除后同一数据仅握手一次 | R1,R2 | 待反填 | assertion：检查背压时valid/data保持；辅助functional coverage：确认真实背压及恢复握手发生；结果计数检查单次输出，采样实现待设计 | 前置：CFG-IDLE；无寄存器配置<br>发起：in_valid=1、in_data=0xA5，输入握手后撤 valid；数据为策略选择<br>推进：out_ready=0，out_valid 出现后保持3个上升沿，再置 ready=1；3拍为策略选择<br>预期/结束：保持期间 valid/data 不变，恢复后输出0xA5仅握手一次，下一周期 out_valid=0 | 检查计数、数据及保持性质；需要 check：驱动、checker 和命中采样实现待设计 | [p] 待设计:背压保持及恢复 | demo-status-1 |
| Performance | 连续传输 | - | - | demo_throughput | 在连续输入且无输出背压条件下，测量规定窗口的输出吞吐<br>draft原因：缺吞吐合格阈值，无法判定性能是否达标（Q1） | R1,R3 | 待反填 | testcase + 计数测量：按100拍窗口统计吞吐；判据比较待Q1阈值明确，不以覆盖率命中判性能通过 | 前置：CFG-IDLE<br>发起/推进：in_valid=1、out_ready=1，输入数据按接受次数递增并取低8位（策略选择）<br>测量：首次输入握手下一上升沿起计100拍，吞吐=输出握手数/100笔每周期<br>预期/结束：窗口结束给出测量值；需要 check：合格阈值（Q1），确认前不判性能通过 | 核对窗口和握手计数；测量器待设计。阈值缺失为设计问题，不能用超时或推导值替代 | [t] 待反填 | demo-status-1 |

## 测试点状态

| TP_ID | lifecycle_status |
|---|---|
| demo_backpressure | complete |
| demo_throughput | draft |

## 场景补充

CFG-IDLE：in_valid=0、out_ready=0；rst=1 保持一个上升沿，再置 rst=0，于随后上升沿起发请求，依据 R1。每个请求发送前驱动相应字段并在规定上升沿判断握手。

## 需求来源

| 需求 ID | 文档与版本 | 章节及条款 | 对应检查 |
|---|---|---|---|
| R1 | content-status-spec.md demo-status-1 | §S1 接口与初始化，两段接口合同 | 初始化及输入接受、输出完成 |
| R2 | content-status-spec.md demo-status-1 | §S2 输出背压 | 保持、不丢不重及恢复 |
| R3 | content-status-spec.md demo-status-1 | §S3 连续传输性能 | 负载、100拍窗口及吞吐口径 |

## 规格缺口

| issue_id | issue_status | affected_parameter | scenario_context | unresolved_item | missing_content | completion_condition | source | affected_tp_ids |
|---|---|---|---|---|---|---|---|---|
| Q1 | open | 吞吐合格阈值 | 连续传输 | 验收阈值未给出 | 缺次数/100口径下的合格线 | 设计确认该窗口和负载下的阈值 | content-status-spec.md demo-status-1 §S3，末两句 | demo_throughput |

## 能力交接

两点均需接口驱动和观察；背压点需保持与单次输出检查，性能点需窗口及握手计数。实现未建不改变内容状态，工具暂不能转换也不得移除 TP。
