# 交付、校验与能力交接

## 产物与执行

格式由用户最终决定，可多选 XLSX、HTML、Markdown；未指定时在授权目录仅写 `<dut>_st_tp.xlsx`。用户约定命名和范围优先。字段与 Excel 样式映射见[格式说明](output-formats.md)。修订先读取用户最新版本，保留手工修改；缓存 Markdown 不能自动覆盖已修改的 Excel。

新计划先按[六类大纲](tp-outline.md)和 13 字段合同建立工作 Markdown，包含分类标记、base 适用性和结构化规格缺口；再校验。它可以位于临时工作区；用户未选择 Markdown 时不放入交付目录。用实际可用 Python 执行，XLSX 另需 Node.js 和 `@oai/artifact-tool`；Codex 桌面环境可通过 `load_workspace_dependencies` 定位运行时，不假定 Windows 命令名。

```bash
python3 <skill_dir>/scripts/tp_contract.py <work_dir>/<dut>_st_tp.md
# 默认仅 XLSX；node_modules 指向提供 @oai/artifact-tool 的运行时目录。
python3 <skill_dir>/scripts/export_tp.py <work_dir>/<dut>_st_tp.md --out-dir <output_dir> --node <node_path> --node-modules <runtime_node_modules>
# 显式多选，可选 xlsx / html / markdown：
python3 <skill_dir>/scripts/export_tp.py <work_dir>/<dut>_st_tp.md --out-dir <output_dir> --formats html markdown
```

`export_tp.py` 默认只输出 XLSX；`--formats` 支持多项或逗号分隔。`--preview-dir <work_dir>/preview` 生成 Excel QA 图片，供检查不作为交付件。已有输出默认拒绝覆盖；只有授权更新这些输出时才使用 `--overwrite`。全部所选格式构建成功后再复制到交付目录。XLSX 依赖缺失时报告具体失败，不能擅自改交付格式。

校验器和 Python 编排仅依赖标准库。单独使用 `gen_tp_html.py input.md [output.html]` 时须先确认 HTML 是用户选择的格式；其保留分类折叠、搜索、各字段和附录，附录按纯文本呈现。不要手改派生 HTML 后声称各格式内容一致。

## 两类检查分别报告

### 自动结构检查

本包检查工作数据的列数、必填字段、名称唯一性、所有点第 10 字段必填、第 9 字段与第 12 字段的覆盖要求、目标格式和数量统计。新分类体系额外检查六类合法性、四类 base 的适用性、问题 ID/TP 引用和逐点文档状态；旧表保留兼容读取。HTML 核对场景数及附录；XLSX 重新读取导出文件，按英文列映射逐字段比对、核对各 Sheet 总数及附录文本，并查看每页代表性区域。只检查用户选中的格式；未选格式缺席不算失败。

维护包工具时运行：

```bash
python3 -m unittest discover -s <skill_dir>/tests -v
```

### 场景语义检查

按[分解决策](decomposition.md)人工核对以下内容，不把结构通过称为语义评审通过：

- 按业务骨架→基础扫描→详细 Scenario→双向补漏核对；逐对象、逐关系有 TP/检查项/维度或处置去向。Cross 条件完整，Scenario 有独立业务判据，不被参数关联表替代。
- Register Access 只验证寄存器属性，APB仅作合法访问手段；协议专项及业务执行效果未混入该页，旧协议TP的范围调整有去向。
- 参数取值对应行为；相关参数的固定/约束/可变/不参与条件明确；负向覆盖不误作 illegal bins；性能测量口径与设计判据匹配。
- Scenario missing-input 分析设计问题，lifecycle missing-input 从 open 问题关联生成，两者及纯问题不增加 TP 总数；complete 表示必要内容完整，无需人工批准；不代表已评审、执行或覆盖。新计划逐点明确状态，平台与工具待办不阻止 complete。
- 主表每行的业务目标和预期来自设计文档；具体激励、观察与check尚未解决的点仍完整保留，不把现有平台能力当作列点门槛。
- 先核对模式和典型业务通路的基础闭环是否有场景落点，再核对专项；不能仅因ACK、仲裁、Credit、退休检查齐全就判定业务覆盖完整。改变执行集合或生命周期的分支须分别有判据和完成证据。
- 按[激励写法](stimulus-description.md)核对每点必要配置的字段和值/约束、请求接口及字段、响应顺序、预期和结束条件。明确区分设计固定值、策略选择及 `需要 check`；不能用泛泛的“配置并启动、检查正常”代替。结构脚本不验证配置值或激励充分性。
- 合并保留了有效检查、维度和独立风险；需求在主表或范围处置中有去向。
- 必要的跨功能交互没有因“按场景合并”被漏掉，综合压力也没有替代独立目标。
- 合法环境约束、违规输入、规格未决以及平台能力待建设分别处理。
- 每条 draft 在主表可直接看到具体原因和问题 ID，missing-input 有受影响范围、来源与完成条件；归组点区分已明确部分和缺口。不得因平台未建而标 draft。
- `coverage_strategy` 明确方法及选择理由，与主/辅助度量一致；断言检查性质、功能覆盖率统计命中，结果检查承接正确性。未触发的断言、仅命中bin或仅发过激励均不能代替有效检查及结束条件。

交付报告实际路径、范围、已执行检查和关键限制；不要声称获得用户批准、仿真通过或覆盖收敛。

## 与 DV MAS 同阶段协作

TP根据设计文档给出目标、条件、判据和覆盖需求，DV MAS承接driver/monitor、参考模型、SCB、FCOV/SVA等能力设计。两者分开工作：TP不要求读取平台代码或先确认能力；DV MAS反馈未实现/无法准确check时，只更新实施说明，不能删除测试点或缩减判据。未确定路径写待设计，不猜层次名。

同一场景可由多个用例共同覆盖，多个场景也可共用业务用例。业务场景的精确条件/判据若需辅助观察或白盒协作，在能力交接中记录，原测试点仍在主表；只有确属设计范围外的纯结构要求另列范围处置。不自动调用其他skill或生成用例。

## 向 TC 环节交接

完整TP可以先交给TC及平台规划环节，能力不完整不阻止TP交付。以下handoff模式仅用于后续检查“实现路径已落实”的子阶段，不是TP完整性或列点准入检查；未满足的点保留主表。需要此检查时，由授权环节核对路径后运行：

```bash
python3 <skill_dir>/scripts/tp_contract.py <output_dir>/<dut>_st_tp.md --stage handoff
```

handoff 模式拒绝字段 12 的待设计/待反填占位及值为 `待确认` 的版本标签；字段 8 可继续待反填。脚本只检查语法，不识别标签中每种未决措辞，不验证真实路径、平台状态或审批。

Excel 交接时先按[字段映射](output-formats.md)读取用户当前工作簿，还原并核对本次工作数据，再运行 handoff 校验；不得因为未交付 Markdown 而拒绝 XLSX 交接。

消费方须理解场景粒度、检查项、辅助覆盖和多对多映射。若旧 `ubench-tc-gen` 或其他工具要求严格 1:1、文件名等于点名或 `[p]` 自动归 Random，报告实际差异，不擅自修改消费方、点名或覆盖目标。

TC 回填第 8 列不代表可以修改第 12 列。已有真实名称来自实际产物；修改主/辅助目标由获授权规划环节处理，随后重建 HTML。

## 可选项目汇总页

独立使用仅交付用户选择的格式，未指定时仅 XLSX。项目已有四页签工作流且用户已选择/授权 HTML 汇总时，定位实际可用的 DV MAS 汇总脚本，再更新 TestPoint 页签，例如：

```bash
python3 <dv_mas_skill_dir>/scripts/ut_html_tab.py fill <output_dir>/<dut>_st.html TestPoint <output_dir>/<dut>_st_tp.html
```

确认其他页签未改。找不到脚本时保留本包产物并报告汇总页未同步，不擅自安装或改写兄弟 skill。工具错误、规格缺口和能力未实现分开报告。
