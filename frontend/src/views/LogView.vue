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
  border: 1px solid #e7ebf0;
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 24px rgba(15, 23, 42, 0.06);
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