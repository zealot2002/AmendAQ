<template>
  <div class="page">
    <el-row :gutter="16">
      <el-col :span="14" class="col-chat">
        <el-card shadow="never" class="chat-card">
          <template #header>向知识库提问</template>
          <div ref="scrollRef" class="messages">
            <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
              <div class="bubble">
                <div class="role">{{ m.role === "user" ? "您" : "助手" }}</div>
                <div v-if="m.pending" class="text pending">
                  <el-icon class="is-loading"><Loading /></el-icon>
                  {{ m.content || "正在思考…" }}
                </div>
                <div v-else class="text">{{ m.content }}</div>
                <div
                  v-if="m.role === 'assistant' && !m.pending && m.elapsedSeconds != null"
                  class="msg-meta"
                >
                  耗时 {{ formatElapsed(m.elapsedSeconds) }} s
                </div>
              </div>
            </div>
            <el-empty v-if="showSetupEmpty" :description="T.chatEmpty">
              <el-button type="primary" @click="goLibrary">{{ T.chatGoLibrary }}</el-button>
            </el-empty>
          </div>
          <div class="composer">
            <el-input
              v-model="question"
              type="textarea"
              :rows="3"
              placeholder="例如：年假可以结转吗？最多几天？"
              :disabled="loading"
              @keydown="onComposerKeydown"
            />
            <div class="composer-actions">
              <span class="hint">
                连续按两次回车发送。依据顶栏所选「问答知识库」中<strong>已上线</strong>的条目回答
                <template v-if="documentId">（{{ documentTitle || documentId }}）</template>
              </span>
              <el-button type="primary" :loading="loading" @click="send">发送</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="10" class="col-trace">
        <el-card shadow="never" class="trace-card">
          <template #header>
            {{ T.chatTraceTitle }}
            <el-tag v-if="verifyOk !== null" :type="verifyOk ? 'success' : 'warning'" size="small">
              {{ verifyOk ? "回答有据" : "建议人工核对" }}
            </el-tag>
          </template>
          <div ref="traceRef" class="trace-timeline">
            <div
              v-for="(ev, idx) in trace"
              :key="idx"
              class="trace-step done trace-step-clickable"
              :class="[
                'kind-' + stepKind(ev).kind,
                { highlight: idx === trace.length - 1 && loading, expanded: isStepExpanded(idx) },
              ]"
              @click="toggleStepExpand(idx)"
            >
              <div class="step-head">
                <el-icon color="#67c23a"><CircleCheck /></el-icon>
                <el-tag
                  v-if="stepKind(ev).label"
                  size="small"
                  :type="stepKind(ev).tagType"
                  effect="plain"
                  class="step-kind-tag"
                >
                  {{ stepKind(ev).label }}
                </el-tag>
                <span class="step-title">{{ stepTitle(ev, idx) }}</span>
                <span class="expand-hint">{{ isStepExpanded(idx) ? "收起" : "展开详情" }}</span>
                <span v-if="ev.at" class="step-time">{{ formatTime(ev.at) }}</span>
              </div>
              <div v-if="!isStepExpanded(idx)" class="trace-detail trace-detail-collapsed">
                <p v-if="stepDisplay(ev)?.summary" class="line-summary">{{ stepDisplay(ev)!.summary }}</p>
                <p v-else class="line-summary muted">（无摘要）</p>
              </div>
              <div v-else class="trace-detail trace-detail-expanded" @click.stop>
                <template v-if="stepDisplay(ev)">
                  <p class="section-label">小白摘要</p>
                  <p v-if="stepDisplay(ev)!.summary" class="line-summary">{{ stepDisplay(ev)!.summary }}</p>
                  <p v-if="stepDisplay(ev)!.input" class="line-io">
                    <span class="label">输入</span>{{ stepDisplay(ev)!.input }}
                  </p>
                  <p v-if="stepDisplay(ev)!.output" class="line-io">
                    <span class="label">输出</span>{{ stepDisplay(ev)!.output }}
                  </p>
                </template>
                <p
                  v-if="llmCaptureMissing(ev)"
                  class="llm-missing-hint"
                >
                  本步应有大模型调用，但未写入 llm_calls（多半是 API 进程过旧或捕获未初始化）。请重启 API
                  后重问；若 Payload 里已有 llm_calls，可忽略此提示。
                </p>
                <template v-if="llmCalls(ev).length">
                  <p class="section-label">大模型 Prompt / 返回（{{ llmCalls(ev).length }} 次）</p>
                  <div v-for="(call, ci) in llmCalls(ev)" :key="ci" class="llm-block">
                    <p class="llm-block-title">调用 {{ ci + 1 }} · {{ call.model || "model" }}</p>
                    <p class="mini-label">System Prompt</p>
                    <pre class="raw-json">{{ call.request?.system || "—" }}</pre>
                    <p class="mini-label">User / 上下文 JSON</p>
                    <pre class="raw-json">{{ call.request?.user || "—" }}</pre>
                    <p class="mini-label">模型返回（原文）</p>
                    <pre class="raw-json">{{ call.response_text || "—" }}</pre>
                    <p v-if="call.usage" class="mini-label">Token usage</p>
                    <pre v-if="call.usage" class="raw-json">{{ formatJson(call.usage) }}</pre>
                    <template v-if="call.response_api">
                      <p class="mini-label">完整 API 响应 JSON</p>
                      <pre class="raw-json">{{ formatJson(call.response_api) }}</pre>
                    </template>
                  </div>
                </template>
                <p class="section-label">完整步骤数据（Payload）</p>
                <pre class="raw-json">{{ formatJson(rawPayload(ev)) }}</pre>
              </div>
            </div>
            <div v-if="loading" class="trace-step active">
              <el-icon class="is-loading"><Loading /></el-icon>
              <el-tag size="small" type="success" effect="plain" class="step-kind-tag">编排</el-tag>
              <span>{{ runningLabel || "处理中…" }}</span>
            </div>
            <el-empty v-if="!trace.length && !loading" description="提问后这里会逐步显示每一步" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { CircleCheck, Loading } from "@element-plus/icons-vue";
import { T } from "@/constants/terminology";
import { chatStream, fetchLibraries, type ChatTraceEvent } from "@/api/client";
import { useDocumentId } from "@/composables/useDocumentId";

const router = useRouter();

function goLibrary() {
  router.push({ name: "library" });
}

const { documentId, documentTitle } = useDocumentId();
const question = ref("");
const lastEnterAt = ref(0);
const loading = ref(false);
const messages = ref<
  { role: "user" | "assistant"; content: string; pending?: boolean; elapsedSeconds?: number }[]
>([]);
const hasLibrary = ref(Boolean(documentId.value.trim()));
const libraryChecked = ref(hasLibrary.value);
const showSetupEmpty = computed(
  () => !messages.value.length && libraryChecked.value && !hasLibrary.value,
);

onMounted(async () => {
  try {
    const data = await fetchLibraries();
    const count = data.count ?? data.libraries?.length ?? 0;
    hasLibrary.value = count > 0 || Boolean(documentId.value.trim());
  } catch {
    hasLibrary.value = Boolean(documentId.value.trim());
  } finally {
    libraryChecked.value = true;
  }
});

function formatElapsed(v: number) {
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}
const trace = ref<ChatTraceEvent[]>([]);
const verifyOk = ref<boolean | null>(null);
const runningLabel = ref("");
const scrollRef = ref<HTMLElement | null>(null);
const traceRef = ref<HTMLElement | null>(null);
const expandedSteps = ref<Set<number>>(new Set());

type DisplayBlock = {
  summary?: string;
  input?: string;
  output?: string;
  step_kind?: string;
  step_kind_label?: string;
};

type StepKindMeta = { kind: string; label: string; tagType: "primary" | "success" | "warning" | "info" };

const STEP_KIND_TAG: Record<string, StepKindMeta["tagType"]> = {
  llm: "primary",
  retrieval: "warning",
  pipeline: "success",
  load: "info",
  rules: "info",
};

const STEP_KIND_FALLBACK: Record<string, StepKindMeta> = {
  understand: { kind: "llm", label: "大模型", tagType: "primary" },
  toc_catalog_batch: { kind: "llm", label: "大模型", tagType: "primary" },
  faq_title_batch: { kind: "llm", label: "大模型", tagType: "primary" },
  plan: { kind: "llm", label: "大模型", tagType: "primary" },
  answer: { kind: "llm", label: "大模型", tagType: "primary" },
  tool: { kind: "retrieval", label: "知识检索", tagType: "warning" },
  outline: { kind: "load", label: "读库加载", tagType: "info" },
  toc: { kind: "load", label: "读库加载", tagType: "info" },
  plan_guard: { kind: "pipeline", label: "编排判断", tagType: "success" },
  verify: { kind: "rules", label: "规则校验", tagType: "info" },
  toc_drill: { kind: "pipeline", label: "编排判断", tagType: "success" },
};

const TOC_DRILL_TITLE: Record<string, string> = {
  pipeline_skip: "目录策略",
  pipeline_stop: "目录终止",
  auto_pick: "目录 · 自动进入",
  llm_pick: "目录 · 大模型选层",
  outcome: "目录 · 定位结果",
};

function stepTitle(ev: ChatTraceEvent, idx: number) {
  const p = ev.payload as Record<string, unknown> | undefined;
  let base = "";
  if (ev.step === "toc_drill") {
    const mode = String(p?.mode || "");
    base = TOC_DRILL_TITLE[mode] || "目录定位";
  } else if (ev.step === "tool") {
    base = "知识检索";
  } else if (ev.step === "outline" || ev.step === "toc") {
    base = "组装 Plan 目录";
  } else if (ev.step === "plan_guard") {
    base = "Plan 条号白名单";
  } else if (ev.step === "understand") {
    base = "理解问题";
  } else if (ev.step === "faq_title_batch") {
    base = "分批选 FAQ";
  } else if (ev.step === "toc_catalog_batch") {
    base = "分批选章";
  } else if (ev.step === "plan") {
    base = "拟定检索计划";
  } else if (ev.step === "verify") {
    base = "核对回答";
  } else if (ev.step === "answer") {
    base = "撰写回答";
  } else {
    base = ev.step;
  }
  if (ev.step === "tool" && p?.gap) {
    return `${idx + 1}. ${base} · ${String(p.gap)}`;
  }
  if (
    (ev.step === "toc_catalog_batch" || ev.step === "faq_title_batch") &&
    p?.batch_index &&
    p?.batch_total
  ) {
    return `${idx + 1}. ${base}（${p.batch_index}/${p.batch_total}）`;
  }
  if (ev.step === "toc_drill" && p?.level) {
    return `${idx + 1}. ${base}（L${p.level}）`;
  }
  return `${idx + 1}. ${base}`;
}

function formatTime(at: string) {
  try {
    return new Date(at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return "";
  }
}

function stepDisplay(ev: ChatTraceEvent): DisplayBlock | null {
  const p = ev.payload as Record<string, unknown> | undefined;
  const d = p?.display as DisplayBlock | undefined;
  if (d && (d.summary || d.input || d.output)) return d;
  return null;
}

function stepKind(ev: ChatTraceEvent): StepKindMeta {
  const p = ev.payload as Record<string, unknown> | undefined;
  const label = String(p?.step_kind_label || stepDisplay(ev)?.step_kind_label || "").trim();
  const kind = String(p?.step_kind || stepDisplay(ev)?.step_kind || "").trim();
  if (label && kind) {
    return { kind, label, tagType: STEP_KIND_TAG[kind] || "info" };
  }
  return STEP_KIND_FALLBACK[ev.step] || { kind: "pipeline", label: "编排判断", tagType: "success" };
}

type LlmCallRecord = {
  model?: string;
  json_mode?: boolean;
  request?: { system?: string; user?: string };
  response_text?: string;
  usage?: unknown;
  response_api?: unknown;
};

function isStepExpanded(idx: number) {
  return expandedSteps.value.has(idx);
}

function toggleStepExpand(idx: number) {
  const next = new Set(expandedSteps.value);
  if (next.has(idx)) {
    next.delete(idx);
  } else {
    next.add(idx);
  }
  expandedSteps.value = next;
}

function llmCalls(ev: ChatTraceEvent): LlmCallRecord[] {
  const p = ev.payload as Record<string, unknown> | undefined;
  const raw = p?.llm_calls;
  return Array.isArray(raw) ? (raw as LlmCallRecord[]) : [];
}

/** 仅当本步标明会调大模型、却没有任何 llm_calls 时提示异常。 */
function llmCaptureMissing(ev: ChatTraceEvent): boolean {
  const p = ev.payload as Record<string, unknown> | undefined;
  if (p?.llm_invoked === false) {
    return false;
  }
  if (stepKind(ev).kind !== "llm") {
    return false;
  }
  return llmCalls(ev).length === 0;
}

function rawPayload(ev: ChatTraceEvent): Record<string, unknown> {
  const p = (ev.payload as Record<string, unknown> | undefined) || {};
  const out: Record<string, unknown> = { step: ev.step, at: ev.at };
  for (const [k, v] of Object.entries(p)) {
    if (k === "display") continue;
    out[k] = v;
  }
  return out;
}

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

async function scrollMessages() {
  await nextTick();
  scrollRef.value?.scrollTo({ top: scrollRef.value.scrollHeight, behavior: "smooth" });
}

function onComposerKeydown(event: KeyboardEvent) {
  if (event.key !== "Enter" || event.repeat || event.shiftKey || event.altKey) return;
  if (event.isComposing || event.keyCode === 229) return;
  if (event.ctrlKey || event.metaKey) {
    event.preventDefault();
    lastEnterAt.value = 0;
    void send();
    return;
  }
  const now = performance.now();
  if (now - lastEnterAt.value <= 600) {
    event.preventDefault();
    lastEnterAt.value = 0;
    void send();
    return;
  }
  lastEnterAt.value = now;
}

async function send() {
  const q = question.value.trim();
  if (!q || loading.value) return;
  if (!documentId.value.trim()) {
    ElMessage.warning(T.chatKbPlaceholder);
    return;
  }
  messages.value.push({ role: "user", content: q });
  question.value = "";
  loading.value = true;
  trace.value = [];
  expandedSteps.value = new Set();
  verifyOk.value = null;
  runningLabel.value = "准备开始…";
  const assistantIdx =
    messages.value.push({ role: "assistant", content: "", pending: true }) - 1;
  await scrollMessages();

  const startedAt = performance.now();
  try {
    const res = await chatStream(
      q,
      documentId.value.trim() || undefined,
      {
        onProgress: (label) => {
          runningLabel.value = label;
        },
        onTrace: (event) => {
          trace.value.push(event);
        },
      },
    );
    const elapsedSeconds =
      res.elapsed_seconds ?? Math.round((performance.now() - startedAt) / 100) / 10;
    messages.value[assistantIdx] = {
      role: "assistant",
      content: res.answer,
      elapsedSeconds,
    };
    verifyOk.value = res.verify?.ok ?? null;
  } catch (e: unknown) {
    ElMessage.error(String(e));
    messages.value[assistantIdx] = {
      role: "assistant",
      content: `暂时无法回答：${e}`,
    };
  } finally {
    loading.value = false;
    runningLabel.value = "";
    await scrollMessages();
  }
}
</script>

<style scoped>
.page {
  height: 100%;
  max-height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}
.page :deep(.el-row) {
  flex: 1;
  min-height: 0;
  height: 100%;
  align-items: stretch;
}
.col-chat {
  align-self: flex-start;
}
.col-trace {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  max-height: 100%;
  overflow: hidden;
}
.trace-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  max-height: 100%;
  overflow: hidden;
}
.trace-card :deep(.el-card__header) {
  flex-shrink: 0;
}
.trace-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding-top: 8px;
}
.messages {
  height: 420px;
  overflow-y: auto;
  padding: 8px;
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  margin-bottom: 12px;
}
.msg {
  display: flex;
  margin-bottom: 12px;
}
.msg.user {
  justify-content: flex-end;
}
.msg.assistant {
  justify-content: flex-start;
}
.bubble {
  max-width: 85%;
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e4e7ed;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.msg.user .bubble {
  background: #ecf5ff;
  border-color: #b3d8ff;
}
.role {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.text {
  white-space: pre-wrap;
  line-height: 1.5;
  font-size: 14px;
}
.msg-meta {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid #ebeef5;
  font-size: 12px;
  color: #909399;
  text-align: right;
}
.text.pending {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #606266;
}
.composer-actions {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.composer-actions .hint {
  font-size: 12px;
  color: #909399;
}
.trace-timeline {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}
.trace-step {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  border: 1px solid #ebeef5;
  background: #fafafa;
  animation: step-in 0.35s ease;
  border-left-width: 3px;
  border-left-color: #dcdfe6;
}
.trace-step.kind-llm {
  border-left-color: #409eff;
}
.trace-step.kind-retrieval {
  border-left-color: #e6a23c;
}
.trace-step.kind-pipeline {
  border-left-color: #67c23a;
}
.trace-step.kind-load {
  border-left-color: #909399;
}
.trace-step.kind-rules {
  border-left-color: #b88230;
}
.trace-step-clickable {
  cursor: pointer;
}
.trace-step-clickable:hover {
  border-color: #c6e2ff;
}
.trace-step.expanded {
  border-color: #409eff;
  background: #fff;
}
.trace-step.done.highlight {
  border-color: #b3d8ff;
  background: #f0f9ff;
}
.expand-hint {
  font-size: 11px;
  font-weight: normal;
  color: #909399;
}
.trace-detail-collapsed {
  padding: 8px 10px;
}
.trace-detail-expanded {
  max-height: min(70vh, 560px);
  overflow: auto;
}
.section-label {
  margin: 12px 0 6px;
  font-size: 12px;
  font-weight: 700;
  color: #606266;
}
.section-label:first-child {
  margin-top: 0;
}
.mini-label {
  margin: 8px 0 4px;
  font-size: 11px;
  font-weight: 600;
  color: #909399;
}
.llm-block {
  margin-bottom: 12px;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
  border: 1px solid #ebeef5;
}
.llm-block-title {
  margin: 0 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: #409eff;
}
.raw-json {
  font-size: 11px;
  line-height: 1.45;
  margin: 0 0 8px;
  padding: 8px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 320px;
  overflow: auto;
}
.line-summary.muted {
  color: #909399;
}
.llm-missing-hint {
  margin: 8px 0;
  font-size: 12px;
  color: #e6a23c;
  line-height: 1.5;
}
.trace-step.active {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #409eff;
  border-style: dashed;
  background: #fff;
}
.step-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.step-kind-tag {
  flex-shrink: 0;
  font-weight: 500;
}
.step-title {
  flex: 1;
  min-width: 120px;
}
.step-time {
  margin-left: auto;
  font-weight: normal;
  font-size: 11px;
  color: #909399;
}
.trace-detail {
  font-size: 13px;
  max-height: none;
  overflow: visible;
  background: #fff;
  padding: 10px;
  border-radius: 4px;
  margin: 0;
  line-height: 1.55;
  color: #303133;
}
.line-summary {
  margin: 0 0 8px;
  color: #606266;
}
.line-io {
  margin: 0 0 8px;
  white-space: pre-wrap;
  word-break: break-word;
}
.line-io .label {
  display: inline-block;
  min-width: 2.5em;
  font-weight: 600;
  color: #409eff;
  margin-right: 6px;
}
.trace-detail .fallback {
  font-size: 11px;
  margin: 0;
  white-space: pre-wrap;
}
@keyframes step-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
