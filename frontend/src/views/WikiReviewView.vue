<template>
  <div class="page">
    <el-alert type="warning" :closable="false" show-icon class="hint">
      此页适合管理员：从服务器上的文件路径导入。普通用户请在「搭建知识库」里上传即可。
    </el-alert>

    <el-card shadow="never">
      <template #header>从服务器文件导入</template>
      <el-form inline>
        <el-form-item label="文件在服务器上的位置">
          <el-input
            v-model="txtPath"
            placeholder="例如 docs/员工手册.txt"
            style="width: 420px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading.ingest" @click="ingestFromPath">{{ T.btnParse }}</el-button>
          <el-button type="success" :loading="loading.publish" @click="publish">{{ T.btnPublish }}</el-button>
          <el-button @click="loadToc">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="16" class="body">
      <el-col :span="10">
        <el-card shadow="never" class="tree-card">
          <template #header>{{ T.catalog }}（树形）</template>
          <el-tree
            v-if="treeData.length"
            :data="treeData"
            :props="{ label: 'label', children: 'children' }"
            node-key="node_id"
            highlight-current
            default-expand-all
            @node-click="onNodeClick"
          />
          <el-empty v-else :description="`暂无${T.catalog}，请先${T.btnParse}`" />
        </el-card>
      </el-col>
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>修改这一条</template>
          <el-form label-width="88px">
            <el-form-item :label="T.entryCode">
              <el-input v-model="edit.node_id" readonly />
            </el-form-item>
            <el-form-item label="章节号">
              <el-input v-model="edit.section_ref" readonly />
            </el-form-item>
            <el-form-item label="标题">
              <el-input v-model="edit.title" />
            </el-form-item>
            <el-form-item label="摘要">
              <el-input v-model="edit.summary" type="textarea" :rows="4" />
            </el-form-item>
            <el-form-item label="状态">
              <el-tag :type="edit.status === 'published' ? 'success' : 'warning'">
                {{ statusLabel(edit.status) }}
              </el-tag>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="loading.save" @click="save">保存修改</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { T } from "@/constants/terminology";
import {
  fetchToc,
  ingestPath,
  patchNode,
  publishDocument,
  type TocNode,
} from "@/api/client";
import { useDocumentId } from "@/composables/useDocumentId";
import { buildTocTree, type TreeNode } from "@/utils/tocTree";

const { documentId, setDocumentId } = useDocumentId();
const txtPath = ref("docs/星河科技_中文员工手册_知识库测试.txt");
const nodes = ref<TocNode[]>([]);
const loading = reactive({ ingest: false, publish: false, save: false });
const edit = reactive({
  node_id: "",
  section_ref: "",
  title: "",
  summary: "",
  status: "",
  kind: "",
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

async function loadToc() {
  const doc = documentId.value.trim();
  if (!doc) return;
  try {
    const data = await fetchToc(doc);
    nodes.value = data.nodes || [];
  } catch (e: unknown) {
    ElMessage.error(String(e));
  }
}

watch(documentId, () => loadToc(), { immediate: true });

function onNodeClick(data: TreeItem) {
  const n = nodes.value.find((x) => x.node_id === data.node_id);
  if (!n) return;
  edit.node_id = n.node_id;
  edit.section_ref = n.section_ref;
  edit.title = n.title;
  edit.summary = n.summary || "";
  edit.status = n.status;
  edit.kind = n.kind;
}

async function ingestFromPath() {
  loading.ingest = true;
  try {
    const data = await ingestPath(txtPath.value, documentId.value.trim() || undefined);
    if (data.document_id) setDocumentId(data.document_id);
    ElMessage.success(T.msgDraftReady);
    await loadToc();
  } catch (e: unknown) {
    ElMessage.error(String(e));
  } finally {
    loading.ingest = false;
  }
}

async function publish() {
  loading.publish = true;
  try {
    await publishDocument(documentId.value.trim());
    ElMessage.success(T.msgPublished);
    await loadToc();
  } catch (e: unknown) {
    ElMessage.error(String(e));
  } finally {
    loading.publish = false;
  }
}

async function save() {
  if (!edit.node_id) return;
  loading.save = true;
  try {
    await patchNode(edit.node_id, edit.title, edit.summary);
    ElMessage.success("已保存");
    await loadToc();
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
.hint {
  margin-bottom: 0;
}
.body {
  margin-top: 0;
}
.tree-card {
  min-height: 480px;
}
</style>
