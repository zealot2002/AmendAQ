<template>
  <div class="log-full-page">
    <p class="hint">{{ T.logPageHint }}</p>
    <LogViewShell :autostart="true" />
  </div>
</template>

<script setup lang="ts">
import LogViewShell from "@/components/LogViewShell.vue";
import { T } from "@/constants/terminology";
</script>

<style scoped>
.log-full-page {
  height: calc(100vh - 56px - 32px);
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #fff;
  border-radius: 4px;
  padding: 12px;
  box-sizing: border-box;
}
.hint {
  margin: 0;
  font-size: 12px;
  color: #909399;
}
.log-full-page :deep(.log-shell) {
  flex: 1;
  min-height: 0;
}
</style>