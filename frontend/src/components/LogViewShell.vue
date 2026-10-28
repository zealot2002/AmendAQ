<template>
  <div class="log-shell" :class="{ 'aside-collapsed': sidebarCollapsed }">
    <aside class="log-aside">
      <div class="aside-head">
        <span v-show="!sidebarCollapsed" class="aside-title">筛选</span>
        <el-button text class="aside-fold" @click="toggleSidebarCollapsed">
          <el-icon :size="16">
            <Expand v-if="sidebarCollapsed" />
            <Fold v-else />
          </el-icon>
        </el-button>
      </div>
      <div v-show="!sidebarCollapsed" class="aside-body">
        <div class="block">
          <div class="block-label">级别</div>
          <el-radio-group v-model="level" size="small">
            <el-radio-button label="">全部</el-radio-button>
            <el-radio-button label="INFO">INFO</el-radio-button>
            <el-radio-button label="WARNING">WARN</el-radio-button>
            <el-radio-button label="ERROR">ERROR</el-radio-button>
          </el-radio-group>
        </div>
        <div class="block">
          <div class="block-label">模块</div>
          <el-menu
            :default-active="loggerPrefix"
            class="module-menu"
            @select="onModuleSelect"
          >
            <el-menu-item index="">全部</el-menu-item>
            <el-menu-item index="mycs.api">接口服务</el-menu-item>
            <el-menu-item index="mycs.agent">问答编排</el-menu-item>
            <el-menu-item index="mycs.llm">大模型</el-menu-item>
            <el-menu-item index="mycs.graph">知识点</el-menu-item>
            <el-menu-item index="mycs.wiki">知识目录</el-menu-item>
            <el-menu-item index="mycs.knowledge">检索</el-menu-item>
          </el-menu>
        </div>
        <div class="block hint">
          记录本次服务运行过程，便于技术支持排查
        </div>
        <div v-if="pathEntries.length" class="block paths">
          <div class="block-label">文件存放位置</div>
          <div v-for="[k, v] in pathEntries" :key="k" class="path-row">
            <span class="path-key">{{ k }}</span>
            <span class="path-val" :title="v">{{ v }}</span>
          </div>
        </div>
      </div>
      <div v-show="sidebarCollapsed" class="aside-rail" @click="toggleSidebarCollapsed">
        <span class="rail-text">筛选</span>
      </div>
    </aside>
    <main class="log-main">
      <LogsPanel
        ref="panelRef"
        sidebar-mode
        :level="level"
        :logger-prefix="loggerPrefix"
        :autostart="autostart"
        compact
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { fetchContext } from "@/api/client";
import LogsPanel from "@/components/LogsPanel.vue";
import { useLogDock } from "@/composables/useLogDock";

withDefaults(
  defineProps<{
    autostart?: boolean;
  }>(),
  { autostart: true },
);

const { sidebarCollapsed, toggleSidebarCollapsed } = useLogDock();
const level = ref("");
const loggerPrefix = ref("");
const panelRef = ref<InstanceType<typeof LogsPanel> | null>(null);
const runtimePaths = ref<Record<string, string>>({});

const pathEntries = computed(() => Object.entries(runtimePaths.value));

onMounted(async () => {
  try {
    const ctx = await fetchContext();
    runtimePaths.value = ctx.paths || {};
  } catch {
    /* ignore */
  }
});

function onModuleSelect(index: string) {
  loggerPrefix.value = index;
}

defineExpose({
  reload: () => panelRef.value?.reload(),
});
</script>

<style scoped>
.log-shell {
  display: flex;
  height: 100%;
  min-height: 0;
  background: #fff;
  border-radius: 4px;
  overflow: hidden;
}
.log-aside {
  width: 200px;
  flex-shrink: 0;
  border-right: 1px solid #ebeef5;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
}
.log-shell.aside-collapsed .log-aside {
  width: 44px;
}
.aside-head {
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 8px 0 12px;
  border-bottom: 1px solid #ebeef5;
}
.aside-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}
.aside-fold {
  color: #606266;
}
.aside-body {
  padding: 12px;
  overflow-y: auto;
  flex: 1;
}
.block {
  margin-bottom: 16px;
}
.block-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}
.module-menu {
  border-right: none;
  background: transparent;
}
.module-menu :deep(.el-menu-item) {
  height: 36px;
  line-height: 36px;
  font-size: 13px;
}
.hint {
  font-size: 11px;
  color: #909399;
  line-height: 1.5;
}
.hint code {
  background: #f0f2f5;
  padding: 0 4px;
  border-radius: 2px;
}
.paths {
  font-size: 11px;
}
.path-row {
  display: flex;
  flex-direction: column;
  margin-bottom: 6px;
}
.path-key {
  color: #909399;
}
.path-val {
  word-break: break-all;
  color: #606266;
  font-family: ui-monospace, Menlo, monospace;
}
.aside-rail {
  flex: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  writing-mode: vertical-rl;
  letter-spacing: 4px;
  font-size: 12px;
  user-select: none;
}
.aside-rail:hover {
  color: #409eff;
  background: rgba(64, 158, 255, 0.06);
}
.log-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  padding: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
