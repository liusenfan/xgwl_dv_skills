# 格式选择与 Excel 映射

## 格式由用户决定

- 支持 `xlsx`、`html`、`markdown` 任意多选。用户最新明确选择覆盖旧默认；如 `HTML + Excel` 就只交付这两种。
- 未指定格式时默认 **仅 XLSX**，直接采用默认，不因没有选择而停工反复询问。用户尚在明确选择过程中时，等待其最终选择再发布。
- `xslx` 视为 `xlsx`，`markdowm` / `md` 视为 `markdown`；最终文件使用正确扩展名。
- 既有未选中文件不自动删除或改写。临时 Markdown/JSON、预览图片、构建脚本不冒充用户选择的交付件。
- 格式转换不新增、删减、拆合或改写测试点；每种格式保留所有原字段、来源、边界、缺口与必要附录。多格式从同一份本次数据生成。

## Excel 样式来源及结构

用户参考文件：`C:\Users\刘\Downloads\VU_vfmacc_vv_TP_0914.xlsx`。本包在 [xlsx-style.json](../assets/xlsx-style.json) 保存提取的格式规则；导出不依赖参考文件仍在该电脑，也不复制其 VU 数据。

已确认采用多 Sheet、英文列名和参考样式，现有内容完整映射：

- 新计划按[测试点大纲](tp-outline.md)依次输出 `Register Access`、`Config Space`、`Dynamic Input`、`Performance`、`Cross`、`Scenario` 六张主表；`Scenario - vfmacc.vv` 统一为 `Scenario`，具体业务放在子分类。六类均保留表头，空类在 Plan Notes 说明适用性/资料缺口，不写占位 TP。
- 随后输出 `Scenario missing-input`、`lifecycle missing-input` 和 `Plan Notes`。前两者分别来自规格问题及其 TP 关联，不计入 TP 总数。分类规则不能导致已有业务闭环被配置字段覆盖替代。
- 旧文档无分类标记时继续按原一级分类导出；授权迁移后使用新版模板标记。Excel 不根据名称猜分类。
- 主表列以 `TP_ID`、`lifecycle_status`、`verification_goal`、`coverage_strategy`、`coverage_strategy_mapping` 开头，与参考通用测试点页一致；后续列承接现有内容。
- `Plan Notes` 用 `section / item / details` 保存元信息和其他附录；结构化规格问题已放入专用 Sheet，不在 Plan Notes 重复维护；附录表格按原字段名展开为明细，长文本分行保留，不截断。不将纯缺口行计入测试点数。
- Carlito：正文 10 pt，表头 11 pt 加粗；表头深蓝 `#1F4E78`、白字、居中，正文左上对齐、自动换行、不合并不同字段。列宽参照样例按内容调整，行高足以显示内容；增加首行冻结以便长表滚动。

## 字段映射

| Excel 列名 | 原计划字段 |
|---|---|
| TP_ID | 测试点名 |
| lifecycle_status | 新版每点默认 draft；显式状态表保留有依据的 reviewed/complete，受 open 规格问题影响者必须 draft。仅为文档状态，不从度量推测已执行/通过；旧格式沿用文档元信息 |
| verification_goal | 测试点描述，保持全文 |
| coverage_strategy | 功能覆盖率描述(Optional)，`[t]` 无辅助覆盖时为 `-` |
| coverage_strategy_mapping | 度量测试点覆盖，保持原目标/占位 |
| requirement_category | 测试需求 |
| sub_requirement_l1 / l2 / l3 | 三层测试子需求，分别保留 |
| requirement_ids | 需求ID(s) |
| related_testcases | 关联用例名称 |
| directed_stimulus | 直接用例激励描述(Optional)，所有测试点必填 |
| environment_checks | 环境检查说明 |
| design_version | 标签 |

所有主度量的必要配置、接口请求、预期及 `需要 check` 说明均保留在 `directed_stimulus`，不能为了套样例把它移成 FCOV 或丢失。Markdown 的 `<br>` 在 XLSX 中转成单元格换行，HTML 保留分行；不截断长配置说明。英文列名只是显示映射，检查、度量目标及下游维护权不改变。六张主表继续使用同一套完整字段，以免套参考表的短列结构丢掉必要激励和追溯。Config Space 的对象/字段、Dynamic Input 的接口/参数放在 L1–L3 与激励描述；Performance 的负载/测量窗口写激励，量化预期写描述/检查。两张问题表使用[大纲](tp-outline.md)规定的专用英文列。

## 修订和权威内容

13 字段工作 Markdown 是现有校验器的输入格式，不要求用户交付或维护 Markdown。修改已有 XLSX 时，先读取用户指定的最新工作簿及全部业务/附录 Sheet，按以上映射还原工作数据，保留真实用例和手工修改；不得用缓存 Markdown 覆盖新版 Excel。

当前脚本支持“工作 Markdown → 所选格式”的单向导出，不提供自动 XLSX 回读。XLSX 修订需通过可用的表格读取工具提取并人工核对；数据源冲突先定位版本及用户修改，再决定更新。多份文件均有独立修改而无法判定权威时，询问用户采用哪份。

## 导出及验证

通用入口见 [交付说明](delivery.md)。XLSX 使用 Node.js 的 `@oai/artifact-tool`，Python 编排与 MD/HTML 校验只使用标准库。运行环境由可用运行时提供，不写死个人机器路径。

校验所有场景的原 13 字段映射、唯一点名、分类计数、状态来源及附录保留。重新读取导出的工作簿核对值，不只检查成功生成文件；按 Sheet 查看代表性区域，特别是长描述、右侧检查列和附录，调整行高/换行而不删字。未选格式不生成交付文件。
