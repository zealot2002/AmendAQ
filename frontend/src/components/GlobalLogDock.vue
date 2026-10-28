<template>
  <aside v-if="open" class="log-dock" :class="{ collapsed: dockCollapsed }">
    <div v-if="dockCollapsed" class="dock-rail" @click="dockCollapsed = false">
      <el-icon :size="18"><Document /></el-icon>
      <span class="rail-label">日志</span>
    </div>
    <div v-else class="dock-panel">
      <header class="dock-header">
        <span>运行日志</span>
        <div class="dock-actions">
          <el-button link type="primary" @click="$router.push('/logs')">全屏</el-button>
          <el-button link title="收起日志栏" @click="toggleDockCollapsed">
            <el-icon><DArrowRight /></el-icon>
          </el-button>
          <el-button link title="关闭" @click="hideLogDock">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </header>
      <LogsPanel class="dock-logs" compact :autostart="true" />
    </div>
  </aside>
</template>

<script setup lang="ts">
import LogsPanel from "@/components/LogsPanel.vue";
import { useLogDock } from "@/composables/useLogDock";

const { open, dockCollapsed, hideLogDock, toggleDockCollapsed } = useLogDock();
</script>

<style scoped>
.log-dock {
  flex-shrink: 0;
  height: 100vh;
  background: #fff;
  border-left: 1px solid #dcdfe6;
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.04);
  transition: width 0.2s ease;
  width: min(480px, 42vw);
  display: flex;
  flex-direction: column;
}
.log-dock.collapsed {
  width: 44px;
}
.dock-rail {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 16px;
  gap: 8px;
  cursor: pointer;
  color: #606266;
  background: #f5f7fa;
}
.dock-rail:hover {
  color: #409eff;
}
.rail-label {
  writing-mode: vertical-rl;
  font-size: 12px;
  letter-spacing: 2px;
}
.dock-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}
.dock-header {
  height: 48px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #ebeef5;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}
.dock-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.dock-logs {
  flex: 1;
  min-height: 0;
  padding: 8px 10px 10px;
  box-sizing: border-box;
}
</style>
