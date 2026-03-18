# agent-hub

[![在线主页](https://img.shields.io/badge/site-live-78A8FF)](https://dominic789654.github.io/agent-hub/)
[![版本](https://img.shields.io/badge/release-v0.1.0-7EF0C4)](https://github.com/Dominic789654/agent-hub/releases/tag/v0.1.0)
[![协议](https://img.shields.io/badge/license-Apache--2.0-C0B0FF)](./LICENSE)

面向代码助手的本地优先多任务看板，用来在多个项目之间排队、路由、观察和交接任务。

快速入口：[在线主页](https://dominic789654.github.io/agent-hub/) · [中文 Demo](https://dominic789654.github.io/agent-hub/demo.zh.html) · [英文 Demo](https://dominic789654.github.io/agent-hub/demo.html) · [英文 README](./README.md) · [仓库](https://github.com/Dominic789654/agent-hub)

这个开源仓库是一个可迁移、可公开分享的最小版本，核心思路很直接：

- 用 `SQLite` 保存代码助手任务队列
- 把任务路由到本地仓库里的 `Codex`、`Claude Code` 等代码助手
- 显式表达依赖、重试、阻塞和人工接入
- 通过轻量网页和 `HTTP` / `CLI` 提供统一观察面

整个代码库刻意保持很小，依赖也尽量轻，主要使用 Python 标准库。

## 📌 一句话理解

`agent-hub` 不是为了替代 `Codex` 或 `Claude Code`。

它的作用是：给这些代码助手前面加一个清晰的多任务看板，让你只需要和助手对话，助手再把工作放到板子上执行和追踪。

## 📊 它适合谁

| 角色 | 适合场景 |
| --- | --- |
| 单个操作者 | 你要同时盯多个编码任务 |
| 多个本地仓库 | 任务分散在不同 repo |
| 已经在用代码助手的人 | 你已经在用 Codex / Claude Code / Kimi / Qwen |
| 需要显式交接的人 | 你想清楚看到失败、阻塞、人工处理点 |

## ✨ 主要能力

| 能力 | 作用 |
| --- | --- |
| 多任务队列 | 同时管理多个代码助手任务 |
| 项目路由 | 按 `project_id` 把任务送到对应 repo |
| 依赖控制 | 支持串行依赖和并行任务 |
| 人工接入 | 难题不会无限重试，会明确进入 `needs_human` |
| Saved Views | 快速筛出某类任务或某个助手的任务 |
| 轻量网页 | 用浏览器快速看整体状态 |

## 🤖 推荐使用方式

最推荐的工作流不是你自己频繁敲底层命令，而是：

1. 后台运行 `agent-hub`
2. 在另一个终端打开 `Codex` 或 `Claude Code`
3. 直接对助手说需求
4. 助手通过 `agent-hub` 创建、排队、检查、重试任务
5. 你通过网页看板统一看进度

推荐职责分层：

| 层级 | 负责什么 |
| --- | --- |
| 你 | 提需求、看结果、做最终判断 |
| Codex / Claude Code | 在 repo 里具体实现、分析、Review |
| `agent-hub` | 排队、路由、调度、依赖、交接、可视化 |

## 🚫 它不是什么

| 不是 | 原因 |
| --- | --- |
| 通用待办软件 | 核心对象是“代码助手任务” |
| 多租户 SaaS | 当前重点是本地优先 |
| 代码助手本体 | 真正写代码的还是 Codex / Claude Code |
| 重平台型系统 | 现在是轻量、可审计、可扩展 MVP |

## ⚡ 快速开始

环境要求：

- Python `>= 3.11`

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

## ✅ 最小验证

第一次验证时，统一使用公开 demo 注册表：

```bash
agent-hub version
agent-hub --projects-file examples/agent-driven-projects.example.json list-projects
agent-hub --projects-file examples/agent-driven-projects.example.json list-project-task-templates demo-codex
```

如果这几条命令都能正常执行，就说明本地安装已经准备好，可以继续公开 demo 流程。

## ⏱️ 五分钟体验方式

建议开三个终端：

- 终端 A：启动服务
- 终端 B：启动 dispatcher
- 终端 C：打开 `Codex` 或 `Claude Code`

**终端 A**

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json serve --port 8080
```

**终端 B**

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json dispatch
```

**终端 C：直接和代码助手对话**

可以直接说：

- `在 demo-codex 里创建一个任务，排查本地构建脚本为什么不稳定。`
- `在 demo-claude 里创建一个 review 任务，检查修复方案有没有风险。`
- `如果 review 没问题，就在 demo-codex 里启动 review-then-implement pipeline。`
- `查看 human inbox，告诉我哪些任务需要人工决定。`

这是这个项目最推荐的交互方式：  
你主要和代码助手对话，助手在底层调用 `agent-hub`。

如果你想在接入代码助手之前，先手动验证看板，也可以直接执行同一套公开流程：

```bash
python -m agent_hub --projects-file examples/agent-driven-projects.example.json run-task-template demo-codex delegate-task --input "Investigate why the local build script is flaky"
python -m agent_hub --projects-file examples/agent-driven-projects.example.json run-pipeline demo-codex review-then-implement --input "Add a dry-run mode"
python -m agent_hub --projects-file examples/agent-driven-projects.example.json dashboard
```

然后打开：

- `http://127.0.0.1:8080/`
- `http://127.0.0.1:8080/app`
- `http://127.0.0.1:8080/dashboard`

公开版默认 onboarding 路径统一使用 `examples/agent-driven-projects.example.json`。

## 📁 默认本地状态

- 数据目录：`./.agent-hub/`
- 数据库：`./.agent-hub/agent_hub.db`
- 项目注册表：`./.agent-hub/projects.json`

可通过这些方式覆盖：

- `--data-dir`
- `--projects-file`
- `AGENT_HUB_DATA_DIR`
- `AGENT_HUB_PROJECTS_FILE`

## 📚 继续阅读

- 架构说明：`docs/architecture.md`
- 助手优先使用方式：`docs/agent-driven-usage.md`
- CLI 演示：`docs/demo.md`
- 浏览器演示页：`docs/demo.zh.html`
- 发布清单：`docs/public-launch-checklist.md`

## 🔒 安全边界

- 示例里不依赖私有基础设施
- 不包含密钥
- 本地状态放在忽略目录里
- 破坏性操作保持显式触发

## 🤝 贡献

- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SUPPORT.md`
- `SECURITY.md`
