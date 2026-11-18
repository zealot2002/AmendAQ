<template>
  <el-container class="admin-root">
    <el-aside width="200px" class="admin-aside">
      <div class="logo">
        <span class="logo-mark">M</span>
        <span class="logo-text">客服知识库</span>
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
        <el-menu-item index="/logs">
          <el-icon><Document /></el-icon>
          <span>{{ T.navLogs }}</span>
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
              {{ item.label }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div v-if="showHandbookContext" class="header-right">
          <span class="label">{{ T.currentHandbook }}</span>
          <el-tooltip
            v-if="documentId"
            :content="documentTitle && documentTitle !== documentId ? `${documentTitle}（${T.docCode}：${documentId}）` : `${T.docCode}：${documentId}`"
            placement="bottom"
          >
            <el-tag type="success" effect="plain" class="handbook-tag">
              {{ documentTitle || documentId }}
            </el-tag>
          </el-tooltip>
          <el-tag v-else type="info" effect="plain">{{ T.docCodeHint }}</el-tag>
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
import { computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import GlobalLogDock from "@/components/GlobalLogDock.vue";
import { T } from "@/constants/terminology";
import { useAppBreadcrumbs } from "@/composables/useAppBreadcrumbs";
import { useDocumentId } from "@/composables/useDocumentId";

const route = useRoute();
const { documentId, documentTitle, refreshFromServer } = useDocumentId();
const { breadcrumbs } = useAppBreadcrumbs();

const activeMenu = computed(() => (route.meta.menu as string) || route.path);
const isChatRoute = computed(() => route.path === "/chat" || route.path.startsWith("/chat/"));
const isFullHeightRoute = computed(() => Boolean(route.meta.fullHeight));
const showHandbookContext = computed(() => route.path === "/chat");

onMounted(() => {
  refreshFromServer();
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
.app-breadcrumb :deep(.el-breadcrumb__inner) {
  font-weight: 500;
  color: #606266;
}
.app-breadcrumb :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
  font-weight: 600;
  color: #303133;
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
.handbook-tag {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
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