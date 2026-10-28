import axios from "axios";

const http = axios.create({
  baseURL: "/api",
  timeout: 120_000,
});

export interface Mount {
  document_id: string;
  mount_id: string;
  display_title?: string;
  draft_count?: number;
  published_leaves?: number;
}

export interface TocNode {
  node_id: string;
  parent_id: string | null;
  kind: string;
  section_ref: string;
  title: string;
  summary: string;
  depth: number;
  status: string;
}

export interface WorkflowState {
  document_id: string;
  document_title?: string;
  uploaded_path: string | null;
  draft_nodes: number;
  published_leaves: number;
  mount_id: string | null;
  current_step: string;
  steps: Record<string, "pending" | "current" | "done">;
}

export interface AppContext {
  document_id: string;
  document_title?: string;
  paths: Record<string, string>;
  log_buffer_size?: number;
}

export async function fetchContext() {
  const { data } = await http.get<AppContext>("/context");
  return data;
}

export async function fetchMounts() {
  const { data } = await http.get<{ mounts: Mount[]; count: number }>("/mounts");
  return data;
}

export async function fetchWorkflowCurrent() {
  const { data } = await http.get<WorkflowState>("/workflow/current");
  return data;
}

export async function fetchWorkflow(documentId: string) {
  const { data } = await http.get<WorkflowState>(`/workflow/${encodeURIComponent(documentId)}`);
  return data;
}

export async function uploadDocument(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await http.post<{ document_id: string; path: string; workflow: WorkflowState }>(
    "/upload",
    form,
  );
  return data;
}

export async function ingestDocument(documentId?: string) {
  const { data } = await http.post("/ingest", documentId ? { document_id: documentId } : {});
  return data;
}

export async function ingestPath(path: string, documentId?: string) {
  const { data } = await http.post("/ingest/path", { path, document_id: documentId || "" });
  return data;
}

export async function publishDocument(documentId?: string) {
  const { data } = await http.post("/publish", documentId ? { document_id: documentId } : {});
  return data;
}

export async function fetchToc(documentId: string) {
  const { data } = await http.get<{ document_id: string; mount: Mount | null; nodes: TocNode[] }>(
    `/toc/${encodeURIComponent(documentId)}`,
  );
  return data;
}

export async function patchNode(nodeId: string, title: string, summary: string) {
  const { data } = await http.patch(`/nodes/${encodeURIComponent(nodeId)}`, { title, summary });
  return data;
}

export interface LogItem {
  id: number;
  ts: number;
  time: string;
  logger: string;
  level: string;
  message: string;
  line: string;
}

export async function fetchLogs(params?: {
  after_id?: number;
  limit?: number;
  level?: string;
  q?: string;
  tail?: boolean;
}) {
  const { data } = await http.get<{
    items: LogItem[];
    latest_id: number;
    count: number;
    paths?: Record<string, string>;
  }>("/logs", {
    params,
  });
  return data;
}

export async function clearLogs() {
  const { data } = await http.delete<{ ok: boolean }>("/logs");
  return data;
}

export type ChatTraceEvent = { step: string; payload: unknown; at?: string };

export type ChatResult = {
  answer: string;
  verify: { ok: boolean; message: string };
  trace: ChatTraceEvent[];
  trace_path?: string;
  document_id?: string;
};

export async function chat(message: string, documentId?: string, caseId?: string) {
  const { data } = await http.post<ChatResult>("/chat", {
    message,
    document_id: documentId || "",
    case_id: caseId || "",
  });
  return data;
}

export async function chatStream(
  message: string,
  documentId: string | undefined,
  handlers: {
    onProgress?: (label: string) => void;
    onTrace?: (event: ChatTraceEvent) => void;
  },
  caseId?: string,
): Promise<ChatResult> {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      document_id: documentId || "",
      case_id: caseId || "",
    }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  if (!res.body) {
    throw new Error("stream body missing");
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult: ChatResult | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) {
      const line = chunk.trim();
      if (!line.startsWith("data:")) continue;
      const raw = line.slice(5).trim();
      if (!raw) continue;
      const msg = JSON.parse(raw) as {
        type: string;
        payload?: { label?: string };
        event?: ChatTraceEvent;
        result?: ChatResult;
        message?: string;
      };
      if (msg.type === "progress" && msg.payload?.label) {
        handlers.onProgress?.(msg.payload.label);
      } else if (msg.type === "trace" && msg.event) {
        handlers.onTrace?.(msg.event);
      } else if (msg.type === "done" && msg.result) {
        finalResult = msg.result;
      } else if (msg.type === "error") {
        throw new Error(msg.message || "问答失败");
      }
    }
  }
  if (!finalResult) {
    throw new Error("未收到完整回答");
  }
  return finalResult;
}

export default http;
