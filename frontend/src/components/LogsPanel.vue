<template>
  <div class="logs-panel" :class="{ compact }">
    <div class="toolbar">
      <el-select
        v-if="!sidebarMode && !compact"
        v-model="level"
        placeholder="级别"
        clearable
        style="width: 110px"
        @change="reload"
      >
        <el-option label="DEBUG" value="DEBUG" />
        <el-option label="INFO" value="INFO" />
        <el-option label="WARNING" value="WARNING" />
        <el-option label="ERROR" value="ERROR" />
      </el-select>
      <el-input
        v-model="keyword"
        placeholder="搜索内容"
        clearable
        class="search-input"
        @change="reload"
      />
      <el-button size="small" :loading="loading" @click="reload">刷新</el-button>
      <el-button size="small" @click="paused = !paused">{{ paused ? "继续" : "暂停" }}</el-button>
      <el-checkbox v-model="autoScroll" class="scroll-check">滚到底</el-checkbox>
      <el-button size="small" type="danger" plain @click="confirmClear">清空</el-button>
      <span class="hint">{{ visibleItems.length }} 条</span>
    </div>
    <div ref="listRef" class="log-list" v-loading="loading">
      <div
        v-for="row in visibleItems"
        :key="row.id"
        class="log-line"
        :class="levelClass(row.level)"
        :title="row.line"
      >
        {{ row.line }}
      </div>
      <el-empty v-if="!visibleItems.length && !loading" :description="T.logEmpty" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { T } from "@/constants/terminology";
import { useLogs } from "@/composables/useLogs";

const props = withDefaults(
  defineProps<{
    autostart?: boolean;
    sidebarMode?: boolean;
    compact?: boolean;
    level?: string;
    loggerPrefix?: string;
  }>(),
  {
    autostart: true,
    sidebarMode: false,
    compact: false,
    level: "",
    loggerPrefix: "",
  },
);

const listRef = ref<HTMLElement | null>(null);
const {
  items,
  latestId,
  loading,
  paused,
  level,
  keyword,
  autoScroll,
  start,
  stop,
  refreshTail,
  onClear,
} = useLogs({ live: true });

watch(
  () => props.level,
  (v) => {
    level.value = v || "";
  },
  { immediate: true },
);

const visibleItems = computed(() => {
  const lv = (props.sidebarMode ? props.level : level.value).toUpperCase();
  const prefix = props.loggerPrefix || "";
  const needle = keyword.value.trim().toLowerCase();
  return items.value.filter((row) => {
    if (lv && row.level !== lv) return false;
    if (prefix && !row.logger.startsWith(prefix)) return false;
    if (needle && !row.line.toLowerCase().includes(needle) && !row.message.toLowerCase().includes(needle)) {
      return false;
    }
    return true;
  });
});

function levelClass(lv: string) {
  return lv.toLowerCase();
}

async function reload() {
  await refreshTail();
}

async function confirmClear() {
  await ElMessageBox.confirm("清空当前页面上的运行记录？（不影响已保存的文件）", "确认", { type: "warning" });
  await onClear();
  ElMessage.success("已清空");
}

watch(
  () => visibleItems.value.length,
  async () => {
    if (!autoScroll.value || paused.value) return;
    await nextTick();
    const el = listRef.value;
    if (el) el.scrollTop = el.scrollHeight;
  },
);

watch([() => props.level, () => props.loggerPrefix], () => reload());

onMounted(async () => {
  if (props.autostart) await start();
});

onUnmounted(stop);

defineExpose({ reload, start, stop });
</script>

<style scoped>
.logs-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}
.logs-panel.compact .toolbar {
  gap: 6px;
}
.logs-panel.compact .search-input {
  flex: 1;
  min-width: 100px;
  max-width: 160px;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-shrink: 0;
}
.search-input {
  width: 200px;
}
.scroll-check {
  margin-right: 0;
}
.hint {
  font-size: 12px;
  color: #909399;
  margin-left: auto;
}
.log-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: #1e1e1e;
  color: #d4d4d4;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  line-height: 1.4;
  border-radius: 4px;
  padding: 4px 0;
  border: 1px solid #303133;
}
.log-line {
  padding: 2px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  word-break: break-word;
  white-space: pre-wrap;
}
.log-line:hover {
  background: rgba(255, 255, 255, 0.06);
}
.log-line.info {
  color: #d4d4d4;
}
.log-line.warning {
  color: #cca700;
}
.log-line.error,
.log-line.critical {
  color: #f48771;
}
</style>
