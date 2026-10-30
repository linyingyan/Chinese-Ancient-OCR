<template>
  <div class="card">
    <div style="display:flex; align-items:center; justify-content:space-between;">
      <div style="font-weight:700;">时空演变（聚类与时间线）</div>
      <div style="display:flex; gap:10px;">
        <el-button :loading="building" type="primary" @click="build(false)">构建/更新索引</el-button>
        <el-button :loading="building" type="danger" plain @click="build(true)">全量重建</el-button>
        <el-button @click="load">刷新</el-button>
      </div>
    </div>

    <div style="height: 12px"></div>

    <el-row :gutter="12">
      <el-col :span="8">
        <el-input v-model="subject" placeholder="主体检索（如：鲁迅）" clearable />
      </el-col>
      <el-col :span="16" style="display:flex; gap:10px;">
        <el-button type="primary" @click="reset">重置</el-button>
      </el-col>
    </el-row>

    <div style="height: 12px"></div>

    <el-tabs v-model="tab">
      <el-tab-pane label="时间线" name="timeline">
        <el-table :data="timelineItems" border style="width: 100%">
          <el-table-column prop="time" label="时间" width="140" />
          <el-table-column prop="subject" label="主体" width="140" />
          <el-table-column prop="action" label="动作" width="120" />
          <el-table-column prop="location_or_object" label="地点/对象" min-width="160" />
          <el-table-column prop="count" label="证据数" width="90" />
          <el-table-column prop="summary" label="聚类摘要" min-width="240" />
          <el-table-column label="关键词" min-width="220">
            <template #default="{ row }">
              <span style="color:#666;">{{ (row.keywords || []).slice(0, 10).join(' / ') }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button size="small" @click="openCluster(row.cluster_id)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div style="height: 12px"></div>

        <el-pagination
          background
          layout="total, prev, pager, next, sizes"
          :total="timelineTotal"
          :page-size="pageSize"
          :current-page="page"
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </el-tab-pane>

      <el-tab-pane label="聚类库" name="clusters">
        <el-table :data="clusterItems" border style="width: 100%" @row-dblclick="(row)=>openCluster(row.id)">
          <el-table-column prop="time" label="时间" width="140" />
          <el-table-column prop="subject" label="主体" width="140" />
          <el-table-column prop="action" label="动作" width="120" />
          <el-table-column prop="location_or_object" label="地点/对象" min-width="160" />
          <el-table-column prop="count" label="证据数" width="90" />
          <el-table-column label="关键词" min-width="260">
            <template #default="{ row }">
              <span style="color:#666;">{{ (row.keywords || []).slice(0, 12).join(' / ') }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button size="small" @click="openCluster(row.id)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div style="height: 12px"></div>

        <el-pagination
          background
          layout="total, prev, pager, next, sizes"
          :total="clusterTotal"
          :page-size="pageSize"
          :current-page="page"
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </el-tab-pane>
    </el-tabs>

    <div style="height: 12px"></div>
    <el-alert
      type="info"
      :closable="false"
      title="说明"
      description="系统会从不同文献中抽取关键词与时空事件，并把相似事件聚合成“聚类库”。时间线展示聚类后的事件节点，点击详情可查看该聚类在不同文献中的上下文证据。"
      show-icon
    />
  </div>

  <el-drawer v-model="drawer" size="55%" :with-header="false">
    <div style="display:flex; align-items:center; justify-content:space-between;">
      <div style="font-weight:700;">聚类详情</div>
      <el-button @click="drawer=false">关闭</el-button>
    </div>
    <div style="height: 10px"></div>
    <el-descriptions :column="2" border>
      <el-descriptions-item label="时间">{{ detail.cluster.time }}</el-descriptions-item>
      <el-descriptions-item label="主体">{{ detail.cluster.subject }}</el-descriptions-item>
      <el-descriptions-item label="动作">{{ detail.cluster.action }}</el-descriptions-item>
      <el-descriptions-item label="地点/对象">{{ detail.cluster.location_or_object }}</el-descriptions-item>
    </el-descriptions>
    <div style="height: 10px"></div>
    <el-alert v-if="detail.cluster.summary" type="success" :closable="false" title="聚类摘要" :description="detail.cluster.summary" show-icon />
    <div style="height: 10px"></div>
    <el-alert
      type="info"
      :closable="false"
      title="关键词"
      :description="(detail.cluster.keywords || []).join(' / ')"
      show-icon
    />
    <div style="height: 12px"></div>
    <el-table :data="detail.events" border style="width: 100%" height="520">
      <el-table-column prop="record_id" label="记录ID" width="90" />
      <el-table-column prop="title" label="来源标题" min-width="160" />
      <el-table-column prop="dynasty" label="朝代" width="120" />
      <el-table-column prop="time" label="时间" width="140" />
      <el-table-column prop="context" label="上下文" min-width="260" />
    </el-table>
  </el-drawer>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import { http } from "../api/client";
import { ElMessage, ElMessageBox } from "element-plus";

const emit = defineEmits(["set-title"]);

const subject = ref("");
const tab = ref("timeline");
const timelineItems = ref([]);
const timelineTotal = ref(0);
const clusterItems = ref([]);
const clusterTotal = ref(0);
const page = ref(1);
const pageSize = ref(20);
const building = ref(false);

const drawer = ref(false);
const detail = ref({ cluster: {}, events: [] });

async function load() {
  try {
    const skip = (page.value - 1) * pageSize.value;
    if (tab.value === "clusters") {
      const res = await http.get("/api/spacetime/clusters", {
        params: { subject: subject.value || undefined, skip, limit: pageSize.value }
      });
      clusterTotal.value = res.data.total || 0;
      clusterItems.value = res.data.items || [];
    } else {
      const res = await http.get("/api/spacetime/timeline", {
        params: { subject: subject.value || undefined, skip, limit: pageSize.value }
      });
      timelineTotal.value = res.data.total || 0;
      timelineItems.value = res.data.items || [];
    }
  } catch (e) {
    ElMessage.error("加载失败");
  }
}

async function build(rebuildAll) {
  building.value = true;
  try {
    if (rebuildAll) {
      await ElMessageBox.confirm("这会清空并重建所有时空索引（可能耗时较长），确认继续？", "全量重建确认", { type: "warning" });
    }
    await http.post("/api/spacetime/build", { rebuild_all: !!rebuildAll, use_llm: true, max_events_per_record: 20 });
    ElMessage.success(rebuildAll ? "全量重建完成" : "索引更新完成");
    page.value = 1;
    load();
  } catch (e) {
    if (rebuildAll) return;
    ElMessage.error("构建失败（请检查后端与大模型配置）");
  } finally {
    building.value = false;
  }
}

async function openCluster(clusterId) {
  if (!clusterId) return;
  try {
    const res = await http.get(`/api/spacetime/clusters/${clusterId}`);
    detail.value = res.data || { cluster: {}, events: [] };
    drawer.value = true;
  } catch (e) {
    ElMessage.error("加载详情失败");
  }
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
  emit("set-title", { title: "时空演变", sub: "事件列表与时间地点" });
  load();
});

watch(tab, () => {
  page.value = 1;
  load();
});
</script>
