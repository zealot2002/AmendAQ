import { createRouter, createWebHistory } from "vue-router";
import AdminLayout from "@/layouts/AdminLayout.vue";
import { T } from "@/constants/terminology";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      component: AdminLayout,
      redirect: "/workflow",
      children: [
        {
          path: "workflow",
          name: "workflow",
          component: () => import("@/views/WorkflowView.vue"),
          meta: { title: T.navWorkflow },
        },
        {
          path: "wiki",
          name: "wiki",
          component: () => import("@/views/WikiReviewView.vue"),
          meta: { title: T.navReview },
        },
        {
          path: "chat",
          name: "chat",
          component: () => import("@/views/ChatView.vue"),
          meta: { title: T.navChat },
        },
        {
          path: "mounts",
          name: "mounts",
          component: () => import("@/views/MountsView.vue"),
          meta: { title: T.navLibrary },
        },
        {
          path: "logs",
          name: "logs",
          component: () => import("@/views/LogView.vue"),
          meta: { title: "运行日志" },
        },
      ],
    },
  ],
});

export default router;
