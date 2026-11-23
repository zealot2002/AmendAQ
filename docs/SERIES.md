# 系列博文 — AmendAQ, a better RAG?

代码与文章同仓。三篇结构：**RAG 发展与问题 → AmendAQ 介绍 → 对照评测（含详表）**。

| # | 文章 | 内容 |
|---|------|------|
| 1 | [RAG 这六年怎么走过来的、2026 年前沿在做什么、以及它还剩哪些没解决的问题](./posts/01-why-amendaq.md) | 六年四代主线；向量有损；2026 前沿四件事；制度场景五件事 → AmendAQ |
| 2 | [我们做了 AmendAQ：可改的问答，发布就是索引](./posts/02-what-amendaq-is.md) | 为何做、mycs 主路径、发布/勾选/核对、试过又拿掉的路 |
| 3 | [澄海手册对照：AmendAQ、传统 RAG 与 LightRAG](./posts/03-when-to-choose-amendaq.md) | 评测设定；103×48 与 211×60 汇总表、逐题表、结论 |

## 名词

| 词 | 含义 |
|----|------|
| AQ | 一条可修订、可发布、可撤回的问答 |
| AmendAQ | 在已发布 AQ 上按编号作答；提问不做向量主检索 |
| mycs | AmendAQ 的实现仓库 |

评测复现：`scripts/run_compare.py`。完整表同步在 `docs/对比测试_澄海手册*.md`。