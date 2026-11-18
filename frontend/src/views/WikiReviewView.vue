<template>
  <div class="page review-page">
    <el-row :gutter="16" class="review-row">
      <el-col :span="10" class="review-col">
        <el-card shadow="never" class="pane-card tree-card">
          <template #header>
            <span>目录树</span>
            <el-button link type="primary" @click="loadToc">刷新</el-button>
          </template>
          <div class="pane-scroll">
            <el-tree
              v-if="treeData.length"
              :data="treeData"
              :props="{ label: 'label', children: 'children' }"
              node-key="node_id"
              highlight-current
              default-expand-all
              @node-click="onNodeClick"
            />
            <el-empty v-else :description="T.catalogEmptyNeedParse" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="14" class="review-col">
        <el-card shadow="never" class="pane-card detail-card">
          <template #header>
            <div class="hdr">
              <span>条目</span>
              <el-button type="success" size="small" :loading="loading.publish" @click="publish">
                {{ T.btnPublish }}
              </el-button>
            </div>
          </template>
          <div class="pane-scroll">
            <el-form label-width="72px">
              <el-form-item label="标题">
                <el-input v-model="edit.title" />
              </el-form-item>
              <el-form-item v-if="edit.kind === 'leaf'" :label="T.reviewAnswerLabel">
                <el-input v-model="edit.body" type="textarea" :rows="12" placeholder="入库的 **答：** 正文" />
              </el-form-item>
              <el-alert
                v-else-if="edit.node_id"
                type="info"
                :closable="false"
                show-icon
                :title="T.reviewChapterNoAnswer"
              />
              <el-form-item label="状态">
                <el-tag :type="edit.status === 'published' ? 'success' : 'warning'">
                  {{ statusLabel(edit.status) }}
                </el-tag>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="loading.save" :disabled="!edit.node_id" @click="save">
                  保存
                </el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { T } from "@/constants/terminology";
import { fetchToc, patchNode, publishDocument, type TocNode } from "@/api/client";
import { formatApiError } from "@/api/httpError";
import { useDocumentId } from "@/composables/useDocumentId";
import { buildTocTree, type TreeNode } from "@/utils/tocTree";

const route = useRoute();
const router = useRouter();
const { documentId, setDocumentId } = useDocumentId();

const nodes = ref<TocNode[]>([]);
const loading = reactive({ publish: false, save: false });
const edit = reactive({
  node_id: "",
  section_ref: "",
  kind: "",
  title: "",
  summary: "",
  body: "",
  status: "",
});

interface TreeItem {
  node_id: string;
  label: string;
  children: TreeItem[];
}

function statusLabel(s: string) {
  if (s === "published") return T.catalogPublished;
  if (s === "draft") return T.catalogDraft;
  return s || "—";
}

function toTreeItems(list: TreeNode[]): TreeItem[] {
  return list.map((n) => ({
    node_id: n.node_id,
    label: `[${n.section_ref || "—"}] ${n.title}`,
    children: toTreeItems(n.children),
  }));
}

const treeData = computed(() => toTreeItems(buildTocTree(nodes.value)));

function syncDocFromRoute() {
  const param = String(route.params.documentId || "");
  if (!param || param === "_") {
    router.replace({ name: "library" });
    return;
  }
  if (param !== documentId.value) setDocumentId(param);
}

async function loadToc() {
  const doc = documentId.value.trim();
  if (!doc) return;
  try {
    const data = await fetchToc(doc);
    nodes.value = data.nodes || [];
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  }
}

watch(() => route.params.documentId, syncDocFromRoute, { immediate: true });
watch(documentId, loadToc, { immediate: true });

function onNodeClick(data: TreeItem) {
  const n = nodes.value.find((x) => x.node_id === data.node_id);
  if (!n) return;
  edit.node_id = n.node_id;
  edit.section_ref = n.section_ref;
  edit.kind = n.kind;
  edit.title = n.title;
  edit.summary = n.summary || "";
  edit.body = n.body || "";
  edit.status = n.status;
}

async function publish() {
  loading.publish = true;
  try {
    await publishDocument(documentId.value.trim());
    ElMessage.success(T.msgPublished);
    await loadToc();
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.publish = false;
  }
}

async function save() {
  if (!edit.node_id) return;
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
    await loadToc();
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.save = false;
  }
}
</script>

<style scoped>
.review-page {
  max-width: 1100px;
  height: 100%;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}
.review-row {
  flex: 1;
  min-height: 0;
  height: 100%;
  align-items: stretch;
}
.review-row > :deep(.el-col) {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.review-col {
  min-height: 0;
}
.review-col > .pane-card {
  flex: 1;
  min-height: 0;
}
.pane-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
.pane-card :deep(.el-card__header) {
  flex-shrink: 0;
}
.pane-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-top: 8px;
}
.pane-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 4px;
}
.detail-card {
  /* 右侧固定占位，仅各自 pane 内滚动 */
}
.hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>