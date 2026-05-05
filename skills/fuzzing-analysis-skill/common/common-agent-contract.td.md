# 通用 Agent 公共协议文档

## 1. 目标

- 定义所有 skill 共享的接入协议和数据协议。
- 保证主 Agent、skill 入口和公共模板对同一套规则有一致理解。
- 让业务 skill 只实现自己的逻辑，不重复定义公共格式。

## 2. 范围

- 本文档只描述公共协议，不描述模板内部实现。
- 本文档适用于所有 skill。
- 本文档覆盖 `SKILL.md` 约定、参数协议、结果协议、状态协议、日志协议、工作目录协议、错误边界和兼容性策略。

## 3. skill 协议

- 每个 skill 必须提供自己的说明文件 `SKILL.md`。
- `SKILL.md` 负责定义该 skill 的能力范围、入口文件、输入契约、输出契约、阶段约束和是否允许修改文件。
- `SKILL.md` 必须明确该 skill 依赖的 `schema_version`、`skill_version` 和必填字段。
- `SKILL.md` 必须写明主 Agent 应如何调用该 skill，包括入口文件路径、参数组织方式和返回结果的读取方式。
- 主 Agent 只能在读取并理解 `SKILL.md` 后，才允许组装参数并调用对应入口文件。

## 4. 参数协议

- 所有调用都使用统一的结构化 `payload` 对象。
- `payload` 顶层只保留编排元信息，业务参数集中放在 `input`，运行时上下文集中放在 `context`。
- `payload` 顶层必须包含 `schema_version`、`skill_name`、`skill_version`、`task_id` 和 `run_mode`。
- `phase_id` 是可选字段，仅在该 skill 处于分阶段执行时填写；未进入分阶段执行时应为 `null` 或省略。
- `input` 用于承载具体业务参数，由各个 skill 根据自己的 `SKILL.md` 定义字段结构和必填约束。
- `context` 用于承载运行时附加信息，例如上游阶段结果、trace 信息、重试次数、调度来源、环境信息和 `project_root`。
- `constraints` 是 `payload` 的顶层独立字段，用于承载执行约束，例如超时时间、只读模式、是否允许修改文件、输出粒度等控制信息。
- 主 Agent 在调用 skill 前，必须先读取该 skill 的说明文件，再按其中定义的参数契约组装 `payload`。
- 所有扩展字段都应放入 `input` 或 `context`，禁止随意新增顶层字段。

## 5. 日志协议

- 日志记录必须落在任务执行项目根目录下的 `.agents_workdir` 中。
- 主 Agent 在调用 skill 时，需要通过 `context.project_root` 传入当前任务对应的项目根目录。
- 公共模板根据 `project_root` 自动创建工作目录，推荐路径为 `{project_root}/.agents_workdir/{skill_name}/{task_id}`；如果当前处于分阶段执行中，再追加 `/{phase_id}`。
- 工作目录由公共模板统一创建，skill 入口不直接拼接目录路径。
- 工作目录下至少应包含 `logs/`、`input/`、`output/` 和 `tmp/` 这几个子目录。
- `logs/` 用于保存执行日志，`input/` 用于保存本次调用的参数快照，`output/` 用于保存结构化输出，`tmp/` 用于保存临时文件。
- 日志内容需要包含 Agent 名称、任务编号、阶段信息、工作目录路径、状态变化和关键输出。

## 6. 状态协议

- 状态回传采用统一的 `status` 协议。
- `status` 只允许使用固定枚举值，建议定义为 `success`、`failed`、`running`、`blocked`、`needs_review`、`waiting`。
- `running` 表示任务正在执行，`waiting` 表示已完成当前动作但需要主 Agent 决定下一步，`blocked` 表示当前阶段无法继续，需要外部条件或人工介入。
- `success` 和 `failed` 作为终态，分别表示本阶段执行完成或执行失败。
- `needs_review` 用于表示当前结果已产出，但需要主 Agent 或人工确认后才能进入下一步。
- `status` 负责描述当前执行结果，`next_action` 负责描述主 Agent 接下来应该怎么处理，两者不能混用。
- `next_action` 只允许表达调度动作，例如继续、重试、暂停、等待确认或转人工，不承载业务结果。
- 主 Agent 依据 `status` 和 `next_action` 共同决定是否继续执行下一阶段、重试当前阶段、暂停流程或转人工处理。

## 7. 结果协议

- 结果输出采用统一的结构化 `result` 对象。
- `result` 顶层应与 `payload` 保持对称，至少包含 `schema_version`、`skill_name`、`task_id`、`phase_id`、`status`、`summary`、`output`、`context`、`error`、`next_action` 和 `trace_id` 等字段。
- `status` 用于表示本次执行结果，建议固定为 `success`、`failed`、`running`、`blocked`、`needs_review`、`waiting` 等枚举值。
- `summary` 用于给主 Agent 提供简短结论，要求可直接用于日志和调度判断。
- `output` 用于承载业务结果，由各个 skill 按自己的返回契约填写。
- `context` 用于承载可以继续传递给下一阶段的上下文信息，例如上游阶段结果、派生参数、局部状态和中间产物。
- `error` 仅在失败或阻塞时返回，必须包含错误码、错误消息和必要的定位信息。
- `next_action` 用于告诉主 Agent 下一步应该继续、重试、暂停、等待确认还是转人工处理。
- `result` 需要能够被主 Agent 直接消费，不要求主 Agent 重新解析业务逻辑。

## 8. 工作目录协议

- 工作目录由公共模板在任务开始时创建。
- 工作目录的创建必须以 `context.project_root` 为基础，禁止 skill 自行推导其他根目录。
- `.agents_workdir` 目录用于存放本次任务的全部执行产物，任务开始前如果不存在则自动创建。
- 任务结束后，工作目录默认保留，便于回溯、排障和主 Agent 继续消费中间产物。
- 是否清理工作目录应由上层编排策略决定，公共模板只负责创建和写入，不默认删除。
- 失败任务的工作目录必须保留现场，方便排查失败原因。

## 9. 错误协议

- 参数校验失败必须在业务执行前返回，状态建议为 `failed`，并在 `error` 中给出字段级原因。
- 运行时异常必须捕获并转换为结构化错误，不允许直接把原始异常抛给主 Agent。
- 外部依赖不可用、文件系统不可写或项目根目录缺失时，必须返回 `blocked` 或 `failed`，并明确说明阻塞原因。
- 可重试错误和不可重试错误需要区分处理，是否重试由主 Agent 根据 `next_action` 决定。
- 错误信息必须稳定、结构化，便于主 Agent、日志系统和后续自动化工具消费。

## 10. 兼容性策略

- 所有 `payload` 和 `result` 都必须带 `schema_version`。
- 新字段只能通过向后兼容方式增加，不能破坏既有字段语义。
- 如果 `schema_version` 不匹配，公共模板必须直接拒绝执行，并返回明确的兼容性错误。
- `skill_version` 用于标识某个 skill 自身的实现版本，不参与公共协议定义，但应记录在结果中，便于排障。
