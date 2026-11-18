<template>
  <div class="library-page">
    <div class="toolbar">
      <el-button type="primary" @click="onAdd">
        <el-icon class="btn-icon"><Plus /></el-icon>
        {{ T.btnAddLibrary }}
      </el-button>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="mounts" border stripe v-loading="loading" empty-text=" ">
        <el-table-column prop="display_title" :label="T.colLibraryName" min-width="200">
          <template #default="{ row }">
            <span class="name">{{ row.display_title || row.document_id }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="T.colStatus" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="statusOf(row).type">{{ statusOf(row).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="draft_count" :label="T.colPendingSections" width="110" align="center" />
        <el-table-column prop="published_leaves" :label="T.colLiveEntries" width="100" align="center" />
        <el-table-column :label="T.colActions" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              v-if="needsIngest(row)"
              link
              type="primary"
              @click="onIngest(row)"
            >
              {{ T.btnContinueIngest }}
            </el-button>
            <template v-else>
              <el-button link type="primary" @click="onEdit(row)">{{ T.btnEdit }}</el-button>
              <el-button link type="primary" @click="onReview(row)">{{ T.btnReview }}</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !mounts.length" :description="T.libraryEmpty">
        <el-button type="primary" @click="onAdd">{{ T.btnAddLibrary }}</el-button>
      </el-empty>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Plus } from "@element-plus/icons-vue";
import { T } from "@/constants/terminology";
import { fetchMounts, type Mount } from "@/api/client";
import { formatApiError } from "@/api/httpError";
import { useDocumentId } from "@/composables/useDocumentId";

const mounts = ref<Mount[]>([]);
const loading = ref(false);
const router = useRouter();
const { setDocumentId, clearDocumentId } = useDocumentId();

function statusOf(row: Mount) {
  const pub = row.published_leaves ?? 0;
  const draft = row.draft_count ?? 0;
  if (pub > 0) return { label: T.statusLive, type: "success" as const };
  if (draft > 0) return { label: T.statusDraft, type: "warning" as const };
  return { label: T.statusPendingIngest, type: "info" as const };
}

function needsIngest(row: Mount) {
  return (row.draft_count ?? 0) === 0 && (row.published_leaves ?? 0) === 0;
}

async function load() {
  loading.value = true;
  try {
    const data = await fetchMounts();
    mounts.value = data.mounts || [];
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
}

function onAdd() {
  clearDocumentId();
  router.push({ name: "library-new" });
}

function onIngest(row: Mount) {
  setDocumentId(row.document_id, row.display_title);
  router.push({ name: "library-ingest", params: { documentId: row.document_id } });
}

function onEdit(row: Mount) {
  setDocumentId(row.document_id, row.display_title);
  router.push({ name: "library-edit", params: { documentId: row.document_id } });
}

function onReview(row: Mount) {
  setDocumentId(row.document_id, row.display_title);
  router.push({ name: "library-review", params: { documentId: row.document_id } });
}

onMounted(load);
</script>

<style scoped>
.library-page {
  max-width: 1000px;
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