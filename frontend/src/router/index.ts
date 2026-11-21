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
          redirect: { name: "library" },
        },
        {
          path: "library/:documentId",
          name: "library-detail",
          component: () => import("@/views/KnowledgeDetailView.vue"),
          meta: { title: T.navLibraryDetail, menu: "/library" },
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
          redirect: { name: "library" },
        },
        { path: "workflow", redirect: { name: "library" } },
        { path: "wiki", redirect: "/library" },
        { path: "mounts", redirect: "/library" },
      ],
    },
  ],
});

export default router;