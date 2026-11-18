<template>
  <Teleport to="body">
    <transition name="log-backdrop-fade">
      <div v-if="open" class="log-backdrop" aria-hidden="true" @click="hideLogDock" />
    </transition>

    <button
      type="button"
      class="log-fab"
      :class="{ 'log-fab--active': open }"
      :title="open ? '关闭日志' : T.navLogs"
      aria-label="运行日志"
      @click="toggleLogDock"
    >
      <el-icon :size="22"><Document /></el-icon>
      <span class="log-fab-label">{{ T.navLogs }}</span>
    </button>

    <aside class="log-drawer" :class="{ 'log-drawer--open': open }" role="dialog" aria-label="运行日志">
      <header class="drawer-header">
        <span class="drawer-title">{{ T.navLogs }}</span>
        <div class="drawer-actions">
          <el-button link type="primary" @click="goFullPage">全屏</el-button>
          <el-button link title="关闭" @click="hideLogDock">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </header>
      <div class="drawer-body">
        <LogViewShell v-if="open" :autostart="true" />
      </div>
    </aside>
  </Teleport>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";
import LogViewShell from "@/components/LogViewShell.vue";
import { T } from "@/constants/terminology";
import { useLogDock } from "@/composables/useLogDock";

const { open, toggleLogDock, hideLogDock } = useLogDock();
const router = useRouter();
const route = useRoute();

function goFullPage() {
  hideLogDock();
  if (route.path !== "/logs") {
    router.push({ name: "logs" });
  }
}
</script>

<style scoped>
.log-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1990;
  background: rgba(0, 0, 0, 0.35);
}
.log-backdrop-fade-enter-active,
.log-backdrop-fade-leave-active {
  transition: opacity 0.2s ease;
}
.log-backdrop-fade-enter-from,
.log-backdrop-fade-leave-to {
  opacity: 0;
}

.log-fab {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 2001;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  width: 56px;
  height: 56px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.45);
  transition: transform 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}
.log-fab:hover {
  transform: scale(1.05);
  box-shadow: 0 6px 20px rgba(64, 158, 255, 0.5);
}
.log-fab--active {
  background: #303133;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
}
.log-fab-label {
  font-size: 10px;
  line-height: 1;
  font-weight: 600;
}

.log-drawer {
  position: fixed;
  top: 0;
  right: 0;
  z-index: 2000;
  width: min(720px, 92vw);
  height: 100vh;
  background: #fff;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  transform: translateX(100%);
  transition: transform 0.25s ease;
  pointer-events: none;
}
.log-drawer--open {
  transform: translateX(0);
  pointer-events: auto;
}

.drawer-header {
  height: 52px;
  flex-shrink: 0;
  padding: 0 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #ebeef5;
  background: #fafafa;
}
.drawer-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}
.drawer-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.drawer-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.drawer-body :deep(.log-shell) {
  height: 100%;
  border-radius: 0;
}
</style>