import { ref, watch } from "vue";

const OPEN_KEY = "mycs_log_dock_open";
const DOCK_COLLAPSED_KEY = "mycs_log_dock_collapsed";
const SIDEBAR_COLLAPSED_KEY = "mycs_log_sidebar_collapsed";

const open = ref(localStorage.getItem(OPEN_KEY) === "1");
const dockCollapsed = ref(localStorage.getItem(DOCK_COLLAPSED_KEY) === "1");
const sidebarCollapsed = ref(
  localStorage.getItem(SIDEBAR_COLLAPSED_KEY) !== "0",
); /* 默认收起筛选，给日志列表留宽度 */

watch(open, (v) => localStorage.setItem(OPEN_KEY, v ? "1" : "0"));
watch(dockCollapsed, (v) => localStorage.setItem(DOCK_COLLAPSED_KEY, v ? "1" : "0"));
watch(sidebarCollapsed, (v) => localStorage.setItem(SIDEBAR_COLLAPSED_KEY, v ? "1" : "0"));

export function useLogDock() {
  function showLogDock() {
    open.value = true;
    dockCollapsed.value = false;
  }

  function hideLogDock() {
    open.value = false;
  }

  function toggleDockCollapsed() {
    dockCollapsed.value = !dockCollapsed.value;
  }

  function toggleSidebarCollapsed() {
    sidebarCollapsed.value = !sidebarCollapsed.value;
  }

  return {
    open,
    dockCollapsed,
    sidebarCollapsed,
    showLogDock,
    hideLogDock,
    toggleDockCollapsed,
    toggleSidebarCollapsed,
  };
}
