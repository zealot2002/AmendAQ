<template>
  <el-container class="admin-root">
    <el-aside width="220px" class="admin-aside">
      <div class="logo">
        <span class="logo-mark" aria-hidden="true">
          <span class="logo-letter">M</span>
          <span class="logo-sheen"></span>
        </span>
        <span class="logo-copy">
          <span class="logo-text">ai客服</span>
          <span class="logo-sub">知识问答</span>
        </span>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="transparent"
        text-color="#c5d0dc"
        active-text-color="#ffffff"
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
  position: relative;
  overflow: hidden;
  color: #fff;
  background:
    radial-gradient(140px 90px at 18% 0%, rgba(94, 184, 255, 0.34), transparent 72%),
    linear-gradient(180deg, #172230 0%, #1e2c3c 46%, #141c27 100%);
  box-shadow: inset -1px 0 0 rgba(150, 200, 255, 0.12);
}
.admin-aside::before {
  content: "";
  position: absolute;
  inset: -40% -20% auto;
  height: 220px;
  background: radial-gradient(circle, rgba(120, 196, 255, 0.18), transparent 68%);
  animation: aside-glow 7s ease-in-out infinite;
  pointer-events: none;
}
.admin-aside :deep(.el-menu) {
  position: relative;
  border-right: none;
  padding-top: 8px;
  background: transparent;
}
.admin-aside :deep(.el-menu-item) {
  height: 44px;
  margin: 4px 12px;
  border-radius: 12px;
  color: #c5d0dc;
  transition: background-color 0.22s ease, color 0.22s ease, transform 0.22s ease, box-shadow 0.22s ease;
}
.admin-aside :deep(.el-menu-item .el-icon) {
  transition: transform 0.22s ease, color 0.22s ease;
}
.admin-aside :deep(.el-menu-item:hover) {
  background-color: rgba(255, 255, 255, 0.06) !important;
  color: #fff !important;
}
.admin-aside :deep(.el-menu-item:hover .el-icon) {
  transform: translateX(3px);
}
.admin-aside :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(79, 163, 255, 0.42), rgba(79, 163, 255, 0.12)) !important;
  color: #fff !important;
  box-shadow: inset 0 0 0 1px rgba(160, 214, 255, 0.38), 0 8px 18px rgba(20, 40, 70, 0.28);
}
.admin-aside :deep(.el-menu-item.is-active .el-icon) {
  color: #d7ecff;
  animation: icon-in 0.45s ease;
}
.logo {
  position: relative;
  height: 72px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  color: #fff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.logo-mark {
  position: relative;
  width: 36px;
  height: 36px;
  border-radius: 11px;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #9ad4ff 0%, #3b8ef0 48%, #1d5fbe 100%);
  box-shadow:
    0 10px 22px rgba(47, 132, 232, 0.45),
    inset 0 1px 0 rgba(255, 255, 255, 0.55);
  animation: logo-float 4.8s ease-in-out infinite;
}
.logo-letter {
  position: relative;
  z-index: 1;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.04em;
}
.logo-sheen {
  position: absolute;
  inset: -40%;
  background: linear-gradient(110deg, transparent 36%, rgba(255, 255, 255, 0.72) 50%, transparent 64%);
  transform: translateX(-70%);
  animation: logo-sheen 3.8s ease-in-out infinite;
}
.logo-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.logo-text {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.04em;
  line-height: 1.15;
}
.logo-sub {
  margin-top: 2px;
  font-size: 11px;
  letter-spacing: 0.18em;
  color: rgba(206, 224, 242, 0.72);
}
@keyframes logo-sheen {
  0%,
  58% {
    transform: translateX(-70%);
  }
  82%,
  100% {
    transform: translateX(70%);
  }
}
@keyframes logo-float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-2px);
  }
}
@keyframes aside-glow {
  0%,
  100% {
    transform: translate3d(0, 0, 0);
    opacity: 0.7;
  }
  50% {
    transform: translate3d(12px, 18px, 0);
    opacity: 1;
  }
}
@keyframes icon-in {
  0% {
    transform: scale(0.82);
  }
  70% {
    transform: scale(1.08);
  }
  100% {
    transform: scale(1);
  }
}
@media (prefers-reduced-motion: reduce) {
  .admin-aside::before,
  .logo-mark,
  .logo-sheen,
  .admin-aside :deep(.el-menu-item.is-active .el-icon) {
    animation: none;
  }
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
  background: #f4f6f8;
  min-height: calc(100vh - 56px);
  padding: 16px 20px;
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