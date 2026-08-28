# ADR 0001：Codex harness 不作为 V0 产品运行时

- 状态：已接受
- 日期：2026-08-28

## 背景

OpenAI 已开源 Codex CLI/harness，并提供 Codex App Server、Codex Exec 和 TypeScript SDK。
需要判断能否直接替换本项目的 Agent 底层。

## 决策

V0 不把 Codex harness 作为面向施工安全质量用户的产品运行时。继续按照 Hello-Agents V1.0.3
教程，采用 Python 单 Agent、结构化输出和少量受控领域工具。Codex 继续作为开发、审查、测试和
维护本仓库的工程 Agent 使用。

## 理由

1. Codex harness 的首要产品场景是软件工程，内置文件、Shell、沙箱、diff 和代码线程能力；
   本项目需要的是问题分类、知识依据、整改状态机和人工复查。
2. 官方 TypeScript SDK 通过子进程包装 Codex CLI，App Server 通过 stdio JSON-RPC 暴露完整
   线程和工具事件；直接接入会增加本地进程、权限、认证、事件桥接和部署复杂度。
3. 给予施工现场 Agent Shell/文件系统能力会扩大不必要的权限和安全面。
4. 当前后端是 Python/FastAPI，且团队已配置 OpenAI 兼容模型接口；Hello-Agents 路径更短、
   更符合现有教程和单 Agent MVP。

## 可以借鉴的能力

- `Thread → Turn → Item` 的可观测事件模型。
- 工具注册、结构化输出、有限循环和失败轨迹。
- 用户批准后才执行高风险工具。
- 工作区隔离、权限最小化和结构化 Trace。
- `AGENTS.md` 与仓库内文档作为开发事实来源。

## 重新评估条件

出现以下需求时可单独做技术验证：

- 产品真的需要让 Agent 安全地操作本地文件或执行命令；
- 需要长时间运行、恢复、分叉的线程及完整事件流；
- 团队决定改用 Codex App Server，并能承担独立进程、认证和权限治理；
- 先完成沙箱、隐私、成本和模型兼容性验证。

## 官方参考

- https://github.com/openai/codex
- https://github.com/openai/codex/tree/main/sdk/typescript
- https://openai.com/index/unlocking-the-codex-harness/

Codex 仓库采用 Apache-2.0 许可证；许可允许使用不等于它适合当前领域运行时。

