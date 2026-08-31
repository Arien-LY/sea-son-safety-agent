import { createRouter, createWebHistory } from "vue-router";
import HomeView from "./views/HomeView.vue";
import RecordsView from "./views/RecordsView.vue";

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/chat" },
    { path: "/chat", name: "chat", component: HomeView },
    { path: "/consult", redirect: "/chat" },
    { path: "/submit", name: "submit", component: HomeView },
    { path: "/records", name: "records", component: RecordsView },
    { path: "/records/:recordId", name: "record-detail", component: HomeView },
    { path: "/:pathMatch(.*)*", redirect: "/chat" },
  ],
});
