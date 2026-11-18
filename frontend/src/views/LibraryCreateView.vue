<template>
  <div class="page">
    <el-steps :active="stepIndex" finish-status="success" align-center class="steps">
      <el-step title="上传文件" :description="T.stepUploadDesc" />
      <el-step :title="T.btnParse" description="按规范解析章节" />
      <el-step title="检查发布" description="审核后可正式发布" />
    </el-steps>

    <el-card shadow="never" class="panel">
      <template v-if="phase === 'upload'">
        <p class="step-label">第 1 步</p>
        <p class="hint">{{ EXTERNAL_ORGANIZE_HINT }}</p>
        <el-alert type="warning" :closable="false" show-icon class="format-alert" :title="T.docFormatHint" />
        <el-card shadow="never" class="prompt-card">
          <template #header>
            <div class="prompt-header">
              <span>{{ T.organizePromptTitle }}</span>
              <el-button type="primary" size="small" @click="copyOrganizePrompt">
                {{ T.organizePromptCopy }}
              </el-button>
            </div>
          </template>
          <el-input
            :model-value="EXTERNAL_ORGANIZE_PROMPT"
            type="textarea"
            :rows="14"
            readonly
            class="prompt-text"
          />
          <p class="prompt-foot">{{ T.handbookOrganizeNote }}</p>
        </el-card>
        <el-form label-position="top">
          <el-form-item :label="T.uploadFileLabel">
            <el-upload
              :auto-upload="false"
              :limit="1"
              accept=".txt,.md,.markdown"
              :on-change="onFilePick"
              :file-list="fileList"
            >
              <el-button>选择文件</el-button>
            </el-upload>
          </el-form-item>
          <div class="actions">
            <el-button
              type="primary"
              size="large"
              class="primary-cta"
              :loading="loading.busy"
              :disabled="!picked"
              @click="uploadAndIngest"
            >
              {{ loading.busy ? busyLabel : T.btnUploadAndIngest }}
            </el-button>
            <el-button
              text
              type="primary"
              :disabled="!picked || loading.busy"
              @click="doUploadOnly"
            >
              {{ T.btnUploadSave }}
            </el-button>
          </div>
          <div v-if="ingesting" class="progress-box">
            <p class="progress-title">{{ T.ingestProgressTitle }}</p>
            <el-progress :percentage="ingestProgress.percent" :stroke-width="14" :striped="ingestProgress.percent < 100" striped-flow />
            <p class="progress-msg">{{ ingestProgress.message }}</p>
            <el-button link type="primary" @click="openLogs">{{ T.ingestOpenLogs }}</el-button>
          </div>
        </el-form>
      </template>

      <template v-else-if="phase === 'ingest'">
        <p class="step-label">第 2 步 · {{ T.btnParse }}</p>
        <el-descriptions :column="1" border size="small" class="meta">
          <el-descriptions-item :label="T.docCode">{{ documentId }}</el-descriptions-item>
          <el-descriptions-item label="已上传文件">
            {{ fileBasename }}
          </el-descriptions-item>
        </el-descriptions>
        <p class="hint">{{ T.tipNewStep2 }}</p>
        <div v-if="ingesting" class="progress-box">
          <p class="progress-title">{{ T.ingestProgressTitle }}</p>
          <el-progress :percentage="ingestProgress.percent" :stroke-width="14" :striped="ingestProgress.percent < 100" striped-flow />
          <p class="progress-msg">{{ ingestProgress.message }}</p>
          <el-button link type="primary" @click="openLogs">{{ T.ingestOpenLogs }}</el-button>
        </div>
        <el-button
          v-else
          type="primary"
          size="large"
          class="primary-cta"
          :disabled="ingesting"
          @click="doIngest"
        >
          {{ T.btnParse }}
        </el-button>
      </template>

      <template v-else>
        <p class="step-label">第 3 步 · 检查发布</p>
        <el-result icon="success" :title="T.msgDraftReady">
          <template #sub-title>
            {{ T.colPendingSections }}：{{ wf?.draft_nodes ?? 0 }} ·
            {{ T.colLiveEntries }}：{{ wf?.published_leaves ?? 0 }}
          </template>
          <template #extra>
            <el-button type="primary" @click="goReview">{{ T.btnReview }}</el-button>
            <el-button type="success" size="large" :loading="loading.publish" @click="doPublish">
              {{ T.btnPublish }}
            </el-button>
            <el-button @click="goEdit">{{ T.btnEdit }}</el-button>
          </template>
        </el-result>
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { UploadFile, UploadUserFile } from "element-plus";
import { ElMessage } from "element-plus";
import { EXTERNAL_ORGANIZE_HINT, EXTERNAL_ORGANIZE_PROMPT } from "@/constants/organizePrompt";
import { T } from "@/constants/terminology";
import {
  fetchWorkflow,
  ingestDocumentStream,
  publishDocument,
  uploadDocument,
  type WorkflowState,
} from "@/api/client";
import { formatApiError } from "@/api/httpError";
import { useDocumentId } from "@/composables/useDocumentId";
import { useLogDock } from "@/composables/useLogDock";

const route = useRoute();
const router = useRouter();
const { documentId, setDocumentId, refreshFromServer } = useDocumentId();

const wf = ref<WorkflowState | null>(null);
const picked = ref<File | null>(null);
const fileList = ref<UploadUserFile[]>([]);
const loading = reactive({ upload: false, ingest: false, publish: false, busy: false });
const busyPhase = ref<"upload" | "ingest" | "">("");
const ingesting = computed(() => loading.ingest || busyPhase.value === "ingest");
const ingestProgress = reactive({ percent: 0, message: "准备中…" });
const { showLogDock } = useLogDock();

function openLogs() {
  showLogDock();
}

async function copyOrganizePrompt() {
  try {
    await navigator.clipboard.writeText(EXTERNAL_ORGANIZE_PROMPT);
    ElMessage.success(T.organizePromptCopied);
  } catch {
    ElMessage.error("复制失败，请手动选中上方文本");
  }
}

async function runIngestStream(doc: string) {
  ingestProgress.percent = 0;
  ingestProgress.message = "启动整理…";
  showLogDock();
  await ingestDocumentStream(doc, {
    onProgress: (p) => {
      ingestProgress.percent = p.percent;
      ingestProgress.message = p.message;
    },
  });
}

const busyLabel = computed(() => {
  if (busyPhase.value === "upload") return "正在上传…";
  if (busyPhase.value === "ingest") return "正在整理目录（请稍候）…";
  return "";
});

const phase = computed(() => {
  const doc = documentId.value.trim();
  if (!doc) return "upload";
  const draft = wf.value?.draft_nodes ?? 0;
  if (draft > 0) return "done";
  if (wf.value?.uploaded_path) return "ingest";
  return "upload";
});

const stepIndex = computed(() => {
  if (phase.value === "upload") return 0;
  if (phase.value === "ingest") return 1;
  return 2;
});

const fileBasename = computed(() => {
  const p = wf.value?.uploaded_path || "";
  if (!p) return "—";
  const parts = p.split(/[/\\]/);
  return parts[parts.length - 1] || p;
});

function syncRouteDoc() {
  const param = String(route.params.documentId || "");
  if (param && param !== documentId.value) setDocumentId(param);
}

async function reload() {
  const doc = documentId.value.trim();
  if (!doc) {
    wf.value = null;
    return;
  }
  try {
    wf.value = await fetchWorkflow(doc);
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  }
}

watch(() => route.params.documentId, syncRouteDoc, { immediate: true });
watch(documentId, reload, { immediate: true });

function onFilePick(file: UploadFile) {
  picked.value = file.raw ?? null;
  fileList.value = file.raw ? [{ name: file.name, url: "" }] : [];
}

async function goIngestRoute(doc: string) {
  if (route.name !== "library-ingest") {
    await router.replace({ name: "library-ingest", params: { documentId: doc } });
  }
}

async function doUploadOnly() {
  if (!picked.value) {
    ElMessage.warning("请先选择文件");
    return;
  }
  loading.upload = true;
  try {
    const res = await uploadDocument(picked.value);
    setDocumentId(res.document_id);
    wf.value = res.workflow;
    await refreshFromServer();
    ElMessage.success(`${T.msgUploadOk}，请点击下方「${T.btnParse}」`);
    await goIngestRoute(res.document_id);
    await reload();
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.upload = false;
  }
}

async function uploadAndIngest() {
  if (!picked.value) {
    ElMessage.warning("请先选择文件");
    return;
  }
  loading.busy = true;
  busyPhase.value = "upload";
  try {
    const res = await uploadDocument(picked.value);
    setDocumentId(res.document_id);
    wf.value = res.workflow;
    await refreshFromServer();
    await goIngestRoute(res.document_id);
    busyPhase.value = "ingest";
    loading.ingest = true;
    await runIngestStream(res.document_id);
    ElMessage.success(T.msgDraftReady);
    await reload();
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
    await reload();
  } finally {
    loading.ingest = false;
    loading.busy = false;
    busyPhase.value = "";
  }
}

async function doIngest() {
  if (!documentId.value.trim()) {
    ElMessage.warning("请先上传文件");
    return;
  }
  loading.ingest = true;
  try {
    await runIngestStream(documentId.value.trim());
    ElMessage.success(T.msgDraftReady);
    await reload();
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.ingest = false;
  }
}

async function doPublish() {
  loading.publish = true;
  try {
    await publishDocument(documentId.value.trim());
    ElMessage.success(T.msgPublished);
    await router.push({ name: "library-edit", params: { documentId: documentId.value } });
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.publish = false;
  }
}

function goReview() {
  router.push({ name: "library-review", params: { documentId: documentId.value } });
}

function goEdit() {
  router.push({ name: "library-edit", params: { documentId: documentId.value } });
}
</script>

<style scoped>
.page {
  max-width: 720px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.steps {
  background: #fff;
  padding: 20px 16px;
  border-radius: 4px;
}
.panel {
  min-height: 200px;
}
.step-label {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
}
.hint {
  color: #606266;
  font-size: 14px;
  line-height: 1.6;
  margin: 0 0 20px;
}
.meta {
  margin-bottom: 16px;
}
.actions {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}
.primary-cta {
  min-width: 220px;
}
.progress-box {
  margin-top: 8px;
  padding: 16px;
  background: #f5f9ff;
  border-radius: 8px;
  border: 1px solid #d9ecff;
}
.progress-title {
  margin: 0 0 12px;
  font-weight: 600;
  color: #303133;
}
.progress-msg {
  margin: 12px 0 8px;
  font-size: 13px;
  color: #606266;
}
.format-alert {
  margin-bottom: 16px;
}
.prompt-card {
  margin-bottom: 20px;
  border: 1px solid #ebeef5;
}
.prompt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-weight: 600;
  color: #303133;
}
.prompt-text :deep(textarea) {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 12px;
  line-height: 1.5;
}
.prompt-foot {
  margin: 12px 0 0;
  font-size: 13px;
  color: #909399;
  line-height: 1.5;
}
</style>