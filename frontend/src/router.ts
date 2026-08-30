import { createRouter, createWebHistory } from "vue-router";
import HomeView from "./views/HomeView.vue";
import RecordsView from "./views/RecordsView.vue";

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/consult" },
    { path: "/chat", name: "chat", component: HomeView },
    { path: "/consult", name: "consult", component: HomeView },
    { path: "/submit", name: "submit", component: HomeView },
    { path: "/records", name: "records", component: RecordsView },
    { path: "/records/:recordId", name: "record-detail", component: HomeView },
    { path: "/:pathMatch(.*)*", redirect: "/consult" },
  ],
});
