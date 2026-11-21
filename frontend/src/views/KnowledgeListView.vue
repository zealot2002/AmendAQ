<template>
  <div class="library-page">
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">
        <el-icon class="btn-icon"><Plus /></el-icon>
        {{ T.btnAddLibrary }}
      </el-button>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="libraries" border stripe v-loading="loading" empty-text=" ">
        <el-table-column prop="title" :label="T.colLibraryName" min-width="180">
          <template #default="{ row }">
            <span class="name">{{ row.title || row.display_title || row.document_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" :label="T.kbDescLabel" min-width="160" show-overflow-tooltip />
        <el-table-column :label="T.colStatus" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="statusOf(row).type">{{ statusOf(row).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="T.colFaqCount" width="90" align="center">
          <template #default="{ row }">{{ row.item_count ?? 0 }}</template>
        </el-table-column>
        <el-table-column prop="draft_count" :label="T.colPendingSections" width="100" align="center" />
        <el-table-column prop="published_leaves" :label="T.colLiveEntries" width="100" align="center" />
        <el-table-column :label="T.colActions" width="220" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="onDetail(row)">{{ T.btnDetail }}</el-button>
            <el-button link type="primary" @click="openEdit(row)">{{ T.btnEdit }}</el-button>
            <el-button link type="danger" @click="onDelete(row)">{{ T.btnDelete }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !libraries.length" :description="T.libraryEmpty">
        <el-button type="primary" @click="openCreate">{{ T.btnAddLibrary }}</el-button>
      </el-empty>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? T.kbCreateTitle : T.kbEditTitle"
      width="480px"
      destroy-on-close
      @closed="resetForm"
    >
      <el-form label-width="100px" @submit.prevent>
        <el-form-item :label="T.kbNameLabel" required>
          <el-input v-model="form.title" maxlength="80" show-word-limit />
        </el-form-item>
        <el-form-item :label="T.kbDescLabel">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">{{ T.btnSave }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus } from "@element-plus/icons-vue";
import { T } from "@/constants/terminology";
import {
  createLibrary,
  deleteLibrary,
  fetchLibraries,
  fetchMounts,
  updateLibrary,
  type Library,
  type Mount,
} from "@/api/client";
import { formatApiError } from "@/api/httpError";

type Row = Library & Mount;

const libraries = ref<Row[]>([]);
const loading = ref(false);
const saving = ref(false);
const router = useRouter();

const dialogVisible = ref(false);
const dialogMode = ref<"create" | "edit">("create");
const editingId = ref("");
const form = reactive({ title: "", description: "" });

function statusOf(row: Row) {
  const pub = row.published_leaves ?? 0;
  const draft = row.draft_count ?? 0;
  if (pub > 0) return { label: T.statusLive, type: "success" as const };
  if (draft > 0 || (row.item_count ?? 0) > 0) return { label: T.statusDraft, type: "warning" as const };
  return { label: T.statusPendingIngest, type: "info" as const };
}

async function load() {
  loading.value = true;
  try {
    const libData = await fetchLibraries();
    if ((libData.libraries || []).length > 0) {
      libraries.value = libData.libraries as Row[];
    } else {
      const data = await fetchMounts();
      libraries.value = (data.mounts || []).map((m) => ({
        document_id: m.document_id,
        title: m.display_title || m.document_id,
        display_title: m.display_title,
        description: m.description || "",
        draft_count: m.draft_count,
        published_leaves: m.published_leaves,
        item_count: (m.draft_count ?? 0) + (m.published_leaves ?? 0),
        mount_id: m.mount_id,
      }));
    }
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  dialogMode.value = "create";
  editingId.value = "";
  form.title = "";
  form.description = "";
  dialogVisible.value = true;
}

function openEdit(row: Row) {
  dialogMode.value = "edit";
  editingId.value = row.document_id;
  form.title = row.title || row.display_title || "";
  form.description = row.description || "";
  dialogVisible.value = true;
}

function resetForm() {
  form.title = "";
  form.description = "";
}

async function submitForm() {
  const title = form.title.trim();
  if (!title) {
    ElMessage.warning("请填写知识库名称");
    return;
  }
  saving.value = true;
  try {
    if (dialogMode.value === "create") {
      const lib = await createLibrary(title, form.description.trim());
      ElMessage.success(T.msgLibraryCreated);
      dialogVisible.value = false;
      await load();
      router.push({ name: "library-detail", params: { documentId: lib.document_id } });
    } else {
      await updateLibrary(editingId.value, {
        title,
        description: form.description.trim(),
      });
      ElMessage.success(T.msgLibraryUpdated);
      dialogVisible.value = false;
      await load();
    }
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  } finally {
    saving.value = false;
  }
}

function onDetail(row: Row) {
  router.push({ name: "library-detail", params: { documentId: row.document_id } });
}

async function onDelete(row: Row) {
  try {
    await ElMessageBox.confirm(T.confirmDeleteLibrary, "提示", { type: "warning" });
    await deleteLibrary(row.document_id);
    ElMessage.success(T.msgLibraryDeleted);
    await load();
  } catch (e: unknown) {
    if (e === "cancel" || e === "close") return;
    ElMessage.error(formatApiError(e));
  }
}

onMounted(load);
</script>

<style scoped>
.library-page {
  max-width: 1100px;
}
.toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}
.table-card {
  background: #fff;
}
.name {
  font-weight: 500;
}
.btn-icon {
  margin-right: 4px;
}
</style>