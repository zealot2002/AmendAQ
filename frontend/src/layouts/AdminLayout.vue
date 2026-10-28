<template>
  <el-container class="admin-root">
    <el-aside width="220px" class="admin-aside">
      <div class="logo">
        <span class="logo-mark">M</span>
        <span class="logo-text">mycs 知识库</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
      >
        <el-menu-item index="/workflow">
          <el-icon><Operation /></el-icon>
          <span>{{ T.navWorkflow }}</span>
        </el-menu-item>
        <el-menu-item index="/wiki">
          <el-icon><FolderOpened /></el-icon>
          <span>{{ T.navReview }}</span>
        </el-menu-item>
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>{{ T.navChat }}</span>
        </el-menu-item>
        <el-menu-item index="/mounts">
          <el-icon><Collection /></el-icon>
          <span>{{ T.navLibrary }}</span>
        </el-menu-item>
        <el-menu-item index="/logs">
          <el-icon><Document /></el-icon>
          <span>运行日志</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container class="admin-body">
      <el-header class="admin-header">
        <div class="header-left">
          <span class="page-title">{{ pageTitle }}</span>
        </div>
        <div class="header-right">
          <el-button :type="open ? 'primary' : 'default'" plain @click="onLogButton">
            <el-icon><Document /></el-icon>
            日志
          </el-button>
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
      <el-main class="admin-main" :class="{ 'admin-main--chat': isChatRoute }">
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
import { useDocumentId } from "@/composables/useDocumentId";
import { useLogDock } from "@/composables/useLogDock";

const route = useRoute();
const { documentId, documentTitle, refreshFromServer } = useDocumentId();
const { open, showLogDock } = useLogDock();

const activeMenu = computed(() => route.path);
const pageTitle = computed(() => (route.meta.title as string) || "mycs");
const isChatRoute = computed(() => route.path === "/chat" || route.path.startsWith("/chat/"));

function onLogButton() {
  showLogDock();
}

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
.page-title {
  font-size: 16px;
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
