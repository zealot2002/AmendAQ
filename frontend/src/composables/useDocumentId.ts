import { ref, watch } from "vue";
import { fetchContext, fetchWorkflow } from "@/api/client";

const STORAGE_KEY = "mycs_document_id";
const TITLE_STORAGE_KEY = "mycs_document_title";

const documentId = ref(localStorage.getItem(STORAGE_KEY) || "");
const documentTitle = ref(localStorage.getItem(TITLE_STORAGE_KEY) || "");
const paths = ref<Record<string, string>>({});

export function useDocumentId() {
  async function refreshTitleForId(id: string) {
    const trimmed = id.trim();
    if (!trimmed) {
      documentTitle.value = "";
      return;
    }
    try {
      const wf = await fetchWorkflow(trimmed);
      const t = (wf.document_title || "").trim();
      if (t) {
        documentTitle.value = t;
      }
    } catch {
      /* API offline */
    }
  }

  async function refreshFromServer() {
    try {
      const ctx = await fetchContext();
      paths.value = ctx.paths || {};
      if (ctx.document_id) {
        documentId.value = ctx.document_id;
      }
      if (ctx.document_title?.trim()) {
        documentTitle.value = ctx.document_title.trim();
      } else if (ctx.document_id) {
        await refreshTitleForId(ctx.document_id);
      }
    } catch {
      /* API offline */
    }
  }

  function setDocumentId(id: string, title?: string) {
    documentId.value = id.trim();
    if (title?.trim()) {
      documentTitle.value = title.trim();
    } else if (id.trim()) {
      void refreshTitleForId(id.trim());
    } else {
      documentTitle.value = "";
    }
  }

  watch(documentId, (v) => {
    if (v) localStorage.setItem(STORAGE_KEY, v);
    else localStorage.removeItem(STORAGE_KEY);
  });

  watch(documentTitle, (v) => {
    if (v) localStorage.setItem(TITLE_STORAGE_KEY, v);
    else localStorage.removeItem(TITLE_STORAGE_KEY);
  });

  watch(
    documentId,
    (v) => {
      if (v && !documentTitle.value) {
        void refreshTitleForId(v);
      }
    },
    { immediate: true },
  );

  function clearDocumentId() {
    documentId.value = "";
    documentTitle.value = "";
  }

  return { documentId, documentTitle, paths, setDocumentId, clearDocumentId, refreshFromServer };
}
