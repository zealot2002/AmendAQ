# mycs

**从已发布问答作答的智能客服——不靠检索回来的文本片段。**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](pyproject.toml)
[![Dev.to series](https://img.shields.io/badge/Dev.to-%22RAG%20%E7%9A%84%E7%BB%88%E7%82%B9%E6%98%AF%E7%9F%A5%E8%AF%86%22-blue)](https://dev.to/zealot2002/series/47162)

你先选一个知识库。模型只从标题列表里勾选已发布条目的编号，必须根据这些条目的完整原文撰写答复。规则校验器——而不是又一次模型调用——会拒绝编造义务或与原文矛盾的答复。

这是更大想法的一个可运行切片：RAG 的终点应该是知识，而不是更好的搜索。长期形态（Wiki、状态 API、知识缺口）见下文。今天能跑通的路径是 Dev.to 系列 [RAG 的终点是知识](https://dev.to/zealot2002/series/47162) 里写的：选人库、勾编号、规则核对。

[English README](README.md)

## 这和常见的 RAG 有什么不同

| | Chunk + 向量 + 生成 | mycs（已发布 FAQ + 勾选编号 + 规则核对） |
|---|---|---|
| 来源 | 原始文本片段 | 已发布的 FAQ 条目及其完整答案 |
| 召回 | 向量相似度 / 混合检索 | 模型读标题列表，只返回编号 |
| 证据 | 看起来"相似"的片段 | 被勾选条目的完整原文 |
| 校验 | 常常没有，或"你觉得这对吗？" | 确定性规则：引用来源、禁止编造义务、禁止自相矛盾 |
| 失败模式 | 从近似片段里 hallucinate 答案 | 空召回 → 拒绝作答 |

## 截图

Vue 管理界面的问答页右侧有一个过程面板，会展示每一步：跳过理解、分批勾选标题、工具调用、撰写、规则核对。

![过程面板](docs/images/process-panel-devto.png)

> 图片来自 [Dev.to 系列](https://dev.to/zealot2002/series/47162) 的真实截图。图中是较早的星河演示数据，但展示的工作流和本仓库当前运行的一致：跳过理解、批量勾选 FAQ 编号、加载完整原文、规则核对。

## 快速开始（Vue / mycs-api 路径）

这是当前默认的可运行路径。仓库里仍然保留了旧的 Ollama 建图、`kg_*` API、政务 demo、Gradio UI，但它们不是主入口。

1. 复制并编辑环境文件：

```bash
cp .env.example .env
# 编辑 .env，选择一家大模型提供商：
#   MYCS_LLM=glm    -> 填写 GLM_API_KEY
#   MYCS_LLM=ollama -> 把 OLLAMA_BASE_URL 指向你的 Ollama 主机
#   MYCS_LLM=openai -> 设置 OPENAI_API_BASE 和 OPENAI_MODEL
#   MYCS_LLM=groq   -> 设置 GROQ_API_KEY
```

2. 安装 Python 依赖并启动开发环境：

```bash
uv sync --extra dev --extra web
scripts/restart-dev.sh
```

脚本会在需要时自动安装前端依赖，然后启动 FastAPI 后端（`mycs-api`，端口 `8765`）和 Vite 前端（端口 `5180`），并打印本地访问地址，通常是 `http://127.0.0.1:5180/`。

3. 导入仓库自带的演示语料：

```bash
uv run python examples/demo/import_demo.py --lang zh
```

这会创建一个名为 **星际系统演示** 的虚构知识库，并把 `examples/demo/stellar_faq.zh.txt` 里的 10 对问答作为已发布条目导入。

4. 打开打印的地址，进入**知识库**，点开 **星际系统演示**，确认条目已发布。

5. 进入**问答**页，选择该演示库，输入示例问题：

- "季度奖金什么时候发放？"
- "每周最多可远程办公几天？"
- "可以带宠物来办公室吗？"（不在演示语料中，应拒答）

右侧过程面板会显示：理解步骤是否被跳过、模型勾了哪些 FAQ 编号、加载了哪些完整原文、规则核对是否通过。

### 进阶：CLI 问答

如果你已经有了一个 `document_id` 为 `my_kb` 的已发布知识库：

```bash
export MYCS_GRAPH_DOCUMENT=my_kb
uv run mycs "周六可以打电话找客服吗？"
```

CLI 路径偏进阶；Vue 界面是推荐的首选入口。

## 实际工作原理

1. **选人库。** 当界面里已经选定一个知识库后，Agent 会跳过通用的"理解问题"模型调用，因为上下文已由用户指定。
2. **列出已发布标题。** 加载该库所有 `published` 状态的 FAQ 条目。若数量不超过 `MYCS_FAQ_SINGLE_PASS_MAX`（默认 120），一次性把所有标题发给模型。
3. **模型只返回编号。** 模型被要求只返回匹配问题的 `section_refs`；不在列表里的编号会被程序丢弃。
4. **加载完整原文。** Agent 按编号读取每条 FAQ 的完整答案。
5. **依据原文撰写。** 模型只能用这些完整原文来写最终答复。
6. **规则核对。** `Verifier.verify_graph_answer` 检查答复是否引用了来源、是否编造义务、是否出现"必须……但未找到"这类矛盾。对有上限的数量题（例如年假），会由技能在撰写前根据问题和原文算出数值边界。

## 评测 / 可复现性

现在仓库里有一套可运行的评测，放在 `examples/eval/`：

```bash
uv run python examples/eval/run_eval.py --lang zh
```

它会导入 `examples/demo/stellar_faq.zh.txt` 里的虚构 **星际系统演示** FAQ，用 12 道题跑一遍 `AgentLoop`，再按 `examples/eval/RUBRIC.md` 里的评分标准打分。这些问题覆盖了产品的强项：编号选择、规则核对、程序计算数量、缺失时拒答。也支持不调用大模型的干跑模式：

```bash
uv run python examples/eval/run_eval.py --lang zh --dry-run
```

博客里提到的原始 **星河 13 题评测在当前仓库仍然无法复现**：

- `scripts/run_xinghe_eval.py` 里只有 10 道题，不是 13 道，且已在文件头加了明确说明。
- 评测用的源手册文件 `docs/星河科技_中文员工手册_知识库测试.txt` 缺失，脚本无法重新入库。
- 部分较老的 wiki-tree 评测报告已经过时。
- 某些测试硬编码了本地桌面路径。

## 限制与路线图

### 当前限制

- **不是通用向量 RAG。** 主路径刻意保持为已发布 FAQ 流程，不做开放域检索。
- **规模：** 一次性发送全部标题适合几十到几百条量级，不是百万文档搜索引擎。
- **核对：** 数量和义务已由规则检查，但当前规则仍可能过严（误伤）或遗漏某些改写后的矛盾。
- **目录钻取：** `wiki.toc.*` 和 `kg_*` 代码路径仍存在，但不是 Vue 界面使用的主路径。

### 路线图

**已完成**
- 以已发布 FAQ 为主要知识来源。
- 知识库已选定时跳过"理解问题"模型调用。
- 规则校验器替代模型自证。
- 有上限的数量由程序根据原文计算。

**下一步**
- 在撰写前按摘要/问题不匹配过滤掉错勾的编号。
- 空召回时利用上下位词召回（如「笔记本」↔「设备」）。
- 核对失败时只删除无依据的句子，而非整段打回。
- 可选的向量短名单以加速大标题列表，但仍然不做向量主检索。

**更长期**
- 知识世界 / LLMWiki：实体、关系、事件、状态、时间轴。
- MCP 服务器暴露 Knowledge API。
- 系列第一篇提到的领域状态 API（办件/工单/预约状态等）。

## 博客系列

本仓库代码支撑 Dev.to 系列 [RAG 的终点是知识](https://dev.to/zealot2002/series/47162)。

| # | 标题 | 内容 |
|---|------|------|
| 1 | [RAG 的终点不是检索，而是知识](https://dev.to/zealot2002/rag-de-zhong-dian-bu-shi-jian-suo-er-shi-zhi-shi-550f) | 从文本片段检索走向持久知识层 |
| 2 | [知识库既已选定，就别再让模型做意图分类](https://dev.to/zealot2002/zhi-shi-ku-ding-liao-jiu-bie-zai-rang-mo-xing-cai-ni-zai-wen-shi-yao-3bgh) | 跳过理解，整表读标题，只返回编号 |
| 3 | [三个模型只改一个变量：7B 读标题花了 27 秒](https://dev.to/zealot2002/san-ge-mo-xing-zhi-gai-ge-bian-liang-45jm) | 切换后端、读标题的代价、结果对比 |
| 4 | [答复能不能发出去，别再问模型自己对不对](https://dev.to/zealot2002/wen-da-shi-bian-ping-de-xian-fa-bu-zai-rang-mo-xing-kan-jian-2i1i) | 发布门禁、撰写约束、确定性核对 |

`docs/posts/02-04.md` 等文件是未发表的旧大纲/草稿，**不是**上面的已发表文章。

## 许可与贡献

MIT © 2026 [zealot2002](https://github.com/zealot2002)。详见 [LICENSE](LICENSE)。

欢迎 issue 和 PR。如果你按快速开始操作后，过程面板展示的内容与文档不符，请附上 `data/traces/` 下的 trace 文件路径开 issue。
