<template>
  <div class="page">
    <el-card shadow="never" class="panel">
      <template #header>
        <div class="hdr">
          <span>{{ T.catalog }} · {{ tocFlat.length }} 条</span>
          <div class="hdr-actions">
            <el-button type="success" :loading="loading.publish" @click="doPublish">{{ T.btnPublish }}</el-button>
            <el-button link type="primary" @click="goReview">{{ T.btnReview }}</el-button>
            <el-button link type="primary" @click="reload">刷新</el-button>
          </div>
        </div>
      </template>
      <p class="edit-hint">{{ T.tipEditBody }}</p>
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
        <el-table-column prop="section_ref" label="章节号" width="100" />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="kind" label="层级" width="80">
          <template #default="{ row }">{{ row.kind === "chapter" ? "章" : "条" }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="88">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'published' ? 'success' : 'warning'">
              {{ row.status === "published" ? T.catalogPublished : T.catalogDraft }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-divider />
      <el-form label-width="72px" :disabled="!edit.node_id">
        <el-form-item label="标题">
          <el-input v-model="edit.title" />
        </el-form-item>
        <el-form-item v-if="edit.kind === 'leaf'" :label="T.reviewAnswerLabel">
          <el-input v-model="edit.body" type="textarea" :rows="8" />
        </el-form-item>
        <el-form-item v-if="edit.kind !== 'leaf'" :label="T.reviewSummaryLabel">
          <el-input v-model="edit.summary" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading.save" @click="saveNode">保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { T } from "@/constants/terminology";
import { fetchToc, patchNode, publishDocument, type TocNode } from "@/api/client";
import { formatApiError } from "@/api/httpError";
import { useDocumentId } from "@/composables/useDocumentId";

const route = useRoute();
const router = useRouter();
const { documentId, setDocumentId } = useDocumentId();

const tocFlat = ref<TocNode[]>([]);
const loading = reactive({ publish: false, save: false });
const edit = reactive({ node_id: "", kind: "", title: "", summary: "", body: "" });

function syncDocFromRoute() {
  const param = String(route.params.documentId || "");
  if (!param || param === "_") {
    router.replace({ name: "library" });
    return;
  }
  if (param !== documentId.value) setDocumentId(param);
}

function goReview() {
  router.push({ name: "library-review", params: { documentId: documentId.value } });
}

async function reload() {
  const doc = documentId.value.trim();
  if (!doc) return;
  try {
    const toc = await fetchToc(doc);
    tocFlat.value = toc.nodes || [];
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  }
}

watch(() => route.params.documentId, syncDocFromRoute, { immediate: true });
watch(documentId, reload, { immediate: true });

async function doPublish() {
  loading.publish = true;
  try {
    await publishDocument(documentId.value.trim());
    ElMessage.success(T.msgPublished);
    await reload();
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.publish = false;
  }
}

function selectNode(row: TocNode) {
  edit.node_id = row.node_id;
  edit.kind = row.kind;
  edit.title = row.title;
  edit.summary = row.summary || "";
  edit.body = row.body || "";
}

async function saveNode() {
  if (!edit.node_id) {
    ElMessage.warning("请先点选表格中的一行");
    return;
  }
  loading.save = true;
  try {
    const summary =
      edit.kind === "leaf"
        ? edit.body.length > 280
          ? `${edit.body.slice(0, 280)}…`
          : edit.body
        : edit.summary;
    await patchNode(edit.node_id, edit.title, summary, edit.body);
    ElMessage.success("已保存");
    await reload();
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.save = false;
  }
}

onMounted(syncDocFromRoute);
</script>

<style scoped>
.page {
  max-width: 960px;
}
.hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.hdr-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.edit-hint {
  font-size: 13px;
  color: #909399;
  margin: 0 0 12px;
}
</style>