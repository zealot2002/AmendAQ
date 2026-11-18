import axios from "axios";

/** FastAPI `detail` string or validation array → readable message. */
export function formatApiError(e: unknown): string {
  if (!axios.isAxiosError(e)) {
    return e instanceof Error ? e.message : String(e);
  }
  const data = e.response?.data as { detail?: unknown } | string | undefined;
  if (typeof data === "string" && data.trim()) {
    return data;
  }
  if (data && typeof data === "object" && "detail" in data) {
    const detail = data.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((x) => (typeof x === "object" && x && "msg" in x ? String((x as { msg: string }).msg) : String(x)))
        .join("；");
    }
  }
  if (e.code === "ECONNABORTED") {
    return "请求超时，请重试或查看运行日志";
  }
  return e.message || `HTTP ${status ?? "error"}`;
}