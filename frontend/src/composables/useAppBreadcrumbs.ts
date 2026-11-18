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

    if (name === "library-new") {
      return [level1, { label: T.navLibraryNew }];
    }

    if (name === "library-ingest" || name === "library-edit" || name === "library-review") {
      const param = String(route.params.documentId || "");
      const docLabel = documentTitle.value?.trim() || documentId.value?.trim() || param || T.docCode;
      const leaf =
        name === "library-ingest"
          ? T.navLibraryIngest
          : name === "library-edit"
            ? T.navLibraryEdit
            : T.navLibraryReview;
      return [
        level1,
        { label: docLabel, to: { name: "library-edit", params: { documentId: param } } },
        { label: leaf },
      ];
    }

    return [{ label: (route.meta.title as string) || "mycs" }];
  });

  return { breadcrumbs };
}