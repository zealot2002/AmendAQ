<template>
  <el-container class="admin-root">
    <el-aside width="200px" class="admin-aside">
      <div class="logo">
        <span class="logo-mark">M</span>
        <span class="logo-text">ai客服</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
      >
        <el-menu-item index="/library">
          <el-icon><Collection /></el-icon>
          <span>{{ T.navLibraryMgmt }}</span>
        </el-menu-item>
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>{{ T.navChat }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container class="admin-body">
      <el-header class="admin-header">
        <div class="header-left">
          <el-breadcrumb separator="/" class="app-breadcrumb">
            <el-breadcrumb-item
              v-for="(item, index) in breadcrumbs"
              :key="index"
              :to="index < breadcrumbs.length - 1 ? item.to : undefined"
            >
              <span
                class="crumb-label"
                :class="{ 'crumb-label--back': index < breadcrumbs.length - 1 && item.to }"
              >
                <el-icon v-if="index === 0 && breadcrumbs.length > 1 && item.to" class="crumb-back-icon">
                  <ArrowLeft />
                </el-icon>
                {{ item.label }}
              </span>
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div v-if="showHandbookContext" class="header-right">
          <span class="label">{{ T.chatKbLabel }}</span>
          <el-select
            v-model="chatDocId"
            class="chat-kb-select"
            filterable
            :placeholder="T.chatKbPlaceholder"
            :loading="mountsLoading"
            @change="onChatKbChange"
          >
            <el-option
              v-for="m in chatMounts"
              :key="m.document_id"
              :label="mountOptionLabel(m)"
              :value="m.document_id"
              :disabled="(m.published_leaves ?? 0) === 0"
            >
              <span>{{ mountOptionLabel(m) }}</span>
              <span v-if="(m.published_leaves ?? 0) === 0" class="opt-muted">
                · {{ T.chatKbNotPublished }}
              </span>
            </el-option>
          </el-select>
        </div>
      </el-header>
      <el-main
        class="admin-main"
        :class="{
          'admin-main--chat': isChatRoute,
          'admin-main--fill': isFullHeightRoute && !isChatRoute,
        }"
      >
        <router-view />
      </el-main>
    </el-container>

    <GlobalLogDock />
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import GlobalLogDock from "@/components/GlobalLogDock.vue";
import { T } from "@/constants/terminology";
import { useAppBreadcrumbs } from "@/composables/useAppBreadcrumbs";
import { useDocumentId } from "@/composables/useDocumentId";
import { fetchMounts, setActiveDocument, type Mount } from "@/api/client";
import { formatApiError } from "@/api/httpError";

const route = useRoute();
const { documentId, documentTitle, setDocumentId, refreshFromServer } = useDocumentId();
const { breadcrumbs } = useAppBreadcrumbs();

const activeMenu = computed(() => (route.meta.menu as string) || route.path);
const isChatRoute = computed(() => route.path === "/chat" || route.path.startsWith("/chat/"));
const isFullHeightRoute = computed(() => Boolean(route.meta.fullHeight));
const showHandbookContext = computed(() => route.path === "/chat");

const chatDocId = ref("");
const chatMounts = ref<Mount[]>([]);
const mountsLoading = ref(false);

function mountOptionLabel(m: Mount) {
  const name = (m.display_title || m.document_id || "").trim();
  const pub = m.published_leaves ?? 0;
  return pub > 0 ? `${name}（${pub} 条）` : name;
}

async function loadChatMounts() {
  mountsLoading.value = true;
  try {
    const data = await fetchMounts();
    chatMounts.value = (data.mounts || []).slice().sort((a, b) => {
      const ap = a.published_leaves ?? 0;
      const bp = b.published_leaves ?? 0;
      if (ap !== bp) return bp - ap;
      return String(a.display_title || a.document_id).localeCompare(
        String(b.display_title || b.document_id),
        "zh-CN",
      );
    });
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
  } finally {
    mountsLoading.value = false;
  }
}

async function onChatKbChange(id: string) {
  if (!id) return;
  try {
    const res = await setActiveDocument(id);
    setDocumentId(id, res.document_title);
    if (!res.qa_ready) {
      ElMessage.warning(T.chatKbNotPublished);
      return;
    }
    ElMessage.success(`${T.chatKbSwitched}：${res.document_title || id}`);
  } catch (e: unknown) {
    ElMessage.error(formatApiError(e));
    chatDocId.value = documentId.value;
  }
}

watch(
  () => documentId.value,
  (v) => {
    if (v && chatDocId.value !== v) {
      chatDocId.value = v;
    }
  },
  { immediate: true },
);

watch(isChatRoute, (on) => {
  if (on) {
    void loadChatMounts();
    chatDocId.value = documentId.value;
  }
});

onMounted(() => {
  void refreshFromServer().then(() => {
    chatDocId.value = documentId.value;
    if (isChatRoute.value) {
      void loadChatMounts();
    }
  });
});
</script>

<style scoped>
.admin-root {
  min-height: 100vh;
}
.admin-aside {
  background: #304156;
  color: #fff;
}
.admin-aside :deep(.el-menu) {
  border-right: none;
}
.logo {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.logo-mark {
  width: 28px;
  height: 28px;
  border-radius: 4px;
  background: #409eff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-right: 10px;
  font-size: 14px;
}
.admin-body {
  min-width: 0;
  flex: 1;
}
.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e6e6e6;
  height: 56px;
  padding: 0 20px;
}
.app-breadcrumb {
  font-size: 14px;
  line-height: 1;
}
.crumb-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.crumb-back-icon {
  font-size: 14px;
}
.app-breadcrumb :deep(.el-breadcrumb__inner) {
  font-weight: 500;
  color: #606266;
}
.app-breadcrumb :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
  font-weight: 600;
  color: #303133;
  cursor: default;
}
.app-breadcrumb :deep(.el-breadcrumb__inner.is-link) {
  font-weight: 500;
}
.app-breadcrumb :deep(.crumb-label--back) {
  color: #409eff;
  transition: color 0.15s ease;
}
.app-breadcrumb :deep(.el-breadcrumb__inner.is-link:hover .crumb-label--back),
.app-breadcrumb :deep(.el-breadcrumb__inner.is-link:focus .crumb-label--back) {
  color: #337ecc;
}
.app-breadcrumb :deep(.el-breadcrumb__separator) {
  color: #c0c4cc;
  margin: 0 6px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.header-right .label {
  font-size: 13px;
  color: #909399;
}
.chat-kb-select {
  width: min(360px, 42vw);
}
.opt-muted {
  margin-left: 6px;
  font-size: 12px;
  color: #909399;
}
.admin-main {
  background: #f0f2f5;
  min-height: calc(100vh - 56px);
}
.admin-main--chat {
  overflow: hidden;
  height: calc(100vh - 56px);
  min-height: 0;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}
.admin-main--chat > :deep(*) {
  flex: 1;
  min-height: 0;
}
.admin-main--fill {
  overflow: hidden;
  height: calc(100vh - 56px);
  min-height: 0;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}
.admin-main--fill > :deep(*) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
</style>

<style>
html,
body,
#app {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: "Helvetica Neue", Helvetica, "PingFang SC", "Microsoft YaHei", sans-serif;
}
</style>