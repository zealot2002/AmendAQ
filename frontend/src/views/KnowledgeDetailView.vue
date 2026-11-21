<template>
  <div class="detail-page" v-loading="pageLoading">
    <el-card shadow="never" class="head-card">
      <div v-if="library" class="head-row">
        <h2 class="head-title">{{ library.title }}</h2>
        <span class="head-meta">{{ T.docCode }}：{{ documentId }}</span>
      </div>
      <p v-if="library?.description" class="desc">{{ library.description }}</p>
      <p v-if="library" class="stats">
        {{ T.faqStatusDraft }}：{{ library.draft_count ?? 0 }} · {{ T.faqStatusLive }}：
        {{ library.published_leaves ?? 0 }}
      </p>
      <div class="actions">
        <el-button type="success" :loading="publishing" @click="doPublish">{{ T.btnPublish }}</el-button>
        <el-button @click="showImport = true">{{ T.btnBatchImport }}</el-button>
        <el-button type="primary" @click="openItemDialog()">{{ T.btnAddFaq }}</el-button>
      </div>
    </el-card>

    <el-card shadow="never" class="table-card">
      <div class="table-toolbar">
        <el-input
          v-model="keyword"
          class="search"
          clearable
          :prefix-icon="Search"
          :placeholder="T.searchFaq"
        />
      </div>
      <el-table
        v-if="filteredItems.length"
        :data="filteredItems"
        border
        stripe
        max-height="520"
        @row-click="(row: FaqItem) => openItemDialog(row)"
      >
        <el-table-column type="index" width="50" align="center" />
        <el-table-column :label="T.faqQuestion" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.question }}</template>
        </el-table-column>
        <el-table-column :label="T.faqAnswer" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">{{ row.answer }}</template>
        </el-table-column>
        <el-table-column :label="T.faqStatus" width="96" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'published' ? 'success' : 'warning'">
              {{ row.status === "published" ? T.faqStatusLive : T.faqStatusDraft }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="T.colActions" width="120" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click.stop="removeItem(row)">{{ T.btnDelete }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!pageLoading && !items.length" :description="T.faqEmpty">
        <el-button type="primary" @click="openItemDialog()">{{ T.btnAddFaq }}</el-button>
        <el-button @click="showImport = true">{{ T.btnBatchImport }}</el-button>
      </el-empty>
      <el-empty v-else-if="!pageLoading && !filteredItems.length" :description="T.searchNoMatch">
        <el-button @click="keyword = ''">{{ T.searchClear }}</el-button>
      </el-empty>
    </el-card>

    <el-dialog v-model="itemDialog" :title="editingItem ? '编辑问答' : T.btnAddFaq" width="560px" destroy-on-close>
      <el-form label-width="72px">
        <el-form-item :label="T.faqQuestion" required>
          <el-input v-model="itemForm.question" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item :label="T.faqAnswer" required>
          <el-input v-model="itemForm.answer" type="textarea" :rows="8" />
        </el-form-item>
        <el-form-item v-if="editingItem" :label="T.faqStatus">
          <el-radio-group v-model="itemForm.status">
            <el-radio value="draft">{{ T.faqStatusDraft }}</el-radio>
            <el-radio value="published">{{ T.faqStatusLive }}</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemDialog = false">取消</el-button>
        <el-button type="primary" :loading="itemSaving" @click="saveItem">{{ T.btnSave }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showImport" :title="T.batchImportTitle" width="640px" destroy-on-close>
      <p class="import-hint">{{ T.batchImportHint }}</p>
      <el-input v-model="importText" type="textarea" :rows="14" :placeholder="T.batchImportPlaceholder" />
      <template #footer>
        <el-button @click="showImport = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="doImport">导入为草稿</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { Search } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { T } from "@/constants/terminology";
import {
  createFaqItem,
  deleteFaqItem,
  fetchFaqItems,
  fetchLibrary,
  importFaqItems,
  publishLibrary,
  updateFaqItem,
  type FaqItem,
  type Library,
} from "@/api/client";
import { formatApiError } from "@/api/httpError";
import { useDocumentId } from "@/composables/useDocumentId";

const route = useRoute();
const router = useRouter();
const { setDocumentId } = useDocumentId();

const documentId = computed(() => String(route.params.documentId || ""));
const library = ref<Library | null>(null);
const items = ref<FaqItem[]>([]);
const keyword = ref("");
const pageLoading = ref(false);
const publishing = ref(false);
const itemDialog = ref(false);
const itemSaving = ref(false);
const editingItem = ref<FaqItem | null>(null);
const itemForm = reactive({ question: "", answer: "", status: "draft" });
const showImport = ref(false);
const importText = ref("");
const importing = ref(false);

const filteredItems = computed(() => {
  const q = keyword.value.trim().toLowerCase();
  if (!q) return items.value;
  return items.value.filter((row) => `${row.question} ${row.answer}`.toLowerCase().includes(q));
});

async function reload() {
  const id = documentId.value;
  if (!id) {
    router.replace({ name: "library" });
    return;
  }
  pageLoading.value = true;
  try {
    library.value = await fetchLibrary(id);
    setDocumentId(id, library.value.title);
    const pack = await fetchFaqItems(id);
    items.value = pack.items || [];
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
    router.replace({ name: "library" });
  } finally {
    pageLoading.value = false;
  }
}

function openItemDialog(row?: FaqItem) {
  editingItem.value = row || null;
  itemForm.question = row?.question || "";
  itemForm.answer = row?.answer || "";
  itemForm.status = row?.status || "draft";
  itemDialog.value = true;
}

async function saveItem() {
  const q = itemForm.question.trim();
  const a = itemForm.answer.trim();
  if (!q || !a) {
    ElMessage.warning("请填写问题和答案");
    return;
  }
  itemSaving.value = true;
  try {
    const id = documentId.value;
    if (editingItem.value) {
      await updateFaqItem(id, editingItem.value.item_id, {
        question: q,
        answer: a,
        status: itemForm.status,
      });
    } else {
      await createFaqItem(id, q, a, "draft");
    }
    ElMessage.success(T.msgFaqSaved);
    itemDialog.value = false;
    await reload();
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  } finally {
    itemSaving.value = false;
  }
}

async function removeItem(row: FaqItem) {
  try {
    await ElMessageBox.confirm(T.confirmDeleteFaq, "提示", { type: "warning" });
    await deleteFaqItem(documentId.value, row.item_id);
    await reload();
  } catch (e: unknown) {
    if (e === "cancel" || e === "close") return;
    ElMessage.error(formatApiError(e));
  }
}

async function doImport() {
  const text = importText.value.trim();
  if (!text) {
    ElMessage.warning("请粘贴导入内容");
    return;
  }
  importing.value = true;
  try {
    const res = await importFaqItems(documentId.value, text, true);
    const skip = res.skipped ?? 0;
    ElMessage.success(
      `${T.msgImportOk}：${res.imported} 条` + (skip ? `，跳过重复 ${skip} 条` : ""),
    );
    showImport.value = false;
    importText.value = "";
    await reload();
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  } finally {
    importing.value = false;
  }
}

async function doPublish() {
  publishing.value = true;
  try {
    await publishLibrary(documentId.value);
    ElMessage.success(T.msgPublished);
    await reload();
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  } finally {
    publishing.value = false;
  }
}

watch(
  () => route.params.documentId,
  () => {
    reload();
  },
);

onMounted(reload);
</script>

<style scoped>
.detail-page {
  max-width: 1100px;
}
.head-card {
  margin-bottom: 12px;
}
.head-title {
  margin: 0;
  font-size: 20px;
}
.head-meta {
  color: #909399;
  font-size: 13px;
  margin-left: 12px;
}
.head-row {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
}
.desc {
  color: #606266;
  margin: 8px 0;
}
.stats {
  margin: 0 0 12px;
  color: #606266;
  font-size: 13px;
}
.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.table-card {
  background: #fff;
}
.table-toolbar {
  margin-bottom: 12px;
}
.search {
  width: min(360px, 100%);
}
.import-hint {
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
  margin: 0 0 12px;
}
</style>