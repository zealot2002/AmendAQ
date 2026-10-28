<template>
  <el-card shadow="never">
    <template #header>
      <span>{{ T.navLibrary }}</span>
      <el-button link type="primary" @click="load">刷新</el-button>
    </template>
    <p class="intro">这里列出您已上传并整理过的手册。点击手册名称，可切换为顶栏「当前手册」。</p>
    <el-table :data="mounts" border stripe v-loading="loading">
      <el-table-column prop="display_title" label="手册名称" min-width="220">
        <template #default="{ row }">
          <el-link type="primary" @click="pickDoc(row)">
            {{ row.display_title || row.document_id }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column prop="document_id" :label="T.docCode" min-width="160" show-overflow-tooltip />
      <el-table-column prop="draft_count" :label="T.colPendingSections" width="140" align="center" />
      <el-table-column prop="published_leaves" :label="T.colLiveEntries" width="130" align="center" />
    </el-table>
    <el-empty v-if="!loading && !mounts.length" :description="T.libraryEmpty" />
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { T } from "@/constants/terminology";
import { fetchMounts, type Mount } from "@/api/client";
import { useDocumentId } from "@/composables/useDocumentId";

const mounts = ref<Mount[]>([]);
const loading = ref(false);
const { setDocumentId } = useDocumentId();
const router = useRouter();

async function load() {
  loading.value = true;
  try {
    const data = await fetchMounts();
    mounts.value = data.mounts || [];
  } catch (e: unknown) {
    ElMessage.error(String(e));
  } finally {
    loading.value = false;
  }
}

function pickDoc(row: Mount) {
  setDocumentId(row.document_id, row.display_title);
  router.push("/workflow");
}

onMounted(load);
</script>

<style scoped>
.intro {
  font-size: 13px;
  color: #606266;
  margin: 0 0 12px;
  line-height: 1.5;
}
</style>
