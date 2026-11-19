# Phase 3 C：与 D 确认最终安全口径（设计确认稿）

> **状态：D 已回复；设计已确认；实现与证据仍待完成。** 本文记录 D 对目标设计的确认，
> 属于**设计确认，不是最终审计证据**。D 的实现尚未合并，也未在本 C 分支本地验证；
> 因此下文所有 storage / `call_id` 行为都是**已确认的目标设计**，不是当前分支已实现的代码。
>
> **D-reported 引用（未在本地验证，禁止当作最终证据）：**
> - D 实现分支：`feat/D-phase3-hardening`
> - 中间实现提交：`1332483`
> - 日志相关提交：`4281ea3`
>
> 标注：**D-reported / interim / not independently verified**。并发修复后的最终提交、
> ADR-003、以及 E 的回归结果**仍然 pending**。
>
> **当前 C 分支现实（未改变）：** 分支 `feat/c-phase3-policy-60339160` 的 `src/`、`test/` 与
> `origin/main`（`6997cef`）逐字节一致（`git diff origin/main -- src test` 为空），本分支
> **没有 `src/storage.py`**，也**没有** `call_id` / `request_id` / `session_id`。请勿把本
> 文档中的目标设计当作本分支已有实现。

## 1. 目的

Phase 3 C 的目标是完成最终安全审计，并确认架构文档、运行时策略和最终代码保持一致。

本次重点不是增加新的业务规则，而是确认：

1. 任何模型输出都不得在通过 `policy_core` 之前影响正常业务数据或 storage；对原始模型输出的
   audit 日志按设计发生在策略校验之前。
2. 所有正常业务数据与 storage 的写入路径都遵守 validation-before-write（先校验、后写入）；
   原始模型输出的 audit 日志不属于业务状态变更。
3. 日志、错误处理和 storage 失败都遵守 fail-closed；
4. 每个结论都有可复现的代码、测试或运行证据。

> **安全原则（英文原文，作为确认口径）：** No model output may affect normal business data
> or storage before passing through `policy_core`. Audit logging of raw model output occurs
> before policy validation by design.

## 2. D 开发前需要统一的端到端处理路径

这里确认的是后续开发约束，不是要求 D 现在提供最终 branch、commit 或测试结果。
如果实现过程中发现代码需要偏离这条路径，请先和 C 讨论，避免安全口径在开发过程中被改变。

建议最终路径固定为：

```text
call_llm.extract()
        ↓
pipeline.process()
        ↓
policy_core.validate_record()
        ↓
storage.append_validated()
```

（注：本分支目前只实现到 `policy_core.validate_record()`；`storage.append_validated()` 是
待 D 实现的部分。）

请确认：

1. `pipeline.process()` 是否是唯一允许把模型结果送入业务处理的入口？
2. `call_llm.extract()` 是否只返回未验证的模型结果？
3. 是否存在其他模块直接调用 `extract()` 后写入 storage 的路径？
4. 是否所有正常数据写入都发生在 `policy_core.validate_record()` 成功之后？
5. `src/call_llm.py` 是否仍然是唯一发起模型网络请求的模块？

确认结果（D 设计确认）：
1. 是。`pipeline.process()` 是唯一的业务入口。
2. 是。`call_llm.extract()` 只返回未验证的解析结果，只附加系统元数据（如 `call_id`），
   不信任模型内容。
3. 否。目标设计中不存在其他模块调用 `extract()` 后直接写入 storage 的路径；所有正常写入
   都经过 `pipeline.process()` → `policy_core` → `storage`。
4. 是。正常业务数据与 storage 写入只发生在 `policy_core` 校验通过之后。
5. 是。`src/call_llm.py` 仍是唯一发起模型网络请求的模块。

> 注：以上为设计口径；实现合入与本地验证仍 pending。

## 3. policy_core 与 storage 的关系

> 本节是**目标设计**确认。本分支没有 storage 代码，答案描述 D 将要实现的行为。

为了防止未来新增调用者绕过 `policy_core`，请确认以下设计：

1. storage 是否会对直接传入的数据再次执行必要的 invariant 检查？
2. 如果 storage 不重复检查，如何保证它不会被直接调用来写入非法数据？
3. `spent` 的权威来源是调用者传入值，还是 storage 中的累计值？
4. 如果调用者传入的 `spent` 与 storage 中的累计值不一致，系统应该：
   - `reject`
   - 抛出独立的 `StorageError`
   - 进入 `REVIEW`
   - 其他：`[填写]`
5. `spent + amount == budget_limit` 是否允许？目前建议：允许。
6. `spent + amount > budget_limit` 是否始终拒绝并进入 `REVIEW`？目前建议：是。

确认结果（D 设计确认）：
1. 是。storage 执行 defense-in-depth 的 invariant 校验（纵深防御，不替代 `policy_core`）。
2. 直接调用 storage 时若违反 amount/category/budget invariant，**仍然**抛出
   `PolicyError(policy:*)`，不会因为来自 storage 而改成 `StorageError`。这样即使未来出现
   绕过 `policy_core` 的调用者，非法数据也无法经由 storage 进入。
3. `spent` 的权威来源是 **storage 中持久化的累计金额**（persisted cumulative spend），
   不是调用者传入值。
4. 若调用者传入的 `spent` / `expected_spent` 低于持久化累计金额，抛出独立的
   `StorageError`（不是 `PolicyError`，也不进入 `REVIEW`）。
5. 允许。`spent + amount == budget_limit` 被接受（等于预算不越界）。
6. 是。`spent + amount > budget_limit` 始终拒绝，抛出
   `PolicyError(code="policy:budget", review=True)`。

> `expected_spent` 是**校验参数**，不是持久化字段。它必须等于持久化累计金额或更高；
> 更低则 `StorageError`，更高则允许但校验更严格（`total == expected_spent + amount`
> 必须成立）。以上为设计口径；实现合入与本地验证仍 pending。

## 4. 错误分类和 fail-closed 行为

请确认最终错误类型和处理口径：

| 场景 | 错误类型 | 是否重试 | 是否允许写入正常数据 | 是否需要证据日志 |
|---|---|---:|---:|---:|
| 非法 JSON | `JSONDecodeError` | 否 | 否 | 是，`not_json` |
| 配置缺失 | `LlmTransportError` | 否 | 否 | 是，一条调用日志 |
| 网络/HTTP/响应 envelope 失败 | `LlmTransportError` | 否 | 否 | 是，一条调用日志 |
| pipeline 来源的 amount/category/budget invariant 失败 | `PolicyError(policy:*)` | 否 | 否 | 尝试恰好一条 `logs/review.jsonl`；若该写入失败则抛 `StorageError`，不写正常数据 |
| 直接 storage 调用的 amount/category/budget invariant 失败 | `PolicyError(policy:*)` | 否 | 否 | 否，不写 review 行 |
| storage I/O / 记录形状 / 重复 `call_id` / 算术一致性 / 持久化失败 | `StorageError`（独立，绝不改写为 `policy:*`） | 否 | 否 | 不得伪装为 `policy:*` |
| `llm_calls.jsonl` 写失败 | `LlmTransportError` 或约定的日志错误 | 否 | 否 | 无法写入时必须停止 |
| `review.jsonl` 写失败 | `StorageError` | 否 | 否 | 不得产生正常数据 |

请特别确认：

1. 是否完全禁止隐藏 retry？
2. 是否禁止用 catch-all 把不同错误统一转换？
3. review 日志写失败时，是保留原始 `PolicyError`，还是改抛独立的（非 `policy:*`）
   错误？**当前本分支实际行为（需要 D 修正）：** `src/pipeline.py::_append_review` 在
   `OSError` 时抛出 `PolicyError(code="policy:budget", review=True)`，把证据写失败错误地
   归为预算规则拒绝；请确认目标行为，并安排修正。
4. storage 写失败时，是否保证没有半条记录或部分状态变化？
5. 如果 append-mode 无法保证原子性，最终实现是否需要改为 atomic write？

确认结果（D 设计确认）：
1. 是。完全禁止 hidden retry。
2. 是。禁止 catch-all 转换把不同失败类别压缩成同一种。
3. **目标设计：** review 证据写入失败时抛出独立的 `StorageError`，保留安全短错误码，
   不把它伪装成 `PolicyError`，也不产生正常数据。
   **注意：** 当前本 C 分支代码仍是旧的错误行为（`PolicyError(code="policy:budget")`），
   本次文档更新**不修复**它；修复属于 D 的实现工作，仍 pending。
4. 目标设计：使用**唯一临时文件 + 文件锁**，围绕 read/check/write/replace 保证原子性，
   不允许半条记录或部分状态变化。**该原子性目标尚未实现验证（pending）。**
5. 是。目标是 atomic write（temp file + lock + replace），取代 append-mode。并发修复、
   ADR-003 仍 pending。

**review 证据的来源区分（设计确认）：**
- **直接调用 storage** 不写 review 证据（无 review 行）。
- **来自 pipeline 的 policy 拒绝**尝试恰好写一条 `logs/review.jsonl`；若该写入失败，则操作
  抛出 `StorageError`，且不写入正常数据。不得在该写入本身失败时仍声称存在 review 行。

**错误分类（设计确认）：** storage 的 I/O、记录形状、重复 `call_id`、算术一致性、持久化
失败都抛独立的 `StorageError`，而不是 `policy:*`。

## 5. 日志和 call_id 口径

请确认以下字段和责任（注：`call_id` / `request_id` / `session_id` 在本分支尚未实现，属
D 待实现项）：

1. `call_id` 是否只允许由 `src/call_llm.py` 生成？
2. 模型返回的同名字段是否必须被忽略，不能覆盖系统生成的 `call_id`？
3. `call_id` 是否在进入 `policy_core` 前移除？目前建议：是，policy_core 只处理业务字段。
4. 每次 `extract()` 尝试是否恰好写一条 `logs/llm_calls.jsonl`？
5. 每次 policy rejection 是否恰好写一条 `logs/review.jsonl`？
6. accepted decision 的证据是否通过 `llm_calls.call_id == storage.call_id` 连接？
7. rejected decision 的证据是否通过 `llm_calls.call_id == review.call_id` 连接？
8. `request_id` 是否代表一次用户请求，`call_id` 是否代表一次模型调用？
9. `session_id` 是否代表一个进程运行，而不是一个真实用户 session？
10. raw response、HTTP body 或 input 是否可能包含 secret 或个人财务数据？如果可能，是否需要脱敏？

**日志字段完整性（需要 D 确认并修正）。** 当前本分支的三条日志路径**没有**都写出四个
必需字段 `input` / `raw` / `parsed` / `error`：成功路径（`src/call_llm.py:156`）缺少
`error`；配置失败路径（`:124`）和传输/HTTP/协议失败路径（`:140-145`）缺少 `raw` 与
`parsed`。请确认“每次调用都写齐四个字段”的要求，并在实现中统一。

确认结果（D 设计确认）：
1. 是。`call_id` 只由 `src/call_llm.py` 系统生成。
2. 是。模型输出中同名/伪造字段必须被忽略，不能覆盖系统生成的 `call_id`。
3. 是。`call_id` 在进入 `policy_core` 之前被移除；`policy_core` 只处理业务字段。
4. 是。每次 `extract()` 尝试恰好写一条 `logs/llm_calls.jsonl`。
5. 是。来自 pipeline 的每次 policy rejection 尝试恰好写一条 `logs/review.jsonl`；若该写入
   失败，则操作抛出 `StorageError` 且不写入正常数据（写入失败时不得声称存在 review 行）。
6. 是。accepted decision 的证据通过 `llm_calls.call_id == storage.call_id` 连接。
7. 是。rejected decision 的证据通过 `llm_calls.call_id == review.call_id` 连接。
8. 是。`request_id` 代表一次用户请求，`call_id` 代表一次模型调用。
9. 是。`session_id` 代表一次进程运行，而不是真实用户 session。
10. **是，且尚未定稿。** raw response / HTTP body / input 可能包含个人财务数据或 secret。
    **未脱敏地记录 input/raw 没有作为最终设计被批准。**

> **隐私要求（pending，未批准）：** 四字段日志模式并不等于批准未脱敏内容。后续必须在以下
> 两条候选路径中择一确定：
> - 在持久化前做最小化 / 脱敏；或
> - 施加可执行的“仅合成数据”运行时约束。
>
> 另：`StorageError` 消息与证据日志**不得**出现原始异常字符串、URL、HTTP body、凭证或
> 敏感数据；如需要，可单独保留安全短错误码。

> 注：`call_id` / `request_id` / `session_id` 的语义与证据 join 属于**设计确认**，但在
> 当前 C 分支上**仍未实现、未验证**（pending）。

## 6. 模型输出和 prompt injection

目前建议继续坚持：

- prompt 只负责请求结构化输出；
- prompt 不是安全规则的最终执行位置；
- category 白名单、金额和预算规则只由 `policy_core` 执行；
- prompt injection 最多导致模型输出被拒绝，不能改变 deterministic policy；
- 不为了处理 injection 而在 C 文档中新增未经批准的业务规则。

请确认：

1. 是否只依赖 deterministic validation 来保证 prompt injection 不能突破安全规则？
2. 是否需要额外的输入清洗或 injection policy？如果需要，请明确其触发条件、动作和测试方式。
3. 当前 8 个 category 是否已经是最终 whitelist？

确认结果（D 设计确认）：
1. 是。prompt injection 由 deterministic validation 处理，不依赖 prompt 文本。
2. 否。当前没有批准额外的 injection policy；如未来需要，需先明确触发条件、动作与测试方式。
3. **否，最终性 pending。** 现有 8 个 category 保持不变；但最终 whitelist 的归属/定稿仍
   需 **B/C 确认**。D 不得自行更改白名单。

## 7. D 的回复摘要（设计确认，不是最终审计证据）

> **标注：design confirmation, not final audit evidence.** 以下只汇总 D 对目标设计的确认，
> 不代表任何安全属性已在本 C 分支被验证。

**已确认的设计口径（摘要）：**
- `pipeline.process()` 是唯一业务入口；`src/call_llm.py` 是唯一模型网络入口。
- `call_llm.extract()` 只返回未验证结果并附加系统元数据。
- 正常业务/storage 写入只在 `policy_core` 校验通过后发生。
- storage 执行 defense-in-depth 校验；直接调用 storage 时 invariant 违规仍抛
  `PolicyError(policy:*)`。
- 直接 storage 调用不写 review 证据；pipeline 级 policy 拒绝尝试恰好写一条 review 线，
  若写失败则抛 `StorageError` 且不产生正常数据（写失败时不得声称存在 review 行）。
- persisted cumulative spend 权威；`expected_spent` 是校验参数（非持久字段），低于持久值
  抛 `StorageError`，更高允许但更严格。
- 预算相等接受；超预算抛 `PolicyError(code="policy:budget", review=True)`。
- 禁止 hidden retry；禁止 catch-all 合并不同失败类别。
- `call_id` 系统生成、不可被模型覆盖、进入 `policy_core` 前移除。
- 原子性目标：唯一临时文件 + 文件锁（read/check/write/replace）。

**D-reported 引用（未本地验证）：** 分支 `feat/D-phase3-hardening`；中间实现提交
`1332483`；日志提交 `4281ea3`。均标注为 **D-reported / interim / not independently
verified**。

**仍然 pending：**
- 并发实现与回归、ADR-003、最终提交、最终合并；
- E 的可复现回归结果；
- storage 原子性/无部分状态证明；
- `call_id` join、fail-closed 测试、no-bypass 测试、完整 logging-schema 测试；
- 隐私/脱敏策略（最小化/脱敏 或 仅合成数据约束）——未脱敏记录 input/raw **未批准**；
- 最终 category whitelist 归属/定稿（B/C）。

> 本文档不代表任何安全属性已被验证；最终审计结论需在上述证据到位后单独出具。
