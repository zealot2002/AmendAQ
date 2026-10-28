import { onUnmounted, ref, shallowRef } from "vue";
import { clearLogs, fetchLogs, type LogItem } from "@/api/client";

export function useLogs(options?: { pollMs?: number; live?: boolean }) {
  const items = shallowRef<LogItem[]>([]);
  const latestId = ref(0);
  const loading = ref(false);
  const paused = ref(false);
  const level = ref("");
  const keyword = ref("");
  const autoScroll = ref(true);

  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let es: EventSource | null = null;

  function mergeIncoming(batch: LogItem[]) {
    if (!batch.length) return;
    const map = new Map<number, LogItem>();
    for (const x of items.value) map.set(x.id, x);
    for (const x of batch) map.set(x.id, x);
    const merged = [...map.values()].sort((a, b) => a.id - b.id);
    const maxKeep = 1500;
    items.value = merged.length > maxKeep ? merged.slice(-maxKeep) : merged;
    latestId.value = Math.max(latestId.value, ...batch.map((x) => x.id));
  }

  async function refreshTail() {
    loading.value = true;
    try {
      const data = await fetchLogs({
        tail: true,
        limit: 400,
        level: level.value || undefined,
        q: keyword.value || undefined,
      });
      items.value = data.items;
      latestId.value = data.latest_id;
    } finally {
      loading.value = false;
    }
  }

  async function pollOnce() {
    if (paused.value) return;
    const data = await fetchLogs({
      after_id: latestId.value,
      limit: 300,
      level: level.value || undefined,
      q: keyword.value || undefined,
    });
    mergeIncoming(data.items);
  }

  function startLive() {
    stopLive();
    es = new EventSource(`/api/logs/stream?after_id=${latestId.value}`);
    es.onmessage = (ev) => {
      if (paused.value) return;
      try {
        const row = JSON.parse(ev.data) as LogItem;
        mergeIncoming([row]);
      } catch {
        /* ignore */
      }
    };
    es.onerror = () => {
      es?.close();
      es = null;
      if (!pollTimer) {
        pollTimer = setInterval(() => pollOnce().catch(() => undefined), options?.pollMs ?? 2500);
      }
    };
  }

  function stopLive() {
    es?.close();
    es = null;
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function start() {
    await refreshTail();
    if (options?.live !== false) startLive();
    else {
      pollTimer = setInterval(() => pollOnce().catch(() => undefined), options?.pollMs ?? 2500);
    }
  }

  async function onClear() {
    await clearLogs();
    items.value = [];
    latestId.value = 0;
  }

  function stop() {
    stopLive();
  }

  onUnmounted(stop);

  return {
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
  };
}
