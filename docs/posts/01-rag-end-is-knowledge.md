# RAG 的终点不是检索，而是知识

## ——从 Chunk、GraphRAG 到 LLMWiki，重新思考企业 AI 的知识组织方式

过去几年，RAG 几乎已经成为企业 AI 应用的标准答案。

企业有大量内部文档，不知道如何让 LLM 使用？

答案是 RAG。

企业想做智能客服、知识问答、内部搜索？

还是 RAG。

它的基本思路非常简单：

```text
Document
   ↓
Chunk
   ↓
Embedding
   ↓
Vector Search
   ↓
Rerank
   ↓
LLM
   ↓
Answer
```

这套方法确实有效，也解决了第一代企业知识问答的大量问题。

但 RAG 发展到今天，一个越来越值得追问的问题出现了：

> **我们究竟是在解决“知识检索”问题，还是只是在解决“文本检索”问题？**

如果答案是后者，那么 RAG 的很多问题，其实并不来自 Embedding、Vector DB 或 LLM，而来自一个更底层的设计：

> **我们把 Chunk 当成了知识的基本单位。**

而现实世界显然不是由 Chunk 构成的。

人类认识世界的基本单位，是对象、概念、属性、关系、事件、状态和时间。

这可能意味着：

> **RAG 真正的演化方向，并不是不断把文本检索做得更复杂，而是逐渐改变“知识”的表示方式。**

---

# 一、传统 RAG 面临的第一个问题：Chunk 根本不是知识单位

假设企业文档中有这样一段：

> ABC Pro 于 2025 年 3 月上市，售价 5999 元，支持 100W 快充。2025 年 8 月通过固件升级增加 RAW 视频功能。

传统 RAG 首先做的是：

```text
文本
 ↓
Chunk
 ↓
Embedding
 ↓
Vector Index
```

但从知识角度看，这段文字表达的其实是：

```text
ABC Pro
 ├── 上市时间 → 2025-03
 ├── 售价 → 5999
 ├── 快充能力 → 100W
 ├── 固件升级 → 2025-08
 └── 新增能力 → RAW 视频
```

文本的物理结构，与知识的逻辑结构，并不是一回事。

这就是固定长度 Chunk 的第一个根本问题。

于是行业很快开始寻找第一个解决方案。

---

# 二、第一次演化：从固定 Chunk 到 Semantic Chunking

既然固定长度不合理，那么就按照语义切。

于是出现了：

- Semantic Chunking
- Structure-aware Chunking
- Parent-child Chunking
- Contextual Chunking

系统开始理解：

```text
标题
章节
段落
表格
代码
语义边界
```

这比简单地每 500 tokens 切一次显然更合理。

但问题并没有真正解决。

因为：

> **语义边界本身就是模糊的。**

例如：

> “乔布斯于 1976 年创立 Apple，1985 年离开公司，并于 1997 年重新回归。”

这在文本上是一个段落。

但在知识上却至少包含：

```text
Steve Jobs
    │
    ├── founded → Apple
    │      └── 1976
    │
    ├── left → Apple
    │      └── 1985
    │
    └── returned → Apple
           └── 1997
```

所以 Semantic Chunking 本质上仍然是在做一件事情：

> **从文本结构猜测知识结构。**

这已经比固定切片前进了一步，但它仍然没有真正解决“知识是什么”的问题。

---

# 三、第二个问题：一个 Chunk 很难回答复杂问题

简单问题通常没有问题：

> ABC Pro 支持多少瓦快充？

找到一个相关 Chunk 即可。

但企业真实问题经常是：

> 为什么我的 ABC Pro 不能升级？

这个问题可能同时涉及：

```text
产品型号
+
当前固件版本
+
购买地区
+
客户类型
+
升级政策
+
政策版本
```

单个 Chunk 很难回答。

于是 RAG 开始第二次演化：

```text
Query
 ↓
Hybrid Search
 ↓
召回更多候选
 ↓
Rerank
 ↓
Top-N
```

BM25 负责精确词匹配。

Embedding 负责语义匹配。

Reranker 再判断：

> 哪些文本真正与问题相关？

这使 RAG 的召回能力大幅提高。

但它也暴露了一个事实：

> **如果一个问题需要不断扩大搜索范围，再通过 reranker 筛选，我们是不是从一开始就选错了检索对象？**

---

# 四、第三次演化：从“一次检索”到 Query Decomposition

复杂问题继续逼迫 RAG 演化。

例如：

> “我去年购买的 ABC Pro，在台湾使用，现在出现故障，还能免费维修吗？”

系统很难直接通过一次搜索找到答案。

于是出现：

- Query Rewrite
- Query Expansion
- Multi-query
- Query Decomposition
- Agentic Retrieval

一个问题被拆成：

```text
Q1：ABC Pro 的保修政策是什么？
Q2：台湾地区适用什么政策？
Q3：去年购买适用哪个政策版本？
Q4：这个故障是否属于免费维修范围？
```

然后分别检索。

这一步非常重要，因为 RAG 开始承认：

> **问题背后不是一个文本片段，而是一组相互关联的知识。**

系统正在从：

> “找一段相关文字”

慢慢走向：

> “寻找回答问题所需要的知识结构”。



如果一个问题需要多个知识，那么自然会产生下一个问题：

> 能不能让 LLM 自己决定需要什么知识？

于是出现了 Query Decomposition、Multi-step Retrieval，以及更进一步的 Agentic RAG。

传统 RAG：

```text
Question
   ↓
Retrieve Top-K
   ↓
LLM
   ↓
Answer
```

Agentic RAG：

```text
Question
   ↓
Understand
   ↓
Plan
   ↓
Retrieve
   ↓
Evaluate
   ↓
Need More Knowledge?
   ├── Yes → Retrieve Again
   │          ↓
   │       Evaluate
   │          ↓
   │          ...
   │
   └── No
       ↓
     Answer
```

这时，RAG 已经发生了一个非常重要的变化：

> **Retrieval 不再是一个固定动作，而成为 Agent 推理过程中的一个循环。**

---


# 五、智能客服其实是一个非常典型的例子

例如用户问：

> 我上个月买的 iPhone 15 Pro 为什么还不能退？如果现在换成 iPhone 16 Pro，需要补多少钱？

这个问题显然不能只搜索一次。

Agent 可能需要：

```text
1. 找到用户
2. 找到订单
3. 查询购买日期
4. 查询商品
5. 查询退货政策
6. 判断是否符合退货条件
7. 查询 iPhone 16 Pro 当前价格
8. 计算差价
9. 综合生成答案
```

于是整个过程变成：

```text
                 User Question
                       │
                       ▼
                  Understand
                       │
                       ▼
                     Plan
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       Order        Policy        Product
          │            │            │
          └────────────┼────────────┘
                       ▼
                    Evaluate
                       │
                Missing Knowledge?
                  ┌────┴────┐
                 Yes         No
                  │           │
                  ▼           ▼
              Retrieve      Reason
                  │           │
                  └───────────┘
                              │
                              ▼
                           Verify
                              │
                              ▼
                            Answer
```

这就是一个真正意义上的 **Knowledge Loop**。

这里有一个值得注意的变化：

> Agent 不应该只是不断地“搜索更多关键词”。

真正应该循环的是：

> **我为了回答这个问题，还缺什么知识？**

这两个问题完全不同。

---

# 六、Plan 的对象，不应该是 Search Query，而应该是 Knowledge Requirement

例如：

> 为什么我的订单不能退款？

一个传统 RAG Agent 可能产生：

```text
Search:
"退款政策"
"订单退款"
"30天退款"
"商品退款条件"
```

但更好的 Agent 应该产生：

```text
Required Knowledge:

Order.purchase_date
Order.status
Order.product
Product.return_policy
Policy.effective_date
Policy.special_conditions
```

然后再决定这些知识应该通过什么方式获得：

```text
Knowledge Requirement
       │
       ├── Wiki
       ├── Knowledge Graph
       ├── Database
       ├── API
       └── RAG Evidence
```

这其实是一个非常重要的架构变化：

> **Agent 不再围绕“搜索”进行规划，而是围绕“知识缺口”进行规划。**

---

# 七、第四次演化：既然知识有层级，那就建立层级

另一个非常有代表性的方向是 RAPTOR。

传统 RAG 往往只检索底层 Chunk。

RAPTOR 则对文本进行聚类和递归摘要，建立多层级结构：

```text
              Document
             /        \
        Summary       Summary
        /   \          /   \
     Chunk Chunk     Chunk Chunk
```

这样既可以从底层细节回答问题，也可以从更高层级理解整个文档。

这实际上已经开始接近人类知识组织方式：

> 人类不会把一本书理解成几百个互不相关的段落，而会先理解章节、主题、概念，再深入细节。

RAPTOR 的重要意义在于：

> **RAG 开始从“平面文本检索”向“层级知识检索”演化。**

但它仍然主要是在构造更好的文本结构。

真正的下一步，是关系。

---

# 八、第五次演化：GraphRAG——从文本走向实体和关系

如果知识之间存在关系，那么为什么不直接建立 Graph？

这就是 GraphRAG 的核心思想。

文本：

```text
Steve Jobs founded Apple.
```

不再只是一个 Chunk，而可以变成：

```text
Steve Jobs
      │
   founded
      │
      ▼
    Apple
```

进一步：

```text
Apple
 ├── founded_by → Steve Jobs
 ├── products → iPhone
 ├── competitor → Microsoft
 └── CEO → Tim Cook
```

微软 GraphRAG 进一步引入 Entity、Relationship、Claim、Community 等结构，并通过 Local Search、Global Search、DRIFT 等方式利用这些结构进行检索。

这一步是 RAG 演化史上的一个重要转折点：

> **检索对象开始从“文本块”变成“知识节点和关系”。**

---

# 九、但 Graph 仍然不是终点

现实世界不仅存在：

```text
Entity
Relation
```

还存在：

```text
Attribute
Event
State
Time
Evidence
```

例如：

> Apple CEO 是谁？

一个简单 Graph 可以表示：

```text
Apple
 ↓ CEO
Tim Cook
```

但如果问题是：

> 2010 年 Apple 的 CEO 是谁？

就必须理解时间。

真正合理的表示应该是：

```text
Apple
  │
  └── CEO
       ├── Steve Jobs
       │     └── valid_until: 2011
       │
       └── Tim Cook
             └── valid_from: 2011
```

再比如：

> ABC Pro 什么时候增加 RAW 视频？

它不是一个普通 Attribute，而是一个 Event：

```text
ABC Pro
   │
   └── Firmware Upgrade
          │
          ├── time → 2025-08
          └── added → RAW Video
```

因此，真正完整的知识对象开始变成：

```text
Object
 ├── Attributes
 ├── Relations
 ├── Events
 ├── States
 ├── Timeline
 └── Evidence
```

这已经开始超越传统 Knowledge Graph。

---

# 十、这时候，一个更根本的问题出现了：为什么一定要在 Query 时理解知识？

到这里，我们可以看到 RAG 一直在做一件事情：

> 用户提问以后，再想办法从原始文本中恢复知识。

于是整个检索链越来越复杂：

```text
Query
 ↓
Rewrite
 ↓
Embedding
 ↓
Hybrid Search
 ↓
Rerank
 ↓
Query Decomposition
 ↓
Graph Traversal
 ↓
Context
 ↓
LLM
```

那么有没有可能反过来？

不是：

> **用户提问时才理解知识。**

而是：

> **知识进入系统的时候，就把它理解、组织和关联好。**

这正是 LLMWiki 这类系统值得关注的地方。

---

# 十一、LLMWiki：从“检索文本”走向“维护知识”

[Microsoft LLM Wiki](https://github.com/microsoft/llmwiki) 的核心价值，并不只是“把 RAG 做得更好”。

它更像是在尝试建立一种：

> **Persistent Knowledge Layer**

传统 RAG：

```text
Document
 ↓
Chunk
 ↓
Index

用户提问
 ↓
Search
 ↓
找到相关 Chunk
```

LLMWiki 所代表的方向更接近：

```text
Document
 ↓
AI Understanding
 ↓
Entity / Concept
 ↓
Knowledge Page
 ↓
Cross-link
 ↓
Enrichment
 ↓
Persistent Knowledge
```

也就是说：

> **传统 RAG 把理解知识的成本推迟到了 Query Time；Wiki 把一部分理解和组织工作提前到了 Knowledge Build Time。**

这其实是非常大的架构变化。

---

# 十二、为什么 Wiki 可能是非常自然的知识形态？

因为人类本身就是这样组织知识的。

我们不会把 Apple 的知识理解成：

```text
Chunk 1827
Chunk 3942
Chunk 8173
```

而会形成：

```text
Apple
 ├── History
 ├── Products
 ├── Leadership
 ├── Technology
 ├── Competitors
 └── Related Concepts
```

点击 Steve Jobs，又可以进入：

```text
Steve Jobs
 ├── Apple
 ├── Pixar
 ├── NeXT
 └── Timeline
```

所以 Wiki 本质上同时具有：

```text
Tree
+
Graph
+
Human-readable Knowledge
+
Evidence
```

LLMWiki 的重要启发是：

> **企业知识可以成为一种持续积累的资产，而不是每次查询时从文档中临时恢复出来的东西。**

---

# 十三、这时出现了另一个非常有意思的问题：为什么不直接训练一个“企业小模型”？

如果 GPT 为什么能够回答大量普适性问题？

一个重要原因是：

> **这些知识已经通过训练进入了模型参数。**

模型不是每次被问“什么是 TCP”时，都去搜索 TCP 文档。

它已经在训练过程中形成了对：

```text
TCP
HTTP
Linux
Python
历史
科学
数学
```

等概念的内部表示。

于是一个自然的问题出现了：

> **如果我们把企业知识也按照训练大模型的方式训练进去，是不是就可以得到一个企业知识小模型？**

答案是：

> **可以，而且这条路确实有价值。**

例如：

```text
Enterprise Documents
       ↓
Cleaning
       ↓
Knowledge Dataset
       ↓
Fine-tuning / Continued Pretraining
       ↓
Enterprise Small Model
```

这样得到的模型可能天然掌握：

- 企业术语
- 产品概念
- 企业流程
- 客服表达方式
- 领域推理模式
- 常见问题
- 稳定知识

于是很多问题可以直接：

```text
User
 ↓
Enterprise Model
 ↓
Answer
```

甚至不需要每次 RAG。

---

# 十四、但“企业小模型”不能成为企业事实数据库

问题也恰恰在这里。

企业知识不是静态的。

例如：

```text
2025 Warranty Policy
→ 12 months

2026 Warranty Policy
→ 24 months
```

如果这个知识进入模型参数：

```text
Enterprise Model v1
```

政策变化之后怎么办？

重新训练：

```text
Enterprise Model v2
```

如果企业每天都在改变：

- 产品价格
- 库存
- 政策
- 客户等级
- 订单
- 产品能力
- 法规

那么把这些信息全部写入参数显然不是一个高效方案。

因此，一个非常重要的分层出现了：

```text
Stable Knowledge
        ↓
Model Parameters

Structured Knowledge
        ↓
Wiki / Knowledge Graph

Dynamic State
        ↓
Database / API

Evidence
        ↓
Documents / RAG
```

这比简单讨论：

> RAG 还是 Fine-tuning？

更加准确。

---

# 十五、换句话说：模型应该学习“企业”，而不是记住“企业数据库”

这是企业小模型真正适合的位置。

例如它可以学习：

> 什么是公司的产品？

> 产品之间通常有什么关系？

> 客服应该如何处理售后问题？

> 企业内部术语是什么意思？

> 某类问题应该调用哪些知识？

这些是：

> **稳定的能力和知识模式。**

但：

> “ABC Pro 今天多少钱？”

> “这个客户当前有没有保修？”

> “2026 年 3 月最新政策是什么？”

应该去问：

```text
Wiki
Database
API
```

而不是相信模型参数。

因此可以把企业 AI 很简单地分成：

> **Model = 能力**

> **Wiki = 知识**

> **Database/API = 状态**

> **RAG = 证据**

这四者各司其职。

---

# 十六、于是我们开始看到一种比传统 RAG 更合理的架构

假设企业生产环境中维护一个 Wiki。

但这个 Wiki 不是简单的 Markdown 文档，而是结构化知识：

```text
Entity
Concept
Attribute
Relation
Event
State
Policy
Procedure
Evidence
```

企业员工负责：

```text
Schema
Policy
Review
Approval
```

AI 负责：

```text
Document Understanding
Entity Extraction
Knowledge Extraction
Cross-link
Conflict Detection
Change Proposal
```

形成：

```text
Raw Source
    ↓
AI Understanding
    ↓
Knowledge Proposal
    ↓
Validation
    ↓
Human Approval
    ↓
Canonical Wiki
```

这就形成了：

> **Human-governed, AI-assisted Knowledge System**

这比要求员工手工维护数万个 Wiki 页面现实得多。

---

# 十七、而 LLM 与 Wiki 之间，不应该只是“搜索”

这是整个架构最值得进一步思考的地方。

传统 RAG 给 LLM 的工具可能是：

```text
search("ABC Pro warranty")
```

然后返回：

```text
Chunk 1
Chunk 2
Chunk 3
...
```

未来的 Knowledge API 可以直接暴露：

```text
get_entity("ABC Pro")

get_attribute(
    entity="ABC Pro",
    attribute="warranty"
)

get_related_entities(
    entity="ABC Pro",
    relation="compatible_with"
)

get_events(
    entity="ABC Pro"
)

get_state(
    entity="ABC Pro",
    time="2025-06"
)

get_evidence(
    claim="ABC Pro warranty = 24 months"
)
```

这时候 LLM 不再是在：

> **搜索文本。**

而是在：

> **查询知识世界。**

这里又回到了前面的智能客服。

如果企业只有 RAG：

```text
Agent
  ↓
Search("退款政策")
  ↓
Search("订单退款")
  ↓
Search("商品退货")
```

如果企业已经拥有 Knowledge World：

```text
Agent
   ↓
Understand Question
   ↓
Plan
   ↓
Get Order
   ↓
Get Product
   ↓
Get Return Policy
   ↓
Get Current Order State
   ↓
Get Evidence
   ↓
Reason
   ↓
Verify
   ↓
Answer
```

这时候 Agent 调用的已经不是简单的 `search()`，而是本节列出的 Knowledge API；LLM 面对的也不再是「一个搜索引擎」，而是**一个可以被查询和操作的企业知识世界**。

MCP 这类机制尤其适合承担这个角色：让模型通过统一的工具协议访问企业知识，而不是把所有知识都塞进 Context。

LLMWiki 当前已经提供 MCP server，并支持外部 Agent 对 Wiki 进行读取和写入；它的 Smart Ingest 也在尝试让 AI 自动从新资料中生成实体、概念、交叉链接并更新已有知识。

---

# 十八、这可能比传统 RAG 更高性价比

比较两个客服请求。

传统 RAG：

```text
用户
 ↓
Query Rewrite
 ↓
Embedding
 ↓
Vector Search
 ↓
BM25
 ↓
Fusion
 ↓
Rerank
 ↓
Context
 ↓
LLM
```

Knowledge Wiki：

```text
用户
 ↓
LLM 理解问题
 ↓
get_entity("ABC Pro")
 ↓
get_policy("warranty")
 ↓
get_state(...)
 ↓
LLM Reasoning
```

如果 Wiki 已经把知识组织好，第二种方案会有一个非常明显的优势：

> **搜索空间大幅缩小。**

这和数据库为什么比全文搜索可靠是类似的。

数据库不会问：

> “哪一段文本看起来最像这个 SQL？”

它直接定位：

```sql
WHERE product_id = 'ABC-Pro'
```

结构化知识的价值并不只是“更聪明”。

它首先意味着：

> **更少的搜索空间，更少的歧义，更少的猜测。**


但这还不是全部区别。传统 Agentic RAG 与 **Knowledge Agent** 的差异，往往不在于「有没有 Agent」，而在于 Agent 是在搜索文本，还是在操作知识：

传统 Agentic RAG：

```text
Question
   ↓
Plan
   ↓
Search
   ↓
Search
   ↓
Search
   ↓
Summarize
```

Knowledge Agent：

```text
Question
   ↓
Understand
   ↓
Plan Knowledge Requirements
   ↓
Traverse Knowledge World
   ↓
Retrieve State
   ↓
Retrieve Evidence
   ↓
Reason
   ↓
Verify
   ↓
Answer
```

> **Agent 到底是在「搜索文本」，还是在「操作知识」？** 这可能是下一阶段企业 Agent 架构非常重要的分界线。

---

# 十九、那么 RAG 会消失吗？

不会。

它的位置会变化。

未来可能是：

```text
                    Enterprise AI
                          │
                         LLM
                          │
                    MCP / Tools
                          │
              Enterprise Knowledge
                          │
          ┌───────────────┼───────────────┐
          │               │               │
         Wiki            Graph         Live Data
          │               │               │
          └───────────────┼───────────────┘
                          │
                       Evidence
                          │
                         RAG
                          │
                     Raw Sources
```

RAG 不再是整个系统。

它变成：

> **Evidence Retrieval Layer**


其中各层可以这样理解：

```text
Wiki / Graph → What we know
Database / API → What is happening now
RAG → Why we believe it
Model → How we reason
Agent → What we should do
```

当 Wiki 中有一个事实：

```text
ABC Pro warranty = 24 months
```

系统仍然需要知道：

> 这个事实来自哪份政策？

于是 RAG 仍然负责从原始资料中找证据。

所以未来不是：

> RAG vs Wiki

而更可能是：

> **Wiki 负责知识，RAG 负责证据。**

---

# 二十、这也解释了为什么“人类知识组织方式”如此重要

回头看整个 RAG 的演化：

```text
Fixed Chunk
    ↓
Semantic Chunk
    ↓
Hybrid Retrieval
    ↓
Reranking
    ↓
Query Decomposition
    ↓
Agentic RAG
    ↓
Hierarchical Retrieval
    ↓
GraphRAG
    ↓
Wiki / Persistent Knowledge
    ↓
Object-centric Knowledge
    ↓
Knowledge Agent
    ↓
Enterprise Knowledge OS
```

表面上，这是 Retrieval 技术不断升级。

但从更底层看，它其实一直在解决同一个问题：

> **机器应该如何表示知识？**

Chunk 不够，于是优化 Chunk。

Chunk 仍然不够，于是做多路检索。

多路检索仍然不够，于是建立层级。

层级仍然不够，于是建立 Graph。

Graph 仍然不够，于是加入 Event、State、Time、Evidence。

最终，我们发现：

> **真正需要的不是一个更好的搜索引擎，而是一套更接近人类知识组织方式的知识系统。**

---

# 二十一、未来可能不是“企业 RAG”，而是“企业知识操作系统”

如果继续把这个方向推到底，最终架构可能变成：

```text
                     Enterprise AI

                          LLM
                           │
                     Reasoning Engine
                           │
                     MCP / Knowledge API
                           │
                ┌──────────┴──────────┐
                │ Enterprise World   │
                │      Model         │
                └──────────┬─────────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
    Objects              Events             Concepts
       │                   │                   │
    Relations            States             Timeline
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                        Evidence
                           │
                    Raw Enterprise Data
```

在这个系统里：

**模型参数**

负责稳定的能力、领域知识和推理模式。

**Wiki / Knowledge Graph**

负责结构化、可审核、可更新的企业知识。

**数据库 / API**

负责动态事实和实时状态。

**RAG**

负责原始证据检索。

**MCP / Tool**

负责让 LLM 访问这个世界。

最终：

> **LLM 不再是一个“读文档然后回答问题”的模型，而是一个能够访问企业知识世界并在其中进行推理的智能接口。**

---

# 二十二、最后结论：RAG 的终点，可能是“知识”，而不是“检索”

现在回头看最初的问题：

> RAG 为什么越来越复杂？

因为我们一直在用 Retrieval 技术弥补 Representation 的不足。

我们希望：

```text
Chunk
```

代表知识。

但 Chunk 并不是知识。

于是：

```text
Semantic Chunk
```

出现了。

还是不够。

于是：

```text
Hybrid Search
Rerank
Query Decomposition
Hierarchical Retrieval
GraphRAG
```

不断出现。

它们都在一点一点地逼近真正的知识结构。

而 LLMWiki 提供了另一个重要启发：

> **为什么不在知识进入系统的时候，就把它组织起来？**

进一步，我们又得到两个新的结论。

第一：

> **企业知识中稳定、抽象、可泛化的部分，可以进入企业小模型，让模型真正“懂企业”。**

第二：

> **动态、精确、需要审计的知识，不应该被锁死在模型参数里，而应该存在于一个由 Human + AI 共同维护的企业知识层中。**

因此未来最合理的企业 AI 架构，也许不是：

```text
LLM + RAG
```

而是：

```text
                    Enterprise AI

        ┌─────────────────────────────────┐
        │              LLM                │
        │        Capability & Reasoning   │
        └────────────────┬────────────────┘
                         │
                    MCP / Tools
                         │
        ┌────────────────┴────────────────┐
        │      Enterprise Knowledge       │
        │                                 │
        │   Wiki + Graph + Timeline       │
        │   Objects + Relations + Events  │
        └────────────────┬────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
          Live Data              Evidence
              │                     │
          DB / API                  RAG
```

这时候，RAG 依然存在，但它已经不再是主角。

**主角变成了知识。**

而知识的最终形态，也许不是文档、Chunk、Embedding，甚至不只是 Graph。

它应该是：

> **一个可理解、可导航、可验证、可更新、可追溯的企业知识世界。**

从这个角度看，RAG 的真正终点可能不是：

> **更好的 Retrieval。**

而是：

> **更好的 Representation。**

而企业 AI 的真正目标，也许不是训练一个“知道所有企业知识”的模型。

而是：

> **建立一个模型能够可靠访问、理解和推理的企业知识世界。**

而当这些知识被持久化之后，Agent 就不再需要每次从海量文档中重新「猜测」企业知识，而可以直接在这个知识世界中进行：

```text
Understand
   ↓
Plan
   ↓
Traverse
   ↓
Retrieve
   ↓
Reason
   ↓
Verify
   ↓
Act
```

---

## 系列说明

本仓库 **mycs** 将按上述架构，同步实现一套**泛化智能客服**系统（政府 / 企业 / 学校等）：以 Knowledge Requirement 驱动的 Agent、结构化知识层与**可选的领域状态 API** 分工协作；**不绑定订单或电商**。博文与代码一一对应。里程碑与博文索引见 [docs/PLAN.md](../PLAN.md)、[docs/SERIES.md](../SERIES.md)。

### 本仓库实现约定（与正文「Wiki / DB / Agent」对齐）

正文里 **RAG → 证据（Why we believe it）** 是行业演进中的常见分工。本系列在工程上采用 **无向量 chunk** 方案，避免把「文本片段检索」重新拉回客服主路径。正文中的 iPhone / 订单 / 退换货示例用于说明 Knowledge Loop，**不是**本仓库的固定业务域。

| 正文概念 | mycs 实现 |
|----------|-----------|
| 结构化知识（Wiki / Graph） | SQLite + Knowledge API（政策、办事指南、FAQ、实体与属性） |
| 动态状态（DB / API） | **可选**：办件 / 工单 / 申请等 **Case 状态 API**（`case_id`）；纯政策咨询可不走该层 |
| 证据（RAG 层） | **Wiki 内嵌 `evidence`**：`quote`、`source_uri`、`effective_from` 等；Verify 对证据做确定性比对 |
| Agent | Plan **Knowledge Requirement** → 调 Wiki /（按需）领域 API → Verify → Answer |
| 编排 | **M1–M4 自研 Agent loop**（非 LangGraph/LangChain）；见 [PLAN.md](../PLAN.md#agent-编排与框架选型) |

**不做：** 独立里程碑上的 simple chunk、向量库与「先搜 chunk 再回答」的客服主链路；**M1–M4 不以 LangGraph/LangChain 为编排核心**（M6 可选评估 LangGraph 用于 HITL 等）。若原文尚未结构化，通过 ingest 写入 Wiki 并附带证据引用，而不是单独建 RAG 索引。

**下一篇（02）** 从一条 **办事/政策咨询** 参考链路（可选带 `case_id`）出发，在代码里落地 `Understand → Plan（知识缺口）→ Tools → Verify → Answer` 的最小闭环（M0–M1，可先 Mock LLM）。

