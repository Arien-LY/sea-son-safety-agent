# 文字请求等待与真实执行状态契约

> 2026-08-31：`responding`和`content_delta`的安全流式展示增量见
> `docs/unified-chat-routing-contract.md`；原 progress/result/error 边界继续兼容。

目标：发送后立即显示用户消息、清空输入；等待展示经过秒数、真实后端步骤及实际工具名，失败可恢复。
教程依据：Hello-Agents V1.0.3 第7/9/12章与 Extra09；不显示隐藏思维链，不用前端计时器编造执行进度。
当前行为：基线 bb4206f 在localhost已修复消息滞留；Chrome DevTools在用户局域网HTTP页面证实
`isSecureContext=false`、`crypto.randomUUID`不存在、输入仍为“你好”、状态仍为“正在回复”。
发送在try之外调用该API，模型请求尚未发出就中断。另隔离浏览器复现只有静态等待、无真实步骤与时间。
验收条件：见下方 P01–P08；旧 HTTP 接口保持兼容，正式工单状态与确认边界不变。
允许修改：文字服务调用边界、只读进度传输、前端文字 API/组件/样式及相关测试、文档和 Fake 验收脚本。
禁止修改：.env、密钥、依赖、Phase1/3冻结结构、工单权限、图片/知识业务逻辑；禁止真实/付费模型调用。
测试命令：相关 pytest、npm test、scripts/verify.ps1、隔离浏览器。
人工确认点：不把本次 Fake 速度视作真实模型性能；取消等待不承诺取消供应商计算或计费。

## 审计与变更门禁

- 模式：full-scan，检查 agents/backend/frontend/scripts/tests/contracts；排除 .venv、node_modules、dist、运行数据及密钥。
- 文字请求生命周期：Local Fix / Local Fix Only，包含用户明确要求的真实状态展示增量；不是重写 Agent。
- 基线：49 项文字/工作台 pytest、7 项前端行为测试通过；当前5173已提供乐观消息代码，无法证明用户旧标签页已更新。
- 分段实现：服务端可观察生命周期；浏览器消费真实事件；联合验收。整个主题预算≤16文件、≤1100行文本变化。
- 禁止顺带修复其他审计发现；独立列入待办。若需新依赖、持久后台任务系统或修改业务权限则停止重新评估。
- 回退：本分支未合并前可放弃；保留旧 JSON 端点，但不在流故障后自动回退调用，以免重复计费。

## 行为与所有权

- 浏览器只计量本次操作实际经过时间，不按秒数切换步骤或编造百分比。步骤由服务器事件决定。
- 新增 POST `/api/text-consultations/stream` 与 POST `/api/text-consultations/{id}/proposal/stream`。
  输入复用已有严格契约；传输为 UTF-8 NDJSON。旧非流式端点不删除。
- 事件严格为 `progress` / `result` / `error`。progress只包含递增seq、非负elapsed_ms、白名单stage和tool。
  阶段：queued、preparing、model_running、validating、tool_running、completed；唯一工具名为propose_issue_record。
  普通文字回复不调用业务工具，不能显示检索/派单等未执行动作；提案只有真正进入工具调用路径才显示工具名。
- result含既有TextResponse或ToolResult；error只有稳定错误码、安全消息。不得传参数原文、环境配置或隐藏思维链。
- 后端锁竞争最多等待1秒，超时返回text_busy，不无限积压。已有单进程序列化和幂等机制保留。
- 请求解析不合法仍HTTP400；流建立后的失败通过error事件返回，不谎称成功。
- 浏览器整体35秒截止覆盖连接、事件和正文读取；断流/非法事件明确失败，不自动重试或重新发起付费请求。
- 发送立即显示用户气泡；结束后显示本次用时，可查看已发生的步骤；失败恢复同一请求输入与幂等标识。
- 请求编号兼容局域网HTTP：优先randomUUID，否则使用getRandomValues生成128位随机ID；不得用时间戳替代。
  发送准备和编号生成纳入try/finally；任何准备错误也必须恢复输入并结束忙碌。
- 模式切换/卸载取消等待，不允许旧回调污染新会话。计时器、流读取器与监听器结束后释放。
- “服务已连接”不能表示模型已验证可用；runtime只验证本地配置，文案改为明确的配置状态。

## 验收场景

- P01 延迟Fake发送：输入立即清空、用户气泡立即出现；等待秒数增长，真实model_running可见。
- P02 真实事件顺序：queued→preparing→model_running→validating→completed→result；普通回复tool恒null。
- P03 工具提案：只有人工点击且服务端资格满足才出现tool_running/propose_issue_record，不自动保存。
- P04 服务忙：并发慢请求占锁时后续请求≤1秒锁等待后明确text_busy，不再无上限队列等待。
- P05 超时、断流、空/非法事件、SDK错误：显示安全失败并恢复输入；不自动重试，不泄漏原异常。
- P06 取消/切换：释放父级忙碌与计时器，晚到事件/回答不回填；原消息可手动重试且不重复入列。
- P07 桌面及390×844：等待/详情无溢出，状态可访问，页面无控制台错误；历史/提交仍可用。
- P08 幂等重放、咨询高风险保留和原确认/保存/工作流测试全部通过；模型调用0次。
