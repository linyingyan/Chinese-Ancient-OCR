<template>
  <div class="card">
    <div style="display:flex; align-items:center; justify-content:space-between;">
      <div style="font-weight:700;">知识图谱（关系抽取）</div>
    </div>
    <div style="height: 12px"></div>

    <el-row :gutter="12">
      <el-col :span="8">
        <el-input v-model="subject" placeholder="主体检索（如：鲁迅）" clearable />
      </el-col>
      <el-col :span="16" style="display:flex; gap:10px;">
        <el-button type="primary" @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-col>
    </el-row>

    <div style="height: 12px"></div>

    <el-tabs v-model="tab">
      <el-tab-pane label="三元组列表" name="list">
        <el-table :data="items" border style="width: 100%">
          <el-table-column prop="subject" label="主体" min-width="120" />
          <el-table-column prop="predicate" label="关系" width="160" />
          <el-table-column prop="object" label="客体" min-width="140" />
          <el-table-column prop="record_id" label="记录ID" width="100" />
          <el-table-column prop="context" label="上下文" min-width="200" />
        </el-table>

        <div style="height: 12px"></div>

        <el-pagination
          background
          layout="total, prev, pager, next, sizes"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </el-tab-pane>

      <el-tab-pane label="关联计算" name="stats">
        <el-row :gutter="12">
          <el-col :span="8">
            <div style="font-weight:700; margin-bottom:8px;">关系类型 Top</div>
            <el-table :data="stats.top_predicates" border style="width: 100%" size="small">
              <el-table-column prop="predicate" label="关系" />
              <el-table-column prop="count" label="数量" width="90" />
            </el-table>
          </el-col>
          <el-col :span="8">
            <div style="font-weight:700; margin-bottom:8px;">客体 Top</div>
            <el-table :data="stats.top_objects" border style="width: 100%" size="small">
              <el-table-column prop="object" label="客体" />
              <el-table-column prop="count" label="数量" width="90" />
            </el-table>
          </el-col>
          <el-col :span="8">
            <div style="font-weight:700; margin-bottom:8px;">关系-客体 Top</div>
            <el-table :data="stats.top_relations" border style="width: 100%" size="small">
              <el-table-column prop="predicate" label="关系" width="120" />
              <el-table-column prop="object" label="客体" />
              <el-table-column prop="count" label="数量" width="90" />
            </el-table>
          </el-col>
        </el-row>

        <div style="height: 12px"></div>
        <el-alert
          type="info"
          :closable="false"
          title="说明"
          :description="`本页会根据三元组数据库做统计计算（不是静态展示）。当前匹配三元组总数：${stats.total}`"
          show-icon
        />
      </el-tab-pane>

      <el-tab-pane label="人物关系网络" name="people">
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form label-width="90px">
              <el-form-item label="最小权重">
                <el-input-number v-model="minWeight" :min="1" :max="50" :step="1" />
              </el-form-item>
              <el-form-item label="最大节点">
                <el-input-number v-model="maxNodes" :min="20" :max="300" :step="10" />
              </el-form-item>
            </el-form>
          </el-col>
          <el-col :span="16" style="display:flex; gap:10px; align-items:center;">
            <el-button type="primary" :loading="networkLoading" @click="loadNetwork">生成网络图</el-button>
            <el-alert
              type="info"
              :closable="false"
              :title="`节点：${network.meta.nodes || 0}，边：${network.meta.links || 0}`"
              description="网络基于三元组中“人物-人物”关系自动构建，边权重为共现次数，边标签为主要关系类型。"
              show-icon
            />
          </el-col>
        </el-row>

        <div style="height: 12px"></div>
        <div ref="chartEl" style="height: 560px; width: 100%;"></div>
      </el-tab-pane>
    </el-tabs>

  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";
import { http } from "../api/client";

const emit = defineEmits(["set-title"]);

const subject = ref("");
const items = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const tab = ref("list");
const stats = ref({ total: 0, top_predicates: [], top_objects: [], top_relations: [] });
const minWeight = ref(1);
const maxNodes = ref(120);
const networkLoading = ref(false);
const network = ref({ nodes: [], links: [], meta: { nodes: 0, links: 0 } });
const chartEl = ref(null);
let chartInstance = null;

async function load() {
  const skip = (page.value - 1) * pageSize.value;
  const res = await http.get("/api/triples", {
    params: { subject: subject.value || undefined, skip, limit: pageSize.value }
  });
  total.value = res.data.total || 0;
  items.value = res.data.items || [];

  const statsRes = await http.get("/api/analytics/relations", {
    params: { subject: subject.value || undefined, limit: 20 }
  });
  stats.value = statsRes.data || { total: 0, top_predicates: [], top_objects: [], top_relations: [] };
}

async function loadNetwork() {
  networkLoading.value = true;
  try {
    const res = await http.get("/api/graph/person_network", {
      params: {
        subject: subject.value || undefined,
        min_weight: minWeight.value,
        max_nodes: maxNodes.value
      }
    });
    network.value = res.data || { nodes: [], links: [], meta: { nodes: 0, links: 0 } };
  } finally {
    networkLoading.value = false;
  }
}

function renderNetwork() {
  if (!chartEl.value) return;
  if (!chartInstance) {
    chartInstance = echarts.init(chartEl.value);
  }
  const nodes = (network.value.nodes || []).map((n) => {
    const v = Number(n.value || 0);
    const size = Math.max(10, Math.min(60, 10 + v * 3));
    return { id: n.id, name: n.name, value: v, symbolSize: size };
  });
  const links = (network.value.links || []).map((l) => ({
    source: l.source,
    target: l.target,
    value: Number(l.value || 0),
    label: { show: false }
  }));
  const linkLabelMap = {};
  for (const l of network.value.links || []) {
    linkLabelMap[`${l.source}__${l.target}`] = l.label || "";
    linkLabelMap[`${l.target}__${l.source}`] = l.label || "";
  }

  chartInstance.setOption({
    tooltip: {
      formatter: (params) => {
        if (params.dataType === "edge") {
          const key = `${params.data.source}__${params.data.target}`;
          const label = linkLabelMap[key] || "";
          return `${params.data.source} → ${params.data.target}<br/>权重：${params.data.value}<br/>${label}`;
        }
        return `${params.data.name}<br/>度：${params.data.value}`;
      }
    },
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        data: nodes,
        links,
        label: { show: true, color: "#333", fontSize: 12 },
        lineStyle: { color: "rgba(120,120,120,0.55)", width: 1 },
        emphasis: { focus: "adjacency" },
        force: { repulsion: 180, edgeLength: 90, gravity: 0.1 }
      }
    ]
  });
  chartInstance.resize();
}

function reset() {
  subject.value = "";
  page.value = 1;
  load();
}

function onPageChange(p) {
  page.value = p;
  load();
}

function onSizeChange(s) {
  pageSize.value = s;
  page.value = 1;
  load();
}

onMounted(() => {
  emit("set-title", { title: "知识图谱", sub: "三元组检索" });
  load();
  loadNetwork();
});

watch(tab, async (t) => {
  if (t === "people") {
    await nextTick();
    renderNetwork();
  }
});

watch(network, async () => {
  if (tab.value === "people") {
    await nextTick();
    renderNetwork();
  }
});

watch([minWeight, maxNodes], () => {
  if (tab.value === "people") {
    loadNetwork();
  }
});

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});
</script>
