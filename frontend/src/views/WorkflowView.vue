<template>
  <div class="page">
    <el-alert type="info" :closable="false" show-icon class="term-tip">
      <template #title>{{ T.tipTitle }}</template>
      {{ T.tipBody }}
    </el-alert>

    <el-row :gutter="16">
      <el-col :span="14">
        <el-card shadow="never" class="panel">
          <template #header>
            <span>进行到哪一步了</span>
            <el-button link type="primary" @click="reload">刷新</el-button>
          </template>
          <el-steps :active="stepActive" finish-status="success" align-center>
            <el-step :title="T.stepUpload" :description="T.stepUploadDesc" />
            <el-step :title="T.stepParse" :description="T.stepParseDesc" />
            <el-step :title="T.stepReview" :description="T.stepReviewDesc" />
            <el-step :title="T.stepPublish" :description="T.stepPublishDesc" />
            <el-step :title="T.stepQa" :description="T.stepQaDesc" />
          </el-steps>
          <el-descriptions :column="2" border size="small" class="meta">
            <el-descriptions-item :label="T.docCode">{{ wf?.document_id || T.docCodeHint }}</el-descriptions-item>
            <el-descriptions-item label="当前进度">{{ stepLabel }}</el-descriptions-item>
            <el-descriptions-item label="文件位置" :span="2">
              {{ wf?.uploaded_path || "尚未上传" }}
            </el-descriptions-item>
            <el-descriptions-item :label="T.colPendingSections">{{ wf?.draft_nodes ?? 0 }}</el-descriptions-item>
            <el-descriptions-item :label="T.colLiveEntries">{{ wf?.published_leaves ?? 0 }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never" class="panel">
          <template #header>我要操作</template>
          <el-form label-position="top">
            <el-form-item label="选择员工手册或制度文本（.txt）">
              <el-upload
                :auto-upload="false"
                :limit="1"
                accept=".txt"
                :on-change="onFilePick"
                :file-list="fileList"
              >
                <el-button type="primary" plain>选择文件</el-button>
              </el-upload>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="loading.upload" @click="doUpload">{{ T.btnUploadSave }}</el-button>
              <el-button :loading="loading.ingest" @click="doIngest">{{ T.btnParse }}</el-button>
              <el-button type="success" :loading="loading.publish" @click="doPublish">{{ T.btnPublish }}</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="showAuditGuide" shadow="never" class="audit-card">
      <template #header>{{ T.auditTitle }}</template>
      <ol class="audit-list">
        <li v-for="(line, i) in T.auditSteps" :key="i">{{ line }}</li>
      </ol>
      <el-button type="primary" link @click="router.push('/wiki')">{{ T.auditTreeLink }}</el-button>
    </el-card>

    <el-card shadow="never" class="panel toc-panel">
      <template #header>
        <span>
          {{ T.catalog }}（共 {{ tocFlat.length }} 条，{{ T.catalogDraft }}）
          <span v-if="(wf?.draft_nodes ?? 0) > 0" class="header-hint">— 请点击表格中的某一行开始检查</span>
        </span>
      </template>
      <el-table
        :data="tocFlat"
        row-key="node_id"
        size="small"
        border
        stripe
        max-height="420"
        highlight-current-row
        @row-click="selectNode"
      >
        <template #empty>
          <el-empty :description="emptyCatalogHint" />
        </template>
        <el-table-column prop="section_ref" label="章节号" width="100" />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="kind" label="层级" width="80">
          <template #default="{ row }">
            {{ row.kind === "chapter" ? "章/节" : "条目" }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="96">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'published' ? 'success' : 'warning'">
              {{ row.status === "published" ? T.catalogPublished : T.catalogDraft }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-divider />
      <p v-if="selectedTitle" class="selected-hint">正在编辑：{{ selectedTitle }}</p>
      <p v-else class="edit-hint">请先在上方表格中<strong>点击一行</strong>，再改标题或摘要。</p>
      <el-form label-width="88px" :disabled="!edit.node_id">
        <el-form-item :label="T.entryCode">
          <el-input v-model="edit.node_id" readonly />
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="edit.title" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="edit.summary" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading.save" @click="saveNode">保存修改</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import type { UploadFile, UploadUserFile } from "element-plus";
import { ElMessage } from "element-plus";
import { T, stepLabels } from "@/constants/terminology";
import {
  fetchToc,
  fetchWorkflow,
  fetchWorkflowCurrent,
  ingestDocument,
  patchNode,
  publishDocument,
  uploadDocument,
  type TocNode,
  type WorkflowState,
} from "@/api/client";
import { useDocumentId } from "@/composables/useDocumentId";

const router = useRouter();
const { documentId, setDocumentId, refreshFromServer } = useDocumentId();
const wf = ref<WorkflowState | null>(null);
const tocFlat = ref<TocNode[]>([]);
const picked = ref<File | null>(null);
const fileList = ref<UploadUserFile[]>([]);
const loading = reactive({ upload: false, ingest: false, publish: false, save: false });
const edit = reactive({ node_id: "", title: "", summary: "" });

const stepMap: Record<string, number> = {
  upload: 0,
  ingest_draft: 1,
  review: 2,
  publish: 3,
  qa_ready: 4,
};

const stepActive = computed(() => stepMap[wf.value?.current_step || "upload"] ?? 0);
const stepLabel = computed(() => stepLabels[wf.value?.current_step || "upload"] || "—");

const showAuditGuide = computed(() => {
  const step = wf.value?.current_step;
  return (wf.value?.draft_nodes ?? 0) > 0 || step === "review" || step === "ingest_draft";
});

const emptyCatalogHint = computed(() => {
  if ((wf.value?.draft_nodes ?? 0) > 0) return T.catalogEmptyMismatch;
  const step = wf.value?.current_step;
  if (step === "upload" || !wf.value?.uploaded_path) return T.catalogEmptyNeedParse;
  return T.catalogEmptyNeedParse;
});

const selectedTitle = computed(() => edit.title || "");

async function reload() {
  try {
    let doc = documentId.value.trim();
    if (!doc) {
      wf.value = await fetchWorkflowCurrent();
      doc = wf.value?.document_id || "";
      if (doc) setDocumentId(doc);
    } else {
      wf.value = await fetchWorkflow(doc);
    }
    if (!doc) {
      tocFlat.value = [];
      return;
    }
    const toc = await fetchToc(doc);
    tocFlat.value = toc.nodes || [];
  } catch (e: unknown) {
    ElMessage.error(String(e));
  }
}

watch(documentId, () => reload(), { immediate: true });

function onFilePick(file: UploadFile) {
  picked.value = file.raw ?? null;
  fileList.value = file.raw ? [{ name: file.name, url: "" }] : [];
}

async function doUpload() {
  if (!picked.value) {
    ElMessage.warning("请先选择文件");
    return;
  }
  loading.upload = true;
  try {
    const res = await uploadDocument(picked.value);
    setDocumentId(res.document_id);
    wf.value = res.workflow;
    ElMessage.success(`${T.msgUploadOk}，${T.docCode}：${res.document_id}`);
    await refreshFromServer();
    await reload();
  } catch (e: unknown) {
    ElMessage.error(String(e));
  } finally {
    loading.upload = false;
  }
}

async function doIngest() {
  loading.ingest = true;
  try {
    await ingestDocument(documentId.value.trim() || undefined);
    ElMessage.success(T.msgDraftReady);
    await reload();
  } catch (e: unknown) {
    ElMessage.error(String(e));
  } finally {
    loading.ingest = false;
  }
}

async function doPublish() {
  loading.publish = true;
  try {
    await publishDocument(documentId.value.trim() || undefined);
    ElMessage.success(T.msgPublished);
    await reload();
  } catch (e: unknown) {
    ElMessage.error(String(e));
  } finally {
    loading.publish = false;
  }
}

function selectNode(row: TocNode) {
  edit.node_id = row.node_id;
  edit.title = row.title;
  edit.summary = row.summary || "";
}

async function saveNode() {
  if (!edit.node_id) {
    ElMessage.warning("请先在表格里点选要改的那一行");
    return;
  }
  loading.save = true;
  try {
    await patchNode(edit.node_id, edit.title, edit.summary);
    ElMessage.success("已保存");
    await reload();
  } catch (e: unknown) {
    ElMessage.error(String(e));
  } finally {
    loading.save = false;
  }
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.term-tip {
  margin-bottom: 0;
}
.panel {
  margin-bottom: 0;
}
.meta {
  margin-top: 20px;
}
.toc-panel {
  flex: 1;
}
.edit-hint {
  font-size: 13px;
  color: #606266;
  margin: 0 0 12px;
}
.selected-hint {
  font-size: 13px;
  color: #409eff;
  margin: 0 0 12px;
}
.audit-card {
  margin-bottom: 0;
}
.audit-list {
  margin: 0 0 12px;
  padding-left: 20px;
  line-height: 1.8;
  color: #606266;
  font-size: 14px;
}
.header-hint {
  font-weight: normal;
  font-size: 13px;
  color: #909399;
}
</style>
