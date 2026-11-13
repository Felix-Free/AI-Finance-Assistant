# Phase 2 C 文档说明与交接

> 核对基准：2026-11-13 的 C 分支、`origin/main` 需求表及 D 的 `feat/D-phase2-measurement` 分支。本文区分 C 已完成的文档工作与 D/E 尚未完成的实现、验证工作；不把 `pending` 当作通过。

## C 已交付的内容

| 文件 | 用途与当前口径 |
|---|---|
| [`runtime-policy-catalog.md`](runtime-policy-catalog.md) | RP-001–007 定义模型内容、配置/传输/协议、规则拒绝、调用日志和存储失败时如何停止；记录成功与拒绝决策各自的 `call_id` 证据配对。RP-007 写明独立 `StorageError`、不转成 `policy:*`，并标出 D 尚未满足的边界。 |
| [`evaluation-logbook.md`](evaluation-logbook.md) | 对齐 main 的 NFR-001–007，写明指标、阈值来源、测量办法、预期证据和当前状态。NFR-004 的 0 表示不能提交任何密钥；NFR-007 的 1.0 表示每条获批不变量都要有能检出移除守卫的离线反例测试，需求状态仍待确认。其余数值阈值在需求表中是 `null`，未自行编造。另有 C 对存储层的代码审查记录。 |
| [`mcp-tool-manifest.md`](../code-governance/mcp-tool-manifest.md) | 登记 Phase 2 的存储、测量、报告和 pipeline 入口，注明仓库未配置 MCP server/tool；入口登记不授予绕过策略校验的权限。 |
| [`permission-model.md`](permission-model.md) 与 [`.opencode/permissions.jsonc`](../../.opencode/permissions.jsonc) | 为 Phase 2 测量工作开放 `data/**`、`scripts/**`、`docs/measurements/**` 的读写范围和指定命令，保留其他限制。 |
| [`docs/ai-use-log.yaml`](../ai-use-log.yaml) 与 [`transcripts/60339160-QiangWanyun.md`](../../transcripts/60339160-QiangWanyun.md) | 保留 C 的 Phase 2 工作记录；现有会话为 5–12，没有第 13 次记录。 |

## 交接给 D：实现与安全边界

1. **存储不能绕过规则。** 当前 `pipeline.process` 先调用 `policy_core.validate_record` 再写入，但直接调用 `storage.append_validated(record)` 只检查结构和基本类型，可写入违反金额、类别或预算规则的记录。调用方提供偏低的 `spent` 时，pipeline 也不会与已持久化累计金额核对。已批准的 `expected_spent` 校验设计记录在策略目录 §5.5；D 当前函数仍只有 `record` 参数，不能把设计视作已实现。
2. **存储失败分类。** 读取已存记录时，列表型 `call_id` 会抛出未转换的 `TypeError`；缺失的 ID 被跳过，空字符串没有被拒绝。直接写入不可 JSON 序列化的 `decided_at` 也会抛出未转换的 `TypeError`。这些路径尚未全部满足 RP-007 的 `StorageError` 合同。
3. **部分写入与日志。** 存储和拒绝证据都使用追加写入；发生中途写入错误时，尚无回滚保证。`call_llm` 的部分传输/协议错误仍把 `str(exc)` 写入日志，需满足短且不泄露密钥的错误信息规则。存储失败是否另记专门证据及其格式尚待确定。
4. **报告口径。** `report_tokens.py` 已有单次调用、按 `session_id` 聚合及总计；按 `request_id` 聚合尚未实现。`measure_latency.py` 标头的 NFR 编号应按 main 修正为 NFR-001。

## 交接给 E 与 B：验证和需求确认

- **E：** 运行并保存 NFR-001–007 中适用的测量/扫描证据，再把实际结果及证据文件填入评估台账。重点覆盖调用日志与存储/审核记录的两种 `call_id` 配对、日志写入失败时的阻断、直接调用存储的反例、偏低 `spent`、两类 `TypeError` 和部分写入。D 的 `test_evidence_join.py` 当前为跳过状态，不能算验证通过。
- **B：** 维护 `docs/req/requirements.yaml`。当前 NFR-001/002/003/005/006 的数值阈值为 `null`；NFR-007 的 1.0 仍是 `pending_confirmation`。如需新增或确认目标，应先更新需求表，再同步评估台账。NFR-002 的令牌聚合只作描述统计，不设臆造的通过阈值。
- **B 与 C：** 当前 `AGENTS.md` 的路径表仍未列出测量目录，而 OpenCode 权限配置和权限模型已允许这三个目录。`AGENTS.md` 声明冲突时从严，合并前需要由其所有者 B 核对并同步这项权限口径。

## 完成状态

C 的三项文档交付、权限调整和存储代码审查已写入分支。**系统级验收尚未全部完成**：上述 D 实现缺口及 E 的测量/测试证据仍待处理。评估台账中的 `pending` 是如实记录的当前状态，不能据此宣称系统安全边界已获验证。
