/**
 * 产品文案（面向非技术用户）
 * 代码/API 仍用 document_id、mount、node_id；界面只用下列中文。
 */
export const T = {
  /** 当前正在操作的那一本手册 */
  currentHandbook: "当前手册",
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
  stepUploadDesc: "支持 .txt 文本",
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

  navWorkflow: "搭建知识库",
  navReview: "审核目录",
  navChat: "智能问答",
  navLibrary: "已入库手册",

  btnUploadSave: "保存上传",
  btnParse: "整理目录",
  btnPublish: "正式发布",
  msgUploadOk: "上传成功",
  msgDraftReady: "目录草稿已生成，请先检查再发布",
  msgPublished: "已正式发布，可以去「智能问答」试试",

  tipTitle: "怎么用？",
  tipBody:
    "1. 上传一本手册（txt）→ 2. 点「整理目录」自动分章节 → 3. 检查标题有无问题 → 4. 点「正式发布」。只有发布后，问答才会用到这份内容。",

  entryCode: "条目编号",
  entryCodeHint: "系统内部编号，一般不用改；点表格某一行可编辑标题",

  chatEmpty: "请先完成上传并「正式发布」，再在这里提问",
  chatTraceTitle: "回答过程（实时）",

  libraryEmpty: "还没有入库的手册，请先在「搭建知识库」上传",

  logEmpty: "暂无运行记录，操作手册或提问后会出现",

  auditTitle: "如何检查、审核？",
  auditSteps: [
    "在下方列表中点击一行，会在下面出现「标题」「摘要」",
    "如有错别字或标题不合适，改完后点「保存修改」",
    "不必每一条都改；整体看过没问题即可",
    "最后点右上角「正式发布」，员工才能在问答里用到",
  ],
  auditTreeLink: "用树形目录审核（更适合章节多的手册）",
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
