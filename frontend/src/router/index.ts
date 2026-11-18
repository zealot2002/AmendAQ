import { createRouter, createWebHistory } from "vue-router";
import AdminLayout from "@/layouts/AdminLayout.vue";
import { T } from "@/constants/terminology";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      component: AdminLayout,
      redirect: "/library",
      children: [
        {
          path: "library",
          name: "library",
          component: () => import("@/views/KnowledgeListView.vue"),
          meta: { title: T.navLibraryMgmt, menu: "/library" },
        },
        {
          path: "library/new",
          name: "library-new",
          component: () => import("@/views/LibraryCreateView.vue"),
          meta: { title: T.navLibraryNew, menu: "/library" },
        },
        {
          path: "library/:documentId/ingest",
          name: "library-ingest",
          component: () => import("@/views/LibraryCreateView.vue"),
          meta: { title: T.navLibraryIngest, menu: "/library" },
        },
        {
          path: "library/:documentId/edit",
          name: "library-edit",
          component: () => import("@/views/WorkflowView.vue"),
          meta: { title: T.navLibraryEdit, menu: "/library" },
        },
        {
          path: "library/:documentId/review",
          name: "library-review",
          component: () => import("@/views/WikiReviewView.vue"),
          meta: { title: T.navLibraryReview, menu: "/library", fullHeight: true },
        },
        {
          path: "chat",
          name: "chat",
          component: () => import("@/views/ChatView.vue"),
          meta: { title: T.navChat, menu: "/chat" },
        },
        {
          path: "logs",
          name: "logs",
          component: () => import("@/views/LogView.vue"),
          meta: { title: T.navLogs, menu: "/logs" },
        },
        {
          path: "library/_/edit",
          redirect: { name: "library-new" },
        },
        { path: "workflow", redirect: { name: "library-new" } },
        { path: "wiki", redirect: "/library" },
        { path: "mounts", redirect: "/library" },
      ],
    },
  ],
});

export default router;