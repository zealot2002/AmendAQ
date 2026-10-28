<template>
  <el-card shadow="never" class="log-page">
    <template #header>
      <span>运行日志</span>
      <span class="sub">供管理员排查问题；日常使用时无需关注</span>
    </template>
    <LogViewShell />
  </el-card>
</template>

<script setup lang="ts">
import LogViewShell from "@/components/LogViewShell.vue";
</script>

<style scoped>
.log-page {
  min-height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
}
.log-page :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 0;
  overflow: hidden;
}
.sub {
  margin-left: 12px;
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}
</style>
