import { computed } from "vue";
import { useRoute, type RouteLocationRaw } from "vue-router";
import { T } from "@/constants/terminology";
import { useDocumentId } from "@/composables/useDocumentId";

export type BreadcrumbItem = {
  label: string;
  to?: RouteLocationRaw;
};

export function useAppBreadcrumbs() {
  const route = useRoute();
  const { documentId, documentTitle } = useDocumentId();

  const breadcrumbs = computed((): BreadcrumbItem[] => {
    const name = route.name as string | undefined;

    if (name === "chat") return [{ label: T.navChat }];
    if (name === "logs") return [{ label: T.navLogs }];
    if (name === "library") return [{ label: T.navLibraryMgmt }];

    const level1 = { label: T.navLibraryMgmt, to: { name: "library" } as RouteLocationRaw };

    if (name === "library-detail") {
      const param = String(route.params.documentId || "");
      const docLabel = documentTitle.value?.trim() || param || T.docCode;
      return [level1, { label: docLabel }];
    }

    return [{ label: (route.meta.title as string) || "amendaq" }];
  });

  return { breadcrumbs };
}