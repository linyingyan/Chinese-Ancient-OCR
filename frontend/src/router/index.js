import { createRouter, createWebHistory } from "vue-router";
import AdminLayout from "../views/AdminLayout.vue";
import Dashboard from "../views/Dashboard.vue";
import Ocr from "../views/Ocr.vue";
import Records from "../views/Records.vue";
import Graph from "../views/Graph.vue";
import QA from "../views/QA.vue";
import Spacetime from "../views/Spacetime.vue";
import Export from "../views/Export.vue";
import Settings from "../views/Settings.vue";

const routes = [
  {
    path: "/",
    component: AdminLayout,
    children: [
      { path: "", name: "dashboard", component: Dashboard },
      { path: "ocr", name: "ocr", component: Ocr },
      { path: "records", name: "records", component: Records },
      { path: "graph", name: "graph", component: Graph },
      { path: "qa", name: "qa", component: QA },
      { path: "spacetime", name: "spacetime", component: Spacetime },
      { path: "export", name: "export", component: Export },
      { path: "settings", name: "settings", component: Settings }
    ]
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

export default router;
