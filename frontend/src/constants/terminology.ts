/**
 * 产品文案（面向非技术用户）
 * 代码/API 仍用 document_id、mount、node_id；界面只用下列中文。
 */
export const T = {
  /** 当前正在操作的那一本手册 */
  currentHandbook: "当前手册",
  chatKbLabel: "问答知识库",
  chatKbPlaceholder: "选择已上线知识库",
  chatKbNotPublished: "尚未上线，无法问答",
  chatKbSwitched: "已切换问答知识库",
  /** 系统给每本上传手册分配的唯一编号 */
  docCode: "文档编号",
  docCodeHint: "上传后自动生成，无需填写",

  /** 章节目录（原 Wiki 目录） */
  catalog: "知识目录",
  catalogDraft: "目录草稿",
  catalogPublished: "已上线",
  catalogReview: "目录审核",

  knowledgeGraph: "结构化知识点",

  stepUpload: "上传手册",
  stepUploadDesc: "支持 .txt / .md",
  uploadFileLabel: "选择制度文本或 FAQ（.txt / .md）",
  stepParse: "自动整理目录",
  stepParseDesc: "生成目录草稿与知识点",
  stepReview: "检查与修改",
  stepReviewDesc: "可改标题与摘要",
  stepPublish: "正式发布",
  stepPublishDesc: "上线后问答才生效",
  stepQa: "智能问答",
  stepQaDesc: "仅依据已上线内容",

  colPendingSections: "待发布章节数",
  colLiveEntries: "已上线条目数",

  navLibraryMgmt: "知识库",
  navLibraryNew: "新建",
  navLibraryIngest: "整理入库",
  navLibraryEdit: "编辑目录",
  navLibraryReview: "审核",
  navChat: "问答",
  navLogs: "日志",

  btnAddLibrary: "新建知识库",
  btnEdit: "编辑",
  btnReview: "审核",
  reviewAnswerLabel: "答案",
  reviewSummaryLabel: "章说明（可选）",
  reviewChapterNoAnswer: "章节点无单独答案，请点选左侧具体问题。",
  btnContinueIngest: "整理目录",
  colLibraryName: "名称",
  colStatus: "状态",
  colActions: "操作",
  statusPendingIngest: "待整理",
  statusDraft: "待发布",
  statusLive: "已上线",
  organizePromptTitle: "豆包整理 Prompt（复制到外部大模型）",
  organizePromptCopy: "复制 Prompt",
  organizePromptCopied: "已复制到剪贴板",
  handbookOrganizeNote:
    "员工手册：请让大模型输出 .txt，章用「1. 标题」、节用「1.1 标题」+ 正文，不要用 FAQ 格式。",
  ingestHint:
    "支持直接上传 .txt / .md 问答素材。默认由大模型整理为标准 FAQ 目录草稿，可在「审核」中逐条修改后再发布。",
  docFormatHint:
    "已整理好的 FAQ 可用规范 .md（## 模块、### Qn、**答：**）跳过模型、秒级入库；杂乱纯文本请保持开启下方「大模型整理」。",
  ingestUseLlm: "用大模型整理为 FAQ（推荐）",
  ingestUseLlmHint: "关闭后仅接受已符合规范的 Markdown，纯文本会失败。",
  ingestProgressTitle: "正在整理目录",
  ingestOpenLogs: "查看运行日志（实时）",

  btnUploadSave: "仅上传",
  btnUploadAndIngest: "上传并整理目录",
  btnParse: "整理目录",
  tipNewStep1: "选好符合规范的 .md 或 .txt 后，点「上传并整理目录」即可。",
  tipNewStep2: "文件已保存。点「整理目录」按规范自动分章节。",
  btnPublish: "正式发布",
  msgUploadOk: "上传成功",
  msgDraftReady: "目录草稿已生成，请先检查再发布",
  msgPublished: "已正式发布，可以去「问答」试试",

  tipTitle: "怎么用？",
  tipBody:
    "杂乱 Word/表格请用外部大模型先整理成规范 .md 或 .txt（见项目 docs/入库格式与外部整理.md），再上传。入库不符合规范会直接失败，以保证 Wiki 质量。",
  tipEditTitle: "编辑已有知识库",
  tipEditBody:
    "此页仅修改目录中的标题与摘要，不能重新上传源文件。需要换稿请新建知识库。改完后如有未发布草稿，可点「正式发布」。",
  panelActionsCreate: "上传并入库",
  panelActionsEdit: "发布",
  editNoReingest: "已入库知识库不支持再次整理目录，以免覆盖手工修改。",

  entryCode: "条目编号",
  entryCodeHint: "系统内部编号，一般不用改；点表格某一行可编辑标题",

  chatEmpty: "请先完成上传并「正式发布」，再在这里提问",
  chatTraceTitle: "回答过程（实时）",

  libraryEmpty: "还没有知识库，点击「新增知识库」开始",
  navLibraryDetail: "知识库详情",
  btnDetail: "详情",
  btnDelete: "删除",
  btnSave: "保存",
  btnAddFaq: "新建问答",
  btnBatchImport: "批量导入",
  kbNameLabel: "知识库名称",
  kbDescLabel: "说明（可选）",
  kbCreateTitle: "新建知识库",
  kbEditTitle: "修改知识库",
  faqQuestion: "问题",
  faqAnswer: "答案",
  faqStatus: "状态",
  faqStatusDraft: "草稿",
  faqStatusLive: "已上线",
  batchImportTitle: "批量导入问答",
  batchImportHint:
    "支持：① `1. Q：题干` 下一行 `A：答案`（可多题连续）；② 规范 Markdown `### Q1.` + `**答：**`；③「问：」「答：」成对文本。导入为草稿，需点「正式发布」。",
  batchImportPlaceholder: "粘贴 .md / .txt 内容…",
  confirmDeleteLibrary: "确定删除该知识库及全部问答？不可恢复。",
  confirmDeleteFaq: "确定删除该条问答？",
  msgLibraryCreated: "知识库已创建",
  msgLibraryUpdated: "已保存",
  msgLibraryDeleted: "已删除",
  msgFaqSaved: "问答已保存",
  msgImportOk: "导入完成",
  colFaqCount: "问答条数",

  logEmpty: "暂无运行记录，操作手册或提问后会出现",
  logPageHint: "全屏日志页；任意界面也可点右下角悬浮球侧栏查看。",

  auditTitle: "如何检查、审核？",
  auditSteps: [
    "在下方列表中点击一行，会在下面出现「标题」「摘要」",
    "如有错别字或标题不合适，改完后点「保存修改」",
    "不必每一条都改；整体看过没问题即可",
    "最后点右上角「正式发布」，员工才能在问答里用到",
  ],
  auditTreeLink: "切换到树形审核页",
  catalogEmptyNeedParse: "还没有目录：请先点「整理目录」",
  catalogEmptyMismatch: "目录加载异常，请点「刷新」；仍为空请联系管理员",
} as const;

/** 步骤条内部 key 仍用 ingest_draft 等，仅映射展示文案 */
export const stepLabels: Record<string, string> = {
  upload: "待上传",
  ingest_draft: "待整理目录",
  review: "待检查",
  publish: "待发布",
  qa_ready: "可问答",
};
