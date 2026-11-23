import { ref, watch } from "vue";

const OPEN_KEY = "amendaq_log_dock_open";
const SIDEBAR_COLLAPSED_KEY = "amendaq_log_sidebar_collapsed";

const open = ref(localStorage.getItem(OPEN_KEY) === "1");
const sidebarCollapsed = ref(localStorage.getItem(SIDEBAR_COLLAPSED_KEY) !== "0");

watch(open, (v) => localStorage.setItem(OPEN_KEY, v ? "1" : "0"));
watch(sidebarCollapsed, (v) => localStorage.setItem(SIDEBAR_COLLAPSED_KEY, v ? "1" : "0"));

export function useLogDock() {
  function showLogDock() {
    open.value = true;
  }

  function hideLogDock() {
    open.value = false;
  }

  function toggleLogDock() {
    open.value = !open.value;
  }

  function toggleSidebarCollapsed() {
    sidebarCollapsed.value = !sidebarCollapsed.value;
  }

  return {
    open,
    sidebarCollapsed,
    showLogDock,
    hideLogDock,
    toggleLogDock,
    toggleSidebarCollapsed,
  };
}